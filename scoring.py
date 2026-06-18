import json
import pathlib
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

import config
from games_client import normalize_name, is_real_participant, is_finished, parse_goals


def _parse_local_date(game: dict) -> datetime:
    try:
        return datetime.strptime(game.get("local_date", ""), "%m/%d/%Y %H:%M")
    except ValueError:
        return datetime.min


@dataclass
class TeamStats:
    match_pts: float = 0.0
    goal_pts: float = 0.0
    qualify_pts: float = 0.0
    knockout_pts: float = 0.0
    qualified: bool = False  # reached R32
    matches: int = 0


# Maps game type → (stage label used in dark-horse, knockout bonus)
_STAGE_BONUS: dict[str, float] = {
    "qf": config.QF_BONUS,
    "sf": config.SF_BONUS,
    "final": config.FINAL_BONUS,
}

_DH_STAGE_BONUS: dict[str, float] = {
    "r32": config.DARK_HORSE_BONUS["r16"],
    "r16": config.DARK_HORSE_BONUS["r16"],
    "qf": config.DARK_HORSE_BONUS["qf"],
    "sf": config.DARK_HORSE_BONUS["sf"],
}


def _tier(canonical_name: str) -> int:
    return config.TEAM_TIERS.get(canonical_name, 1)


def _build_stats(
    games: list[dict],
) -> tuple[dict, dict, dict, list[str], "dict | None"]:
    """Compute per-team stats, award pts, dark-horse pts, warnings, and last match."""
    stats: dict[str, TeamStats] = defaultdict(TeamStats)
    warnings: list[str] = []

    finished_games = [g for g in games if is_finished(g)]
    last_match = max(finished_games, key=_parse_local_date) if finished_games else None

    # --- Collect all canonical API team names seen in games (for warning detection)
    api_teams: set[str] = set()
    for g in games:
        for side in ("home", "away"):
            tid = g.get(f"{side}_team_id", "0")
            name = g.get(f"{side}_team_name_en", "")
            if is_real_participant(tid, name):
                api_teams.add(normalize_name(name))

    # --- Process each finished game
    for g in games:
        if not is_finished(g):
            continue

        gtype = g.get("type", "")
        home_id = g.get("home_team_id", "0")
        away_id = g.get("away_team_id", "0")
        home_raw = g.get("home_team_name_en", "")
        away_raw = g.get("away_team_name_en", "")

        home_real = is_real_participant(home_id, home_raw)
        away_real = is_real_participant(away_id, away_raw)

        if not home_real or not away_real:
            continue

        home = normalize_name(home_raw)
        away = normalize_name(away_raw)

        stats[home].matches += 1
        stats[away].matches += 1

        home_goals = parse_goals(g.get("home_scorers"), g.get("home_score"))
        away_goals = parse_goals(g.get("away_scorers"), g.get("away_score"))

        home_tier = _tier(home)
        away_tier = _tier(away)

        # Match points
        if home_goals > away_goals:
            stats[home].match_pts += config.WIN_PTS
        elif away_goals > home_goals:
            stats[away].match_pts += config.WIN_PTS
        else:
            stats[home].match_pts += config.DRAW_PTS
            stats[away].match_pts += config.DRAW_PTS

        # Goal points (shooter-safe count × tier multiplier)
        stats[home].goal_pts += home_goals * config.GOAL_MULTIPLIER[home_tier]
        stats[away].goal_pts += away_goals * config.GOAL_MULTIPLIER[away_tier]

        # Qualification bonus (R32 appearance = cleared group stage)
        if gtype == "r32":
            for name, tier in ((home, home_tier), (away, away_tier)):
                if not stats[name].qualified:
                    stats[name].qualified = True
                    stats[name].qualify_pts += config.QUALIFY_BONUS[tier]

        # Knockout progression bonuses
        if gtype in _STAGE_BONUS:
            bonus = _STAGE_BONUS[gtype]
            stats[home].knockout_pts += bonus
            stats[away].knockout_pts += bonus

            # Champion / Runner-up (only for final)
            if gtype == "final":
                if home_goals > away_goals:
                    stats[home].knockout_pts += config.CHAMPION_BONUS
                    stats[away].knockout_pts += config.RUNNER_UP_BONUS
                elif away_goals > home_goals:
                    stats[away].knockout_pts += config.CHAMPION_BONUS
                    stats[home].knockout_pts += config.RUNNER_UP_BONUS
                # Tied on goals (penalty final) → no champion bonus assigned (documented limitation)

    # --- Warn on unmatched roster teams
    all_roster_canonical: dict[str, str] = {}  # canonical → contender
    for contender, teams in config.CONTENDERS.items():
        for raw in teams:
            canon = normalize_name(raw)
            all_roster_canonical[canon] = contender

    for canon in all_roster_canonical:
        if canon not in config.TEAM_TIERS:
            warnings.append(f"No tier defined for '{canon}' — defaulting to Tier 1")

    # --- Awards: highest award per team → credited to team owner
    team_award_pts: dict[str, float] = defaultdict(float)
    for award_key, team_raw in config.AWARDS.items():
        canon = normalize_name(team_raw)
        pts = config.AWARD_PTS.get(award_key, 0.0)
        team_award_pts[canon] = max(team_award_pts[canon], pts)

    # --- Dark Horse
    contender_dh_pts: dict[str, float] = defaultdict(float)
    for contender, dh_team_raw in config.DARK_HORSE.items():
        canon = normalize_name(dh_team_raw)
        tier = _tier(canon)
        if tier not in (3, 4):
            warnings.append(f"Dark Horse '{dh_team_raw}' for {contender} is not Tier 3/4")
        best = 0.0
        for stage, bonus in sorted(_DH_STAGE_BONUS.items(), key=lambda x: x[1], reverse=True):
            # We infer stage from stats: qualified covers r32/r16; knockout covers qf/sf
            if stage in ("r32", "r16") and stats[canon].qualified:
                best = max(best, config.DARK_HORSE_BONUS["r16"])
            elif stage == "qf" and stats[canon].knockout_pts >= config.QF_BONUS:
                best = max(best, config.DARK_HORSE_BONUS["qf"])
            elif stage == "sf" and stats[canon].knockout_pts >= config.QF_BONUS + config.SF_BONUS:
                best = max(best, config.DARK_HORSE_BONUS["sf"])
        contender_dh_pts[contender] = best

    return stats, team_award_pts, contender_dh_pts, warnings, last_match


def build_leaderboard(games: list[dict]) -> tuple[list[dict], list[str], "dict | None"]:
    stats, team_award_pts, contender_dh_pts, warnings, last_match = _build_stats(games)

    leaderboard_rows: list[dict] = []
    for contender, teams in config.CONTENDERS.items():
        match_total = goal_total = qualify_total = knockout_total = award_total = 0.0
        matches_total = 0

        for raw in teams:
            canon = normalize_name(raw)
            s = stats[canon]
            match_total += s.match_pts
            goal_total += s.goal_pts
            qualify_total += s.qualify_pts
            knockout_total += s.knockout_pts
            award_total += team_award_pts.get(canon, 0.0)
            matches_total += s.matches

        dh_total = contender_dh_pts.get(contender, 0.0)
        grand_total = match_total + goal_total + qualify_total + knockout_total + award_total + dh_total

        leaderboard_rows.append({
            "user": contender,
            "points": round(grand_total, 2),
            "matches": matches_total,
            "breakdown": {
                "match": round(match_total, 2),
                "goals": round(goal_total, 2),
                "qualification": round(qualify_total, 2),
                "knockout": round(knockout_total, 2),
                "awards": round(award_total, 2),
                "dark_horse": round(dh_total, 2),
            },
        })

    leaderboard_rows.sort(key=lambda r: (-r["points"], r["matches"]))

    # Assign ranks (ties share the same rank)
    rank = 1
    for i, row in enumerate(leaderboard_rows):
        if i > 0 and row["points"] < leaderboard_rows[i - 1]["points"]:
            rank = i + 1
        row["rank"] = rank

    return leaderboard_rows, warnings, last_match


def build_user_report(games: list[dict], user_name: str) -> dict:
    """Returns per-team stats breakdown for a single contender."""
    matched_contender = None
    for name in config.CONTENDERS:
        if name.lower() == user_name.lower():
            matched_contender = name
            break
    if matched_contender is None:
        available = ", ".join(sorted(config.CONTENDERS.keys()))
        raise ValueError(f"User '{user_name}' not found. Available: {available}")

    stats, team_award_pts, contender_dh_pts, _, _ = _build_stats(games)

    dh_team_raw = config.DARK_HORSE.get(matched_contender, "")
    dh_team_canon = normalize_name(dh_team_raw) if dh_team_raw else ""
    dh_pts = contender_dh_pts.get(matched_contender, 0.0)

    team_rows = []
    for raw in config.CONTENDERS[matched_contender]:
        canon = normalize_name(raw)
        s = stats[canon]
        is_dh = canon == dh_team_canon
        team_dh_pts = dh_pts if is_dh else 0.0
        award_pts = team_award_pts.get(canon, 0.0)
        total = s.match_pts + s.goal_pts + s.qualify_pts + s.knockout_pts + award_pts + team_dh_pts
        team_rows.append({
            "name": canon,
            "tier": _tier(canon),
            "is_dark_horse": is_dh,
            "match_pts": round(s.match_pts, 2),
            "goal_pts": round(s.goal_pts, 2),
            "qualify_pts": round(s.qualify_pts, 2),
            "knockout_pts": round(s.knockout_pts, 2),
            "award_pts": round(award_pts, 2),
            "dh_pts": round(team_dh_pts, 2),
            "total": round(total, 2),
            "matches": s.matches,
        })

    team_rows.sort(key=lambda r: r["total"], reverse=True)
    grand_total = round(sum(r["total"] for r in team_rows), 2)

    return {
        "user": matched_contender,
        "teams": team_rows,
        "grand_total": grand_total,
    }


_SNAPSHOT_PATH = pathlib.Path(__file__).parent / "rank_snapshot.json"


def load_rank_snapshot() -> dict[str, int]:
    if not _SNAPSHOT_PATH.exists():
        return {}
    with open(_SNAPSHOT_PATH) as f:
        return json.load(f)


def save_rank_snapshot(rows: list[dict]) -> None:
    snapshot = {row["user"]: row["rank"] for row in rows}
    with open(_SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

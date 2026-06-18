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

    # --- Warn on API team names that don't normalize to a known tier (points silently dropped)
    for canon in sorted(api_teams):
        if canon not in config.TEAM_TIERS:
            warnings.append(f"API team '{canon}' has no tier mapping — points dropped (check TEAM_ALIASES)")

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


def build_contender_timeline(games: list[dict], contender: str) -> dict:
    """Returns a flat chronological timeline of match events for a contender."""
    matched_contender = None
    for name in config.CONTENDERS:
        if name.lower() == contender.lower():
            matched_contender = name
            break
    if matched_contender is None:
        available = ", ".join(sorted(config.CONTENDERS.keys()))
        raise ValueError(f"User '{contender}' not found. Available: {available}")

    stats, team_award_pts, contender_dh_pts, _, _ = _build_stats(games)

    team_canons = {normalize_name(raw) for raw in config.CONTENDERS[matched_contender]}

    dh_team_raw = config.DARK_HORSE.get(matched_contender, "")
    dh_team_canon = normalize_name(dh_team_raw) if dh_team_raw else ""
    dh_pts = contender_dh_pts.get(matched_contender, 0.0)

    award_events: list[dict] = []
    for canon in team_canons:
        a_pts = team_award_pts.get(canon, 0.0)
        if a_pts > 0:
            award_name = ""
            for award_key, team_raw in config.AWARDS.items():
                if normalize_name(team_raw) == canon and config.AWARD_PTS.get(award_key, 0.0) == a_pts:
                    award_name = award_key.replace("_", " ").title()
                    break
            award_events.append({"team": canon, "name": award_name, "pts": a_pts})

    finished = sorted([g for g in games if is_finished(g)], key=_parse_local_date)

    _STAGE_LABEL = {"group": "", "r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF", "final": "Final"}
    team_qualified: dict[str, bool] = {}
    events: list[dict] = []
    running_total = 0.0

    for g in finished:
        gtype = g.get("type", "")
        home_raw = g.get("home_team_name_en", "")
        away_raw = g.get("away_team_name_en", "")
        if not is_real_participant(g.get("home_team_id", "0"), home_raw) or \
           not is_real_participant(g.get("away_team_id", "0"), away_raw):
            continue

        home = normalize_name(home_raw)
        away = normalize_name(away_raw)
        home_goals = parse_goals(g.get("home_scorers"), g.get("home_score"))
        away_goals = parse_goals(g.get("away_scorers"), g.get("away_score"))
        game_date = _parse_local_date(g)
        date_str = game_date.strftime("%d %b") if game_date != datetime.min else "?"

        for team, opponent, team_goals, opp_goals in (
            (home, away, home_goals, away_goals),
            (away, home, away_goals, home_goals),
        ):
            if team not in team_canons:
                continue

            tier = _tier(team)
            goal_mult = config.GOAL_MULTIPLIER[tier]

            if team_goals > opp_goals:
                result, match_pts = "W", float(config.WIN_PTS)
            elif team_goals < opp_goals:
                result, match_pts = "L", 0.0
            else:
                result, match_pts = "D", float(config.DRAW_PTS)

            goal_pts = round(team_goals * goal_mult, 2)

            qualify_pts = 0.0
            if gtype == "r32" and not team_qualified.get(team, False):
                team_qualified[team] = True
                qualify_pts = config.QUALIFY_BONUS[tier]

            knockout_pts = champion_pts = runner_up_pts = 0.0
            if gtype in _STAGE_BONUS:
                knockout_pts = _STAGE_BONUS[gtype]
            if gtype == "final":
                if team_goals > opp_goals:
                    champion_pts = float(config.CHAMPION_BONUS)
                elif team_goals < opp_goals:
                    runner_up_pts = float(config.RUNNER_UP_BONUS)

            event_total = round(match_pts + goal_pts + qualify_pts + knockout_pts + champion_pts + runner_up_pts, 2)
            running_total = round(running_total + event_total, 2)

            events.append({
                "date_str": date_str,
                "team": team,
                "tier": tier,
                "opponent": opponent,
                "result": result,
                "stage": _STAGE_LABEL.get(gtype, gtype),
                "goals": team_goals,
                "goal_mult": goal_mult,
                "match_pts": match_pts,
                "goal_pts": goal_pts,
                "qualify_pts": qualify_pts,
                "knockout_pts": knockout_pts,
                "champion_pts": champion_pts,
                "runner_up_pts": runner_up_pts,
                "event_total": event_total,
                "cumulative": running_total,
            })

    dh_info = None
    if dh_pts > 0 and dh_team_canon:
        dh_s = stats[dh_team_canon]
        if dh_s.knockout_pts >= config.QF_BONUS + config.SF_BONUS:
            dh_stage = "SF"
        elif dh_s.knockout_pts >= config.QF_BONUS:
            dh_stage = "QF"
        elif dh_s.qualified:
            dh_stage = "R16"
        else:
            dh_stage = "R32"
        dh_info = {"team": dh_team_canon, "stage": dh_stage, "pts": dh_pts}

    grand_total = round(running_total + dh_pts + sum(a["pts"] for a in award_events), 2)

    return {
        "user": matched_contender,
        "events": events,
        "match_subtotal": running_total,
        "dark_horse": dh_info,
        "awards": award_events,
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

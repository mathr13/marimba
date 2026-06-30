import json
import pathlib
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

import config
from games_client import is_real_participant, is_finished, parse_goals, display_name_for_id, load_team_registry


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
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0


# Maps game type → knockout bonus
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


def _tier(team_id: str) -> int:
    return config.TEAM_TIERS.get(team_id, 1)


def _is_penalty_game(game: dict) -> bool:
    """Check if a game went to penalty shootout."""
    home_pen = game.get("home_penalty_score")
    away_pen = game.get("away_penalty_score")
    if home_pen is None or away_pen is None:
        return False
    try:
        int(home_pen)
        int(away_pen)
        return True
    except (ValueError, TypeError):
        return False


def _penalty_winner(game: dict) -> "str | None":
    """Return 'home', 'away', or None based on penalty shootout scores."""
    if not _is_penalty_game(game):
        return None
    home_pen = int(game.get("home_penalty_score", 0))
    away_pen = int(game.get("away_penalty_score", 0))
    if home_pen > away_pen:
        return "home"
    elif away_pen > home_pen:
        return "away"
    return None


def _build_stats(
    games: list[dict],
) -> tuple[dict, dict, dict, list[str], "dict | None"]:
    """Compute per-team stats, award pts, dark-horse pts, warnings, and last match.
    All dicts keyed by team_id (string).
    """
    stats: dict[str, TeamStats] = defaultdict(TeamStats)
    warnings: list[str] = []

    finished_games = [g for g in games if is_finished(g)]
    last_match = max(finished_games, key=_parse_local_date) if finished_games else None

    # --- Config validation: every roster/tier/dark-horse id must be in the registry
    registry = load_team_registry()
    for contender, team_ids in config.CONTENDERS.items():
        for tid in team_ids:
            if tid not in registry:
                warnings.append(f"Roster id '{tid}' for {contender} not found in teams.json — check config")
            elif tid not in config.TEAM_TIERS:
                warnings.append(f"No tier defined for id '{tid}' ({display_name_for_id(tid)}) — defaulting to Tier 1")
    for contender, dh_id in config.DARK_HORSE.items():
        if dh_id not in registry:
            warnings.append(f"Dark Horse id '{dh_id}' for {contender} not found in teams.json")
        elif _tier(dh_id) not in (3, 4):
            warnings.append(f"Dark Horse '{display_name_for_id(dh_id)}' for {contender} is not Tier 3/4")
    for award_key, tid in config.AWARDS.items():
        if tid not in registry:
            warnings.append(f"Award '{award_key}' team id '{tid}' not found in teams.json")

    # --- Process each finished game
    for g in games:
        if not is_finished(g):
            continue

        gtype = g.get("type", "")
        home_id = g.get("home_team_id", "0")
        away_id = g.get("away_team_id", "0")
        home_raw = g.get("home_team_name_en", "")
        away_raw = g.get("away_team_name_en", "")

        if not is_real_participant(home_id, home_raw) or not is_real_participant(away_id, away_raw):
            continue

        if home_id not in registry or away_id not in registry:
            warnings.append(f"Game team_id not in teams.json registry: {home_id}/{away_id} ({home_raw} vs {away_raw})")
            continue

        stats[home_id].matches += 1
        stats[away_id].matches += 1

        home_goals = parse_goals(g.get("home_scorers"), g.get("home_score"))
        away_goals = parse_goals(g.get("away_scorers"), g.get("away_score"))

        home_tier = _tier(home_id)
        away_tier = _tier(away_id)

        stats[home_id].goals_for += home_goals
        stats[home_id].goals_against += away_goals
        stats[away_id].goals_for += away_goals
        stats[away_id].goals_against += home_goals

        # Match points
        if home_goals > away_goals:
            stats[home_id].match_pts += config.WIN_PTS
            stats[home_id].wins += 1
            stats[away_id].losses += 1
        elif away_goals > home_goals:
            stats[away_id].match_pts += config.WIN_PTS
            stats[away_id].wins += 1
            stats[home_id].losses += 1
        # Regular time draw — check for penalty shootout
        else:
            pen_winner = _penalty_winner(g)
            if pen_winner == "home":
                stats[home_id].match_pts += config.WIN_PTS
                stats[home_id].wins += 1
                stats[away_id].losses += 1
            elif pen_winner == "away":
                stats[away_id].match_pts += config.WIN_PTS
                stats[away_id].wins += 1
                stats[home_id].losses += 1
            else:
                stats[home_id].match_pts += config.DRAW_PTS
                stats[away_id].match_pts += config.DRAW_PTS
                stats[home_id].draws += 1
                stats[away_id].draws += 1

        # Goal points (shooter-safe count × tier multiplier)
        stats[home_id].goal_pts += home_goals * config.GOAL_MULTIPLIER[home_tier]
        stats[away_id].goal_pts += away_goals * config.GOAL_MULTIPLIER[away_tier]

        # Qualification bonus (R32 appearance = cleared group stage)
        if gtype == "r32":
            for tid, tier in ((home_id, home_tier), (away_id, away_tier)):
                if not stats[tid].qualified:
                    stats[tid].qualified = True
                    stats[tid].qualify_pts += config.QUALIFY_BONUS[tier]

        # Knockout progression bonuses
        if gtype in _STAGE_BONUS:
            bonus = _STAGE_BONUS[gtype]
            stats[home_id].knockout_pts += bonus
            stats[away_id].knockout_pts += bonus

            # Champion / Runner-up (only for final)
            if gtype == "final":
                if home_goals > away_goals:
                    stats[home_id].knockout_pts += config.CHAMPION_BONUS
                    stats[away_id].knockout_pts += config.RUNNER_UP_BONUS
                elif away_goals > home_goals:
                    stats[away_id].knockout_pts += config.CHAMPION_BONUS
                    stats[home_id].knockout_pts += config.RUNNER_UP_BONUS
                else:
                    # Penalty shootout final
                    pen_winner = _penalty_winner(g)
                    if pen_winner == "home":
                        stats[home_id].knockout_pts += config.CHAMPION_BONUS
                        stats[away_id].knockout_pts += config.RUNNER_UP_BONUS
                    elif pen_winner == "away":
                        stats[away_id].knockout_pts += config.CHAMPION_BONUS
                        stats[home_id].knockout_pts += config.RUNNER_UP_BONUS

    # --- Awards: highest award per team → credited to team owner (keyed by id)
    team_award_pts: dict[str, float] = defaultdict(float)
    for award_key, tid in config.AWARDS.items():
        pts = config.AWARD_PTS.get(award_key, 0.0)
        team_award_pts[tid] = max(team_award_pts[tid], pts)

    # --- Dark Horse (keyed by team id)
    contender_dh_pts: dict[str, float] = defaultdict(float)
    for contender, dh_id in config.DARK_HORSE.items():
        best = 0.0
        for stage, bonus in sorted(_DH_STAGE_BONUS.items(), key=lambda x: x[1], reverse=True):
            if stage in ("r32", "r16") and stats[dh_id].qualified:
                best = max(best, config.DARK_HORSE_BONUS["r16"])
            elif stage == "qf" and stats[dh_id].knockout_pts >= config.QF_BONUS:
                best = max(best, config.DARK_HORSE_BONUS["qf"])
            elif stage == "sf" and stats[dh_id].knockout_pts >= config.QF_BONUS + config.SF_BONUS:
                best = max(best, config.DARK_HORSE_BONUS["sf"])
        contender_dh_pts[contender] = best

    return stats, team_award_pts, contender_dh_pts, warnings, last_match


def build_leaderboard(games: list[dict]) -> tuple[list[dict], list[str], "dict | None"]:
    stats, team_award_pts, contender_dh_pts, warnings, last_match = _build_stats(games)

    leaderboard_rows: list[dict] = []
    for contender, team_ids in config.CONTENDERS.items():
        match_total = goal_total = qualify_total = knockout_total = award_total = 0.0
        matches_total = 0

        for tid in team_ids:
            s = stats[tid]
            match_total += s.match_pts
            goal_total += s.goal_pts
            qualify_total += s.qualify_pts
            knockout_total += s.knockout_pts
            award_total += team_award_pts.get(tid, 0.0)
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

    dh_id = config.DARK_HORSE.get(matched_contender, "")
    dh_pts = contender_dh_pts.get(matched_contender, 0.0)

    team_rows = []
    for tid in config.CONTENDERS[matched_contender]:
        s = stats[tid]
        is_dh = tid == dh_id
        team_dh_pts = dh_pts if is_dh else 0.0
        award_pts = team_award_pts.get(tid, 0.0)
        total = s.match_pts + s.goal_pts + s.qualify_pts + s.knockout_pts + award_pts + team_dh_pts
        team_rows.append({
            "name": display_name_for_id(tid) or tid,
            "tier": _tier(tid),
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
    registry = load_team_registry()

    team_ids = set(config.CONTENDERS[matched_contender])
    dh_id = config.DARK_HORSE.get(matched_contender, "")
    dh_pts = contender_dh_pts.get(matched_contender, 0.0)

    award_events: list[dict] = []
    for tid in team_ids:
        a_pts = team_award_pts.get(tid, 0.0)
        if a_pts > 0:
            award_name = ""
            for award_key, award_tid in config.AWARDS.items():
                if award_tid == tid and config.AWARD_PTS.get(award_key, 0.0) == a_pts:
                    award_name = award_key.replace("_", " ").title()
                    break
            award_events.append({"team": display_name_for_id(tid) or tid, "name": award_name, "pts": a_pts})

    finished = sorted([g for g in games if is_finished(g)], key=_parse_local_date)

    _STAGE_LABEL = {"group": "", "r32": "R32", "r16": "R16", "qf": "QF", "sf": "SF", "final": "Final"}
    team_qualified: dict[str, bool] = {}
    events: list[dict] = []
    running_total = 0.0

    for g in finished:
        gtype = g.get("type", "")
        home_id = g.get("home_team_id", "0")
        away_id = g.get("away_team_id", "0")
        home_raw = g.get("home_team_name_en", "")
        away_raw = g.get("away_team_name_en", "")

        if not is_real_participant(home_id, home_raw) or not is_real_participant(away_id, away_raw):
            continue
        if home_id not in registry or away_id not in registry:
            continue

        home_goals = parse_goals(g.get("home_scorers"), g.get("home_score"))
        away_goals = parse_goals(g.get("away_scorers"), g.get("away_score"))
        game_date = _parse_local_date(g)
        date_str = game_date.strftime("%d %b") if game_date != datetime.min else "?"

        for tid, opp_id, team_goals, opp_goals in (
            (home_id, away_id, home_goals, away_goals),
            (away_id, home_id, away_goals, home_goals),
        ):
            if tid not in team_ids:
                continue

            tier = _tier(tid)
            goal_mult = config.GOAL_MULTIPLIER[tier]

            if team_goals > opp_goals:
                result, match_pts = "W", float(config.WIN_PTS)
            elif team_goals < opp_goals:
                result, match_pts = "L", 0.0
            else:
                # Regular time draw — check for penalty shootout
                pen_winner = _penalty_winner(g)
                if (pen_winner == "home" and tid == home_id) or (pen_winner == "away" and tid == away_id):
                    result, match_pts = "W", float(config.WIN_PTS)
                elif pen_winner is not None:
                    result, match_pts = "L", 0.0
                else:
                    result, match_pts = "D", float(config.DRAW_PTS)

            goal_pts = round(team_goals * goal_mult, 2)

            qualify_pts = 0.0
            if gtype == "r32" and not team_qualified.get(tid, False):
                team_qualified[tid] = True
                qualify_pts = config.QUALIFY_BONUS[tier]

            knockout_pts = champion_pts = runner_up_pts = 0.0
            if gtype in _STAGE_BONUS:
                knockout_pts = _STAGE_BONUS[gtype]
            if gtype == "final":
                if team_goals > opp_goals:
                    champion_pts = float(config.CHAMPION_BONUS)
                elif team_goals < opp_goals:
                    runner_up_pts = float(config.RUNNER_UP_BONUS)
                else:
                    # Penalty shootout final
                    pen_winner = _penalty_winner(g)
                    if (pen_winner == "home" and tid == home_id) or (pen_winner == "away" and tid == away_id):
                        champion_pts = float(config.CHAMPION_BONUS)
                    elif pen_winner is not None:
                        runner_up_pts = float(config.RUNNER_UP_BONUS)

            event_total = round(match_pts + goal_pts + qualify_pts + knockout_pts + champion_pts + runner_up_pts, 2)
            running_total = round(running_total + event_total, 2)

            events.append({
                "date_str": date_str,
                "team": display_name_for_id(tid) or tid,
                "tier": tier,
                "opponent": display_name_for_id(opp_id) or opp_id,
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
    if dh_pts > 0 and dh_id:
        dh_s = stats[dh_id]
        if dh_s.knockout_pts >= config.QF_BONUS + config.SF_BONUS:
            dh_stage = "SF"
        elif dh_s.knockout_pts >= config.QF_BONUS:
            dh_stage = "QF"
        elif dh_s.qualified:
            dh_stage = "R16"
        else:
            dh_stage = "R32"
        dh_info = {"team": display_name_for_id(dh_id) or dh_id, "stage": dh_stage, "pts": dh_pts}

    grand_total = round(running_total + dh_pts + sum(a["pts"] for a in award_events), 2)

    return {
        "user": matched_contender,
        "events": events,
        "match_subtotal": running_total,
        "dark_horse": dh_info,
        "awards": award_events,
        "grand_total": grand_total,
    }


def build_value_report(games: list[dict], leaderboard_rows: "list[dict] | None" = None) -> list[dict]:
    """Returns value-for-money data for all contenders.

    Each item in the returned list contains per-team pts vs auction price,
    sorted internally by pts/M descending. The list is ordered by leaderboard
    rank when leaderboard_rows is provided, otherwise by overall pts/M desc.
    """
    stats, team_award_pts, contender_dh_pts, _, _ = _build_stats(games)

    result = []
    for contender, team_ids in config.CONTENDERS.items():
        prices = config.AUCTION_PRICES.get(contender, {})
        dh_id = config.DARK_HORSE.get(contender, "")
        dh_pts = contender_dh_pts.get(contender, 0.0)

        team_rows = []
        total_pts = 0.0
        total_spent = 0

        for tid in team_ids:
            s = stats[tid]
            award_pts = team_award_pts.get(tid, 0.0)
            pts = round(s.match_pts + s.goal_pts + s.qualify_pts + s.knockout_pts + award_pts, 2)
            price = prices.get(tid, 0)
            pts_per_m = round(pts / price, 3) if price > 0 else 0.0
            total_pts += pts
            total_spent += price
            team_rows.append({
                "id": tid,
                "name": display_name_for_id(tid) or tid,
                "tier": _tier(tid),
                "price": price,
                "pts": pts,
                "pts_per_m": pts_per_m,
                "is_dark_horse": tid == dh_id,
            })

        team_rows.sort(key=lambda r: r["pts_per_m"], reverse=True)
        total_pts = round(total_pts, 2)
        overall_pts_per_m = round(total_pts / total_spent, 3) if total_spent > 0 else 0.0

        result.append({
            "user": contender,
            "total_pts": total_pts,
            "total_spent": total_spent,
            "budget_remaining": config.BUDGETS.get(contender, 0),
            "dh_pts": round(dh_pts, 2),
            "pts_per_m": overall_pts_per_m,
            "teams": team_rows,
        })

    if leaderboard_rows:
        rank_order = {r["user"]: i for i, r in enumerate(leaderboard_rows)}
        result.sort(key=lambda r: rank_order.get(r["user"], 999))
    else:
        result.sort(key=lambda r: r["pts_per_m"], reverse=True)

    return result


def build_team_tier_report(games: list[dict]) -> list[dict]:
    """Returns all owned teams grouped by tier and ranked by fantasy output."""
    stats, team_award_pts, contender_dh_pts, _, _ = _build_stats(games)

    owner_by_team = {
        tid: contender
        for contender, team_ids in config.CONTENDERS.items()
        for tid in team_ids
    }
    dark_horse_by_team = {
        dh_id: contender
        for contender, dh_id in config.DARK_HORSE.items()
    }

    tier_groups: dict[int, list[dict]] = defaultdict(list)
    for tid, owner in owner_by_team.items():
        s = stats[tid]
        tier = _tier(tid)
        award_pts = team_award_pts.get(tid, 0.0)
        base_total = round(s.match_pts + s.goal_pts + s.qualify_pts + s.knockout_pts + award_pts, 2)
        dh_owner = dark_horse_by_team.get(tid)
        dh_pts = contender_dh_pts.get(dh_owner, 0.0) if dh_owner else 0.0

        tier_groups[tier].append({
            "id": tid,
            "name": display_name_for_id(tid) or tid,
            "owner": owner,
            "tier": tier,
            "matches": s.matches,
            "wins": s.wins,
            "draws": s.draws,
            "losses": s.losses,
            "goals_for": s.goals_for,
            "goals_against": s.goals_against,
            "goal_diff": s.goals_for - s.goals_against,
            "match_pts": round(s.match_pts, 2),
            "goal_pts": round(s.goal_pts, 2),
            "qualify_pts": round(s.qualify_pts, 2),
            "knockout_pts": round(s.knockout_pts, 2),
            "award_pts": round(award_pts, 2),
            "total": base_total,
            "is_dark_horse": dh_owner is not None,
            "dark_horse_owner": dh_owner,
            "dark_horse_pts": round(dh_pts, 2),
        })

    result = []
    for tier in sorted(tier_groups):
        teams = tier_groups[tier]
        teams.sort(
            key=lambda r: (
                -r["total"],
                -r["match_pts"],
                -r["goal_diff"],
                -r["goals_for"],
                r["matches"],
                r["name"],
            )
        )

        rank = 1
        for i, row in enumerate(teams):
            if i > 0 and row["total"] < teams[i - 1]["total"]:
                rank = i + 1
            row["rank"] = rank

        result.append({
            "tier": tier,
            "teams": teams,
        })

    return result


_SNAPSHOT_PATH = pathlib.Path(config.RANK_SNAPSHOT_PATH)


def load_rank_snapshot() -> dict[str, int]:
    if not _SNAPSHOT_PATH.exists():
        return {}
    with open(_SNAPSHOT_PATH) as f:
        return json.load(f)


def save_rank_snapshot(rows: list[dict]) -> None:
    snapshot = {row["user"]: row["rank"] for row in rows}
    with open(_SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)

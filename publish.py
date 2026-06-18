"""
Publish the current fantasy leaderboard to the league's WhatsApp group.

Sending goes through a long-lived local daemon (whatsapp_sender/daemon.js) that
holds a warm WhatsApp session, so each publish is a near-instant HTTP POST rather
than a flaky browser cold-start. Start the daemon via launchd (see RUNNING.md) or
manually: `node whatsapp_sender/daemon.js`.

Usage:
    python3 publish.py                       # fetch leaderboard and send to group
    python3 publish.py --dry-run             # print the message without sending
    python3 publish.py --test                # send a timestamped "test" to verify the connection
    python3 publish.py --daemon-status       # check whether the daemon session is ready
    python3 publish.py --find-groups         # list all groups and their JIDs (for config setup)
    python3 publish.py --user <name> [--dry-run] # show per-team breakdown for a specific user
    python3 publish.py --all                 # show ranked progressive timeline for all contenders
"""
import sys
import time
import pathlib
import subprocess
from datetime import datetime

import httpx

import config
from games_client import fetch_games
from scoring import build_leaderboard, build_user_report, load_rank_snapshot, save_rank_snapshot, build_contender_timeline

_FIND_GROUPS = pathlib.Path(__file__).parent / "whatsapp_sender" / "find_groups.js"

# Retry budget for the brief window after a launchd (re)start when the daemon is
# up but its WhatsApp session is still syncing (HTTP 503).
_WARMUP_RETRIES = 5
_WARMUP_DELAY = 3  # seconds between retries


def _rank_delta_prefix(delta: "int | None") -> str:
    if delta is None:
        return "🆕 "
    if delta > 0:
        return f"🟢▲{delta} "
    if delta < 0:
        return f"🔴▼{abs(delta)} "
    return "➡️ "


def format_leaderboard(
    rows: list[dict],
    warnings: list[str],
    last_match: "dict | None",
    snapshot: "dict[str, int] | None" = None,
) -> str:
    lines = ["🏆 *FIFA Fantasy 2026 — Leaderboard* 🏆", ""]
    for row in rows:
        m = row.get("matches", 0)
        match_str = f"{m} {'match' if m == 1 else 'matches'}"
        if snapshot is not None:
            prev = snapshot.get(row["user"])
            delta = (prev - row["rank"]) if prev is not None else None
            prefix = _rank_delta_prefix(delta)
        else:
            prefix = ""
        lines.append(f"{prefix}*{row['user']}* — {row['points']:g} pts ({match_str})")
    lines.append("")
    if last_match:
        home = last_match.get("home_team_name_en", "")
        away = last_match.get("away_team_name_en", "")
        hs = last_match.get("home_score", "?")
        aws = last_match.get("away_score", "?")
        date_raw = last_match.get("local_date", "")
        try:
            date_fmt = datetime.strptime(date_raw, "%m/%d/%Y %H:%M").strftime("%d %b %Y")
        except ValueError:
            date_fmt = date_raw
        lines.append(f"_Data up to: {home} {hs}-{aws} {away} ({date_fmt})_")
    else:
        lines.append(f"_Updated {datetime.now().strftime('%d %b %Y, %I:%M %p')}_")
    if warnings:
        lines.append("")
        lines.append("⚠️ " + "; ".join(warnings))
    return "\n".join(lines)


def format_user_stats(report: dict) -> str:
    lines = [f"📊 *{report['user']} — Team Breakdown*", ""]
    tier_emoji = {"T1": "🔴", "T2": "🟡", "T3": "🟢", "T4": "🔵"}

    for team in report["teams"]:
        name = team["name"]
        tier = f"T{team['tier']}"
        emoji = tier_emoji.get(tier, "⭐")
        is_dh = team["is_dark_horse"]
        total = team["total"]
        matches = team["matches"]
        dh_marker = " ⭐ dark horse" if is_dh else ""

        match_str = f"{matches} {'match' if matches == 1 else 'matches'}"
        lines.append(f"{emoji} *{name}* ({tier}){dh_marker} — {total:g} pts ({match_str})")

        subcats = []
        if team["match_pts"] > 0:
            subcats.append(f"Match: {team['match_pts']:g}")
        if team["goal_pts"] > 0:
            subcats.append(f"Goals: {team['goal_pts']:g}")
        if team["qualify_pts"] > 0:
            subcats.append(f"Qual: {team['qualify_pts']:g}")
        if team["knockout_pts"] > 0:
            subcats.append(f"KO: {team['knockout_pts']:g}")
        if team["award_pts"] > 0:
            subcats.append(f"Awards: {team['award_pts']:g}")
        if team["dh_pts"] > 0:
            subcats.append(f"DH: {team['dh_pts']:g}")

        if subcats:
            lines.append(f"  {' | '.join(subcats)}")

    lines.append("")
    lines.append(f"*Total: {report['grand_total']:g} pts across {len(report['teams'])} teams*")
    return "\n".join(lines)


def format_contender_timeline(timeline: dict) -> str:
    tier_emoji = {1: "🔴", 2: "🟡", 3: "🟢", 4: "🔵"}
    result_emoji = {"W": "✅", "D": "↔️", "L": "❌"}

    lines = []
    for event in timeline["events"]:
        date = event["date_str"]
        team_em = tier_emoji.get(event["tier"], "⭐")
        res_em = result_emoji.get(event["result"], "?")
        opp = event["opponent"]
        stage_tag = f" ({event['stage']})" if event["stage"] else ""

        pts_parts = []
        if event["match_pts"] > 0:
            pts_parts.append(f"Match +{event['match_pts']:g}")
        if event["goal_pts"] > 0:
            pts_parts.append(f"Goals {event['goals']}×{event['goal_mult']} +{event['goal_pts']:g}")
        if event["qualify_pts"] > 0:
            pts_parts.append(f"Qual +{event['qualify_pts']:g}")
        if event["knockout_pts"] > 0:
            pts_parts.append(f"KO +{event['knockout_pts']:g}")
        if event["champion_pts"] > 0:
            pts_parts.append(f"Champ +{event['champion_pts']:g}")
        if event["runner_up_pts"] > 0:
            pts_parts.append(f"Runner-up +{event['runner_up_pts']:g}")

        pts_str = " · ".join(pts_parts)
        lines.append(f"{date}  {team_em} {event['team']:<15} {res_em} {event['result']} vs {opp:<15}{stage_tag}  {pts_str} → {event['cumulative']:g}")

    if timeline["dark_horse"]:
        dh = timeline["dark_horse"]
        lines.append(f"  + Dark Horse ({dh['team']}, {dh['stage']}): +{dh['pts']:g}")

    for award in timeline["awards"]:
        lines.append(f"  + Award ({award['team']}, {award['name']}): +{award['pts']:g}")

    lines.append(f"  ═══ Grand total: {timeline['grand_total']:g} pts")
    return "\n".join(lines)


def format_all_progressive(leaderboard_rows: list[dict], games: list[dict]) -> str:
    divider = "━" * 40
    blocks = [f"🏆 FIFA Fantasy 2026 — Full Breakdown 🏆"]

    for row in leaderboard_rows:
        blocks.append(f"\n{divider}")
        blocks.append(f"#{row['rank']}  {row['user']} — {row['points']:g} pts")
        blocks.append(divider)

        try:
            timeline = build_contender_timeline(games, row["user"])
            blocks.append("\n" + format_contender_timeline(timeline))
        except ValueError as e:
            blocks.append(f"❌ Error: {e}")

    return "\n".join(blocks)


def _daemon_down(exc: Exception) -> None:
    print(f"❌ Can't reach the WhatsApp daemon at {config.WHATSAPP_DAEMON_URL} ({exc}).")
    print("   Start it with launchd:")
    print("     cp com.fifafantasy.whatsappd.plist ~/Library/LaunchAgents/")
    print("     launchctl load ~/Library/LaunchAgents/com.fifafantasy.whatsappd.plist")
    print("   Or run it manually:  node whatsapp_sender/daemon.js")
    sys.exit(1)


def daemon_status() -> None:
    try:
        resp = httpx.get(f"{config.WHATSAPP_DAEMON_URL}/health", timeout=5)
        ready = resp.json().get("ready")
        print("✅ Daemon ready." if ready else "⏳ Daemon up but session not ready yet (still syncing / needs QR scan).")
    except httpx.HTTPError as exc:
        _daemon_down(exc)


def _send(message: str) -> None:
    group_id = config.WHATSAPP_GROUP_ID
    if not group_id or group_id == "PASTE_GROUP_JID_HERE":
        print("ERROR: Set WHATSAPP_GROUP_ID in config.py. Run --find-groups to look it up.")
        sys.exit(1)

    url = f"{config.WHATSAPP_DAEMON_URL}/send"
    payload = {"groupId": group_id, "message": message}

    for attempt in range(1, _WARMUP_RETRIES + 1):
        try:
            resp = httpx.post(url, json=payload, timeout=30)
        except httpx.HTTPError as exc:
            _daemon_down(exc)

        if resp.status_code == 200:
            print(f"✅ Sent to \"{resp.json().get('chat', '')}\".")
            return
        if resp.status_code == 503:
            if attempt < _WARMUP_RETRIES:
                print(f"⏳ Daemon warming up (503); retry {attempt}/{_WARMUP_RETRIES} in {_WARMUP_DELAY}s…")
                time.sleep(_WARMUP_DELAY)
                continue
            print("❌ Daemon never became ready. Check whatsapp_sender/daemon.log (may need a QR scan).")
            sys.exit(1)

        # 4xx/5xx other than 503 — surface the daemon's error and stop.
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        print(f"❌ Send failed (HTTP {resp.status_code}): {detail}")
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]

    if "--find-groups" in args:
        subprocess.run(["node", str(_FIND_GROUPS)], check=True)
        return

    if "--daemon-status" in args:
        daemon_status()
        return

    if "--test" in args:
        print("Sending test message...")
        _send(f"test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return

    games = fetch_games()

    if "--all" in args:
        rows, warnings, _ = build_leaderboard(games)
        print(format_all_progressive(rows, games))
        if warnings:
            print("\n⚠️ " + "; ".join(warnings))
        return

    # Check for --user flag
    user_name = None
    if "--user" in args:
        idx = args.index("--user")
        if idx + 1 < len(args):
            user_name = args[idx + 1]

    if user_name:
        try:
            report = build_user_report(games, user_name)
            message = format_user_stats(report)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        rows, warnings, last_match = build_leaderboard(games)
        snapshot = load_rank_snapshot()
        message = format_leaderboard(rows, warnings, last_match, snapshot=snapshot)

    print(message)
    print()

    if "--dry-run" in args:
        print("[dry-run] Not sending.")
        return

    _send(message)
    if not user_name:
        save_rank_snapshot(rows)


if __name__ == "__main__":
    main()

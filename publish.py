"""
Publish the current fantasy leaderboard to the league's WhatsApp group.

Sending goes through a long-lived local daemon (whatsapp_sender/daemon.js) that
holds a warm WhatsApp session, so each publish is a near-instant HTTP POST rather
than a flaky browser cold-start. Start the daemon via launchd (see RUNNING.md) or
manually: `node whatsapp_sender/daemon.js`.

Usage:
    python3 publish.py                # fetch leaderboard and send to group
    python3 publish.py --dry-run      # print the message without sending
    python3 publish.py --test         # send a timestamped "test" to verify the connection
    python3 publish.py --daemon-status# check whether the daemon session is ready
    python3 publish.py --find-groups  # list all groups and their JIDs (for config setup)
"""
import sys
import time
import pathlib
import subprocess
from datetime import datetime

import httpx

import config
from games_client import fetch_games, parse_goals
from scoring import build_leaderboard

_FIND_GROUPS = pathlib.Path(__file__).parent / "whatsapp_sender" / "find_groups.js"

# Retry budget for the brief window after a launchd (re)start when the daemon is
# up but its WhatsApp session is still syncing (HTTP 503).
_WARMUP_RETRIES = 5
_WARMUP_DELAY = 3  # seconds between retries


def format_leaderboard(rows: list[dict], warnings: list[str], last_match: "dict | None") -> str:
    lines = ["🏆 *FIFA Fantasy 2026 — Leaderboard* 🏆", ""]
    for row in rows:
        m = row.get("matches", 0)
        match_str = f"{m} {'match' if m == 1 else 'matches'}"
        lines.append(f"*{row['user']}* — {row['points']:g} pts ({match_str})")
    lines.append("")
    if last_match:
        home = last_match.get("home_team_name_en", "")
        away = last_match.get("away_team_name_en", "")
        hs = parse_goals(last_match.get("home_scorers"), last_match.get("home_score"))
        aws = parse_goals(last_match.get("away_scorers"), last_match.get("away_score"))
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

    rows, warnings, last_match = build_leaderboard(fetch_games())
    message = format_leaderboard(rows, warnings, last_match)
    print(message)
    print()

    if "--dry-run" in args:
        print("[dry-run] Not sending.")
        return

    _send(message)


if __name__ == "__main__":
    main()

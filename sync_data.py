#!/usr/bin/env python3
"""
Periodic data syncer for FIFA Fantasy.

Fetches match data from the remote API and updates sampresp.json. Silently
swallows failures. Always exits with 0 so launchd never thinks it crashed.

The sync cadence is **time-of-day aware** (all times IST, the Mac's timezone).
Most World Cup matches finish between 22:00 and 11:00 IST, so during that "hot"
window we sync every 30 minutes; the rest of the day we sync every 3 hours.

launchd runs this script every 30 minutes (the finest cadence) via StartInterval,
but each run only actually fetches if the current window's interval has elapsed
since the last attempt (see _should_sync). This keeps cold-window awake ticks at
the 3h cadence instead of hammering the API.

The script also re-arms a macOS pmset wake event at the next desired wake time so
the Mac wakes from sleep to run the next sync (the hot window is overnight in IST,
when the Mac is usually asleep). This requires a NOPASSWD sudoers rule for
/usr/bin/pmset (see RUNNING.md).

Usage:
    python3 sync_data.py

This script is meant to run as a launchd single-shot agent; see
com.fifafantasy.datasync.plist for configuration. Manual invocation is also fine
for testing or debugging.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

import config
from games_client import sync_once

# Hot window (IST, the Mac's timezone): most matches finish between these hours.
# The window wraps past midnight, so "hot" means hour >= START or hour < END.
HOT_START_HOUR = 22
HOT_END_HOUR = 11

HOT_INTERVAL_MIN = 30   # sync cadence inside the match window
COLD_INTERVAL_MIN = 180  # sync cadence the rest of the day (3h)

# Slack so launchd's slightly-early StartInterval ticks don't push the effective
# cadence to the next multiple (e.g. a 29:55 tick shouldn't skip a 30-min slot).
_DUE_SLACK = timedelta(seconds=60)


def _is_hot(now: datetime) -> bool:
    """True if now falls inside the overnight match window (wraps midnight)."""
    return now.hour >= HOT_START_HOUR or now.hour < HOT_END_HOUR


def _interval(now: datetime) -> timedelta:
    return timedelta(minutes=HOT_INTERVAL_MIN if _is_hot(now) else COLD_INTERVAL_MIN)


def _next_wake_time(now: datetime) -> datetime:
    """When to wake the Mac for the next sync.

    Inside the hot window: one interval out. Outside it: the sooner of one cold
    interval out or the next hot-window start, so a long cold gap doesn't make us
    miss the beginning of the match window.
    """
    if _is_hot(now):
        return now + _interval(now)

    cold = now + timedelta(minutes=COLD_INTERVAL_MIN)
    hot_start = now.replace(hour=HOT_START_HOUR, minute=0, second=0, microsecond=0)
    if hot_start <= now:
        hot_start += timedelta(days=1)
    return min(cold, hot_start)


def _read_last_attempt() -> "datetime | None":
    if not os.path.exists(config.SYNC_STATUS_PATH):
        return None
    try:
        with open(config.SYNC_STATUS_PATH, encoding="utf-8") as f:
            ts = json.load(f).get("last_attempt")
        return datetime.fromisoformat(ts) if ts else None
    except (ValueError, OSError):
        return None


def _should_sync(now: datetime, last_attempt: "datetime | None") -> bool:
    """Gate an actual fetch to the current window's cadence."""
    if last_attempt is None:
        return True
    return (now - last_attempt) >= (_interval(now) - _DUE_SLACK)


def _schedule_next_wake(when: datetime) -> None:
    """Re-arm a pmset one-off wake event at the given time.

    Clears the previous one-off event first so wakes don't accumulate. Uses
    `sudo -n` (non-interactive) so it never hangs; a missing sudoers rule just
    logs a warning and the sync continues normally.

    pmset format: MM/dd/yy HH:mm:ss
    """
    when_str = when.strftime("%m/%d/%y %H:%M:%S")

    try:
        # Clear any existing one-off wakeorpoweron events we previously scheduled.
        # schedule cancelall only cancels one-off events, not the static `repeat`
        # backstop, so the daily fallback wake is preserved.
        subprocess.run(
            ["sudo", "-n", "pmset", "schedule", "cancelall"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["sudo", "-n", "pmset", "schedule", "wakeorpoweron", when_str],
            check=True,
            capture_output=True,
            timeout=10,
        )
        print(f"⏰ Next wake scheduled for {when_str}.")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode().strip() if e.stderr else str(e)
        print(f"⚠️  Could not schedule wake (pmset): {stderr}")
        print("   Run the NOPASSWD sudoers setup in RUNNING.md to enable overnight syncing.")
    except Exception as e:
        print(f"⚠️  Could not schedule wake: {e}")


def main() -> None:
    now = datetime.now()
    window = "hot" if _is_hot(now) else "cold"

    if _should_sync(now, _read_last_attempt()):
        success = sync_once(retries=3, delay=5)
        if success:
            print(f"✅ Sync succeeded ({window} window).")
        else:
            print(f"⚠️  Sync failed (will retry next interval, {window} window).")
    else:
        mins = HOT_INTERVAL_MIN if _is_hot(now) else COLD_INTERVAL_MIN
        print(f"⏭️  Skipping — within the {mins}-min {window}-window cadence.")

    # Re-arm the next wake regardless of whether we synced so the chain continues
    # even on a bad API day or a skipped tick.
    _schedule_next_wake(_next_wake_time(now))

    # Always exit 0 so launchd doesn't think we crashed.
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Periodic data syncer for FIFA Fantasy.

Fetches match data from the remote API every N hours (via launchd StartInterval)
and updates sampresp.json. Silently swallows failures. Always exits with 0 so
launchd never thinks it crashed.

Also re-arms a macOS pmset wake event ~3h out so the Mac wakes from sleep to run
the next sync. Requires a NOPASSWD sudoers rule for /usr/bin/pmset (see RUNNING.md).

Usage:
    python3 sync_data.py

This script is meant to run as a launchd single-shot agent; see
com.fifafantasy.datasync.plist for configuration. Manual invocation is also fine
for testing or debugging.
"""
import subprocess
import sys
from datetime import datetime, timedelta

from games_client import sync_once

_WAKE_INTERVAL_HOURS = 3


def _schedule_next_wake(hours: int = _WAKE_INTERVAL_HOURS) -> None:
    """Re-arm a pmset one-off wake event at now+hours.

    Clears the previous one-off event first so wakes don't accumulate. Uses
    `sudo -n` (non-interactive) so it never hangs; a missing sudoers rule just
    logs a warning and the sync continues normally.

    pmset format: MM/dd/yy HH:mm:ss
    """
    when = datetime.now() + timedelta(hours=hours)
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
    success = sync_once(retries=3, delay=5)
    if success:
        print("✅ Sync succeeded.")
    else:
        print("⚠️  Sync failed (will retry next interval).")

    # Re-arm the next wake regardless of sync success so the chain continues
    # even on a bad API day.
    _schedule_next_wake()

    # Always exit 0 so launchd doesn't think we crashed.
    sys.exit(0)


if __name__ == "__main__":
    main()

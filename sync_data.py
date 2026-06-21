#!/usr/bin/env python3
"""
Periodic data syncer for FIFA Fantasy.

Fetches match data from the remote API every N hours (via launchd StartInterval)
and updates sampresp.json. Silently swallows failures. Always exits with 0 so
launchd never thinks it crashed.

Usage:
    python3 sync_data.py

This script is meant to run as a launchd single-shot agent; see
com.fifafantasy.datasync.plist for configuration. Manual invocation is also fine
for testing or debugging.
"""
import sys
from games_client import sync_once


def main() -> None:
    success = sync_once(retries=3, delay=5)
    if success:
        print("✅ Sync succeeded.")
    else:
        print("⚠️  Sync failed (will retry next interval).")
    # Always exit 0 so launchd doesn't think we crashed.
    sys.exit(0)


if __name__ == "__main__":
    main()

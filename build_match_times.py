"""
One-time script: fetches the WC2026 schedule from ESPN's public API and
writes match_times.json with accurate kickoff times in IST (+05:30).

Run once (or re-run to refresh):
    python build_match_times.py

The output file is committed to the repo and used by games_client.py to
override the inaccurate local_date values returned by worldcup26.ir.
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone

import httpx

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
IST = timezone(timedelta(hours=5, minutes=30))
TOURNAMENT_START = date(2026, 6, 11)
TOURNAMENT_END = date(2026, 7, 19)
OUTPUT_PATH = "/Users/shishirmathur/Downloads/fifa_fantasy/match_times.json"

# ESPN team name → name used in sampresp.json (home_team_name_en / away_team_name_en)
ESPN_TO_SAMPRESP: dict[str, str] = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "Democratic Republic of the Congo",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
}


def _espn_name(raw: str) -> str:
    return ESPN_TO_SAMPRESP.get(raw, raw)


def fetch_all_matches() -> list[dict]:
    games = []
    d = TOURNAMENT_START
    while d <= TOURNAMENT_END:
        try:
            resp = httpx.get(
                ESPN_SCOREBOARD,
                params={"dates": d.strftime("%Y%m%d")},
                headers={"User-Agent": "Mozilla/5.0 (compatible; FIFAFantasyBot/1.0)"},
                timeout=15,
            )
            resp.raise_for_status()
            events = resp.json().get("events", [])
            for event in events:
                competition = (event.get("competitions") or [{}])[0]
                utc_str = event.get("date", "")
                if not utc_str:
                    continue
                utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
                ist_dt = utc_dt.astimezone(IST)
                local_date_ist = ist_dt.strftime("%m/%d/%Y %H:%M")

                competitors = competition.get("competitors", [])
                home_name = away_name = ""
                for c in competitors:
                    name = _espn_name(c.get("team", {}).get("displayName", ""))
                    if c.get("homeAway") == "home":
                        home_name = name
                    else:
                        away_name = name

                # Skip placeholder/TBD entries (e.g. "Group A Winner")
                if not home_name or not away_name:
                    continue
                if "winner" in home_name.lower() or "winner" in away_name.lower():
                    continue
                if "place" in home_name.lower() or "place" in away_name.lower():
                    continue
                if "loser" in home_name.lower() or "loser" in away_name.lower():
                    continue

                games.append({
                    "home": home_name,
                    "away": away_name,
                    "local_date_ist": local_date_ist,
                })
        except Exception as exc:
            print(f"  Warning: failed for {d}: {exc}", file=sys.stderr)
        d += timedelta(days=1)
    return games


def main() -> None:
    print("Fetching WC2026 schedule from ESPN…")
    games = fetch_all_matches()
    games.sort(key=lambda g: g["local_date_ist"])
    out = {"games": games}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(games)} matches to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

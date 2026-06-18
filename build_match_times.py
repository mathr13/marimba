"""
One-time script: fetches the WC2026 schedule from ESPN's public API and
writes match_times.json with accurate kickoff times in IST (+05:30).

Run once (or re-run to refresh):
    python build_match_times.py

The output file is committed to the repo and used by games_client.py to
override the inaccurate local_date values returned by worldcup26.ir.
Each entry includes home_id/away_id (from teams.json) so the overlay
join is fully id-based and name-independent.
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
TEAMS_PATH = "/Users/shishirmathur/Downloads/fifa_fantasy/teams.json"

# ESPN team name → name_en in teams.json (for id resolution at generation time only)
ESPN_TO_REGISTRY: dict[str, str] = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "Democratic Republic of the Congo",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
}


def _load_name_to_id() -> dict[str, str]:
    """Build lowercase name_en -> id map from the teams registry."""
    registry = json.load(open(TEAMS_PATH, encoding="utf-8"))
    return {t["name_en"].lower(): t["id"] for t in registry.values()}


def _resolve_id(name: str, name_to_id: dict[str, str]) -> "str | None":
    normalized = ESPN_TO_REGISTRY.get(name, name)
    return name_to_id.get(normalized.lower())


def fetch_all_matches() -> list[dict]:
    name_to_id = _load_name_to_id()
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
                    name = c.get("team", {}).get("displayName", "")
                    if c.get("homeAway") == "home":
                        home_name = name
                    else:
                        away_name = name

                # Skip placeholder/TBD entries (e.g. "Group A Winner")
                if not home_name or not away_name:
                    continue
                if any(kw in n.lower() for n in (home_name, away_name) for kw in ("winner", "loser", "place")):
                    continue

                home_id = _resolve_id(home_name, name_to_id)
                away_id = _resolve_id(away_name, name_to_id)
                if home_id is None or away_id is None:
                    print(f"  Warning: unresolved id for '{home_name}' or '{away_name}'", file=sys.stderr)
                    continue

                games.append({
                    "home": ESPN_TO_REGISTRY.get(home_name, home_name),
                    "away": ESPN_TO_REGISTRY.get(away_name, away_name),
                    "home_id": home_id,
                    "away_id": away_id,
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

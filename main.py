from fastapi import FastAPI, HTTPException

from games_client import fetch_games
from scoring import build_leaderboard, load_rank_snapshot

app = FastAPI(title="FIFA Fantasy API")


@app.get("/hello")
def hello_world():
    return {"message": "Hello, World!"}


@app.get("/leaderboard")
def leaderboard():
    try:
        games = fetch_games()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch games: {exc}")

    rows, warnings, last_match = build_leaderboard(games)
    snapshot = load_rank_snapshot()
    for row in rows:
        prev = snapshot.get(row["user"])
        row["rank_delta"] = (prev - row["rank"]) if prev is not None else None
    last_match_summary = None
    if last_match:
        last_match_summary = {
            "date": last_match.get("local_date"),
            "home": last_match.get("home_team_name_en"),
            "away": last_match.get("away_team_name_en"),
            "score": f"{last_match.get('home_score')}-{last_match.get('away_score')}",
            "type": last_match.get("type"),
        }
    return {"leaderboard": rows, "warnings": warnings, "last_match": last_match_summary}

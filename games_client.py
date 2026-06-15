import re
from datetime import datetime
from typing import Optional
import httpx
from config import TEAM_ALIASES

GAMES_URL = "https://worldcup26.ir/get/games"
_PLACEHOLDER_RE = re.compile(r"^(winner|loser|runner)", re.IGNORECASE)


def normalize_name(raw: str) -> str:
    """Return canonical team name used as key in TEAM_TIERS."""
    cleaned = raw.strip().lower()
    if cleaned in TEAM_ALIASES:
        return TEAM_ALIASES[cleaned]
    # Title-case fallback — preserves original if no alias matches
    return raw.strip()


def is_real_participant(team_id: str, name: str) -> bool:
    return team_id != "0" and not _PLACEHOLDER_RE.match(name or "")


def is_finished(game: dict) -> bool:
    return game.get("finished", "").upper() == "TRUE" or game.get("time_elapsed", "") == "finished"


def parse_goals(scorers: Optional[str], score: Optional[str]) -> int:
    """
    Count goals from the scorers string (excludes penalty-shootout goals).
    Falls back to the raw score field when scorers is absent/null.
    """
    if scorers and scorers.strip().lower() not in ("null", "", "{}"):
        # Format: {"Player1 9'","Player2 67'"} — count comma-separated entries inside braces
        inner = scorers.strip()
        if inner.startswith("{") and inner.endswith("}"):
            inner = inner[1:-1]
        if inner.strip():
            return len([e for e in inner.split(",") if e.strip()])
    try:
        return int(score or 0)
    except ValueError:
        return 0


def _sort_games(games: list[dict]) -> list[dict]:
    def _key(g: dict) -> tuple:
        finished = 0 if is_finished(g) else 1
        try:
            date = datetime.strptime(g.get("local_date", ""), "%m/%d/%Y %H:%M")
        except ValueError:
            date = datetime.min
        return (finished, date)
    return sorted(games, key=_key)


def fetch_games() -> list[dict]:
    import config
    if config.DATA_SOURCE == "local":
        return _sort_games(_load_local(config.LOCAL_JSON_PATH))
    return _sort_games(_fetch_api())


def _load_local(path: str) -> list[dict]:
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "games" in data:
        return data["games"]
    return data


def _fetch_api() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FIFAFantasyBot/1.0)"}
    resp = httpx.get(GAMES_URL, timeout=15, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "games" in data:
        return data["games"]
    return data

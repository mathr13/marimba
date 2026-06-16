import json
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


def _overlay_match_times(games: list[dict]) -> list[dict]:
    """Replace local_date with accurate IST kickoff from match_times.json."""
    import os
    import config
    path = config.MATCH_TIMES_PATH
    if not os.path.exists(path):
        return games
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    overlay = {
        (entry["home"].lower(), entry["away"].lower()): entry["local_date_ist"]
        for entry in data.get("games", [])
    }
    for game in games:
        key = (
            game.get("home_team_name_en", "").lower(),
            game.get("away_team_name_en", "").lower(),
        )
        if key in overlay:
            game["local_date"] = overlay[key]
    return games


def fetch_games() -> list[dict]:
    import config
    if config.DATA_SOURCE == "local":
        games = _sort_games(_load_local(config.LOCAL_JSON_PATH))
    else:
        games = _sort_games(_fetch_api())
    return _overlay_match_times(games)


def _load_local(path: str) -> list[dict]:
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "games" in data:
        return data["games"]
    return data


def _fetch_api() -> list[dict]:
    import config
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FIFAFantasyBot/1.0)"}
    resp = httpx.get(GAMES_URL, timeout=15, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    new_games = data["games"] if isinstance(data, dict) and "games" in data else data
    try:
        old_games = _load_local(config.LOCAL_JSON_PATH)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        old_games = []
    with open(config.LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _auto_commit_cache(old_games, new_games)
    return new_games


def refresh_local_cache() -> None:
    import subprocess
    import config
    result = subprocess.run(
        ["curl", "-sf", "-A", "Mozilla/5.0 (compatible; FIFAFantasyBot/1.0)", GAMES_URL],
        capture_output=True,
        timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed (exit {result.returncode}): {result.stderr.decode()}")
    data = json.loads(result.stdout)
    new_games = data["games"] if isinstance(data, dict) and "games" in data else data
    try:
        old_games = _load_local(config.LOCAL_JSON_PATH)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        old_games = []
    with open(config.LOCAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _auto_commit_cache(old_games, new_games)
    print(f"Updated {config.LOCAL_JSON_PATH} with {len(new_games)} games.")


def _auto_commit_cache(old_games: list[dict], new_games: list[dict]) -> None:
    import os
    import subprocess
    import config

    old_by_id = {g.get("id"): g for g in old_games}
    new_by_id = {g.get("id"): g for g in new_games}

    lines = []

    if not old_games:
        lines.append(f"Initial cache: {len(new_games)} games")
    else:
        newly_finished = [
            g for gid, g in new_by_id.items()
            if is_finished(g) and not is_finished(old_by_id.get(gid, {}))
        ]
        if newly_finished:
            lines.append("Newly finished:")
            for g in newly_finished:
                home = g.get("home_team_name_en", "?")
                away = g.get("away_team_name_en", "?")
                hs = g.get("home_score", "?")
                aws = g.get("away_score", "?")
                date = g.get("local_date", "")[:10]
                lines.append(f"  {home} {hs}-{aws} {away} ({date})")

        new_ids = set(new_by_id) - set(old_by_id)
        if new_ids:
            lines.append(f"New fixtures added: {len(new_ids)}")
            for gid in sorted(new_ids):
                g = new_by_id[gid]
                home = g.get("home_team_name_en", "?")
                away = g.get("away_team_name_en", "?")
                date = g.get("local_date", "")[:10]
                lines.append(f"  {home} vs {away} ({date})")

    if not lines:
        return

    msg = (
        "Update sampresp.json from live API\n\n"
        + "\n".join(lines)
        + "\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    )
    repo_dir = os.path.dirname(os.path.abspath(config.LOCAL_JSON_PATH))
    try:
        subprocess.run(["git", "add", config.LOCAL_JSON_PATH], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass


if __name__ == "__main__":
    refresh_local_cache()

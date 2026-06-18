import json
import re
from datetime import datetime
from typing import Optional
import httpx

GAMES_URL = "https://worldcup26.ir/get/games"
_PLACEHOLDER_RE = re.compile(r"^(winner|loser|runner)", re.IGNORECASE)

_TEAM_REGISTRY: "dict[str, dict] | None" = None


def load_team_registry() -> dict[str, dict]:
    """Load id-keyed team registry from teams.json (id -> team record), cached."""
    global _TEAM_REGISTRY
    if _TEAM_REGISTRY is None:
        import config
        with open(config.TEAMS_JSON_PATH, encoding="utf-8") as f:
            _TEAM_REGISTRY = json.load(f)
    return _TEAM_REGISTRY


def display_name_for_id(team_id: str) -> "str | None":
    """Human-readable team name for display. Prefers TEAM_DISPLAY_OVERRIDES, else registry name_en."""
    import config
    if team_id in config.TEAM_DISPLAY_OVERRIDES:
        return config.TEAM_DISPLAY_OVERRIDES[team_id]
    t = load_team_registry().get(team_id)
    return t["name_en"] if t else None


def is_real_participant(team_id: str, name: str) -> bool:
    return team_id != "0" and not _PLACEHOLDER_RE.match(name or "")


def is_finished(game: dict) -> bool:
    return game.get("finished", "").upper() == "TRUE" or game.get("time_elapsed", "") == "finished"


def parse_goals(scorers: Optional[str], score: Optional[str]) -> int:
    """
    Count goals for fantasy scoring. Prefers the scorers string (excludes
    penalty-shootout goals) but falls back to the raw score when the scorers
    string is absent, null, or incomplete (fewer entries than the reported score).
    """
    raw = 0
    try:
        raw = int(score or 0)
    except ValueError:
        pass

    if scorers and scorers.strip().lower() not in ("null", "", "{}"):
        inner = scorers.strip()
        if inner.startswith("{") and inner.endswith("}"):
            inner = inner[1:-1]
        if inner.strip():
            count = len([e for e in inner.split(",") if e.strip()])
            # If scorers list has fewer goals than the score field, the API is
            # missing scorer entries — trust the authoritative score instead.
            return max(count, raw)

    return raw


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
    """Replace local_date with accurate IST kickoff from match_times.json (joined by team ids)."""
    import os
    import config
    path = config.MATCH_TIMES_PATH
    if not os.path.exists(path):
        return games
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    overlay = {
        (entry["home_id"], entry["away_id"]): entry["local_date_ist"]
        for entry in data.get("games", [])
        if entry.get("home_id") and entry.get("away_id")
    }
    for game in games:
        key = (game.get("home_team_id", ""), game.get("away_team_id", ""))
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
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
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
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
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
    except subprocess.CalledProcessError as e:
        print(f"⚠️  git auto-commit failed: {e.stderr.decode().strip() if e.stderr else e}")


if __name__ == "__main__":
    refresh_local_cache()

# ---------------------------------------------------------------------------
# Contenders and their team rosters
# ---------------------------------------------------------------------------
CONTENDERS: dict[str, list[str]] = {
    "Shishir": ["Germany", "Netherlands", "United States", "Australia", "Curaçao", "Czech Republic (Czechia)"],
    "Tushar": ["Brazil", "Mexico", "Colombia", "Iran", "Ivory Coast", "Scotland", "Sweden", "New Zealand"],
    "Shivansh": ["Belgium", "Spain", "Ecuador", "Algeria", "Qatar", "Tunisia", "Ghana", "Jordan"],
    "Ghanghas": ["Austria", "Croatia", "Morocco", "Switzerland", "Uruguay", "Turkey (Türkiye)"],
    "Ojus": ["Argentina", "Japan", "South Korea", "Paraguay", "Uzbekistan", "Haiti"],
    "Nikhil": ["England", "Portugal", "Senegal", "Saudi Arabia", "Bosnia and Herzegovina", "Cape Verde", "Iraq"],
    "Ashwini": ["Canada", "France", "Egypt", "Norway", "Panama", "DR Congo", "South Africa"],
}

# ---------------------------------------------------------------------------
# Team tiers (edit these if the tier list changes)
# ---------------------------------------------------------------------------
TEAM_TIERS: dict[str, int] = {
    # Tier 1
    "Argentina": 1, "France": 1, "Spain": 1, "England": 1, "Brazil": 1,
    "Portugal": 1, "Netherlands": 1, "Belgium": 1, "Germany": 1,
    "United States": 1, "Mexico": 1, "Canada": 1,
    # Tier 2
    "Croatia": 2, "Morocco": 2, "Colombia": 2, "Uruguay": 2, "Switzerland": 2,
    "Japan": 2, "Senegal": 2, "Iran": 2, "South Korea": 2, "Ecuador": 2,
    "Austria": 2, "Australia": 2,
    # Tier 3
    "Norway": 3, "Egypt": 3, "Algeria": 3, "Scotland": 3, "Ivory Coast": 3,
    "Tunisia": 3, "Paraguay": 3, "Panama": 3, "Sweden": 3, "Uzbekistan": 3,
    "Qatar": 3, "Saudi Arabia": 3,
    # Tier 4
    "Ghana": 4, "South Africa": 4, "Jordan": 4, "Cape Verde": 4, "Curaçao": 4,
    "Haiti": 4, "New Zealand": 4, "Czechia": 4, "Bosnia and Herzegovina": 4,
    "Türkiye": 4, "Iraq": 4, "DR Congo": 4,
}

# ---------------------------------------------------------------------------
# Name aliases: roster name / API name variants → canonical TEAM_TIERS key
# ---------------------------------------------------------------------------
TEAM_ALIASES: dict[str, str] = {
    # Roster variants
    "czech republic (czechia)": "Czechia",
    "czechia": "Czechia",
    "czech republic": "Czechia",
    "turkey (türkiye)": "Türkiye",
    "turkey": "Türkiye",
    "türkiye": "Türkiye",
    "ivory coast": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "dr congo": "DR Congo",
    "congo dr": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "democratic republic of the congo": "DR Congo",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "korea dpr": "South Korea",  # unlikely but safe
    "united states": "United States",
    "usa": "United States",
    "curaçao": "Curaçao",
    "curacao": "Curaçao",
}

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
# "local"  → read from LOCAL_JSON_PATH (default, avoids hitting the live API)
# "api"    → fetch live from https://worldcup26.ir/get/games
DATA_SOURCE: str = "local"
LOCAL_JSON_PATH: str = "/Users/shishirmathur/Downloads/fifa_fantasy/sampresp.json"
MATCH_TIMES_PATH: str = "/Users/shishirmathur/Downloads/fifa_fantasy/match_times.json"

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
WIN_PTS = 2
DRAW_PTS = 1

GOAL_MULTIPLIER: dict[int, float] = {1: 1.0, 2: 1.5, 3: 2.0, 4: 3.0}

# Group-stage qualification bonus (reaching knockouts / R32)
QUALIFY_BONUS: dict[int, float] = {1: 2.0, 2: 2.0, 3: 2.0, 4: 5.0}

# Knockout progression bonuses (cumulative)
QF_BONUS = 2.0
SF_BONUS = 2.0
FINAL_BONUS = 2.0
CHAMPION_BONUS = 10.0
RUNNER_UP_BONUS = 5.0

# Dark Horse bonuses (only highest applies)
DARK_HORSE_BONUS: dict[str, float] = {"r16": 1.0, "qf": 3.0, "sf": 5.0}

# Award points
AWARD_PTS: dict[str, float] = {
    "golden_ball": 5.0,
    "golden_boot": 5.0,
    "golden_glove": 4.0,
    "best_young_player": 4.0,
    "fair_play": 3.0,
}

# ---------------------------------------------------------------------------
# Optional manual inputs (leave empty to disable)
# ---------------------------------------------------------------------------

# Map award key → team name (canonical). Only highest per team counts.
# Example: AWARDS = {"golden_ball": "Argentina", "golden_boot": "France"}
AWARDS: dict[str, str] = {}

# Map contender name → their Dark Horse team (must be Tier 3 or 4).
# Example: DARK_HORSE = {"Ojus": "Haiti", "Nikhil": "Cape Verde"}
DARK_HORSE: dict[str, str] = {
    "Ojus": "Paraguay",
    "Ashwini": "Norway",
    "Shivansh": "Algeria",
    "Ghanghas": "Türkiye",
    "Shishir": "Czechia",
    "Nikhil": "Bosnia and Herzegovina",
    "Tushar": "Sweden",
}

# ---------------------------------------------------------------------------
# WhatsApp publishing
# ---------------------------------------------------------------------------
# Internal group JID — the "120363...@g.us" id shown in the group debug logs.
# This lets send_group.js use getChatById() (instant) instead of getChats()
# (slow with many groups). To find it: run publish.py --find-groups
WHATSAPP_GROUP_ID: str = "918428058576-1528206449@g.us"

# Local daemon that holds a warm WhatsApp session (see whatsapp_sender/daemon.js).
# publish.py POSTs the message here instead of cold-starting Node on every send.
WHATSAPP_DAEMON_URL: str = "http://127.0.0.1:8765"

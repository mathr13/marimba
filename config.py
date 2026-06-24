# ---------------------------------------------------------------------------
# Contenders and their team rosters (team ids from teams.json)
# ---------------------------------------------------------------------------
CONTENDERS: dict[str, list[str]] = {
    "Shishir":  ["17", "21", "13", "15", "18", "4"],   # Germany, Netherlands, USA, Australia, Curaçao, Czechia
    "Tushar":   ["9", "1", "44", "27", "19", "12", "23", "28"],  # Brazil, Mexico, Colombia, Iran, Ivory Coast, Scotland, Sweden, New Zealand
    "Shivansh": ["25", "29", "20", "38", "7", "24", "47", "40"],  # Belgium, Spain, Ecuador, Algeria, Qatar, Tunisia, Ghana, Jordan
    "Ghanghas": ["39", "46", "10", "8", "32", "16"],   # Austria, Croatia, Morocco, Switzerland, Uruguay, Türkiye
    "Ojus":     ["37", "22", "3", "14", "43", "11"],   # Argentina, Japan, South Korea, Paraguay, Uzbekistan, Haiti
    "Nikhil":   ["45", "41", "34", "31", "6", "30", "35"],  # England, Portugal, Senegal, Saudi Arabia, Bosnia and Herzegovina, Cape Verde, Iraq
    "Ashwini":  ["5", "33", "26", "36", "48", "42", "2"],  # Canada, France, Egypt, Norway, Panama, DR Congo, South Africa
}

# ---------------------------------------------------------------------------
# Team tiers (team id → tier). All 48 WC2026 teams.
# ---------------------------------------------------------------------------
TEAM_TIERS: dict[str, int] = {
    # Tier 1
    "37": 1,  # Argentina
    "33": 1,  # France
    "29": 1,  # Spain
    "45": 1,  # England
    "9":  1,  # Brazil
    "41": 1,  # Portugal
    "21": 1,  # Netherlands
    "25": 1,  # Belgium
    "17": 1,  # Germany
    "13": 1,  # United States
    "1":  1,  # Mexico
    "5":  1,  # Canada
    # Tier 2
    "46": 2,  # Croatia
    "10": 2,  # Morocco
    "44": 2,  # Colombia
    "32": 2,  # Uruguay
    "8":  2,  # Switzerland
    "22": 2,  # Japan
    "34": 2,  # Senegal
    "27": 2,  # Iran
    "3":  2,  # South Korea
    "20": 2,  # Ecuador
    "39": 2,  # Austria
    "15": 2,  # Australia
    # Tier 3
    "36": 3,  # Norway
    "26": 3,  # Egypt
    "38": 3,  # Algeria
    "12": 3,  # Scotland
    "19": 3,  # Ivory Coast
    "24": 3,  # Tunisia
    "14": 3,  # Paraguay
    "48": 3,  # Panama
    "23": 3,  # Sweden
    "43": 3,  # Uzbekistan
    "7":  3,  # Qatar
    "31": 3,  # Saudi Arabia
    # Tier 4
    "47": 4,  # Ghana
    "2":  4,  # South Africa
    "40": 4,  # Jordan
    "30": 4,  # Cape Verde
    "18": 4,  # Curaçao
    "11": 4,  # Haiti
    "28": 4,  # New Zealand
    "4":  4,  # Czechia
    "6":  4,  # Bosnia and Herzegovina
    "16": 4,  # Türkiye
    "35": 4,  # Iraq
    "42": 4,  # DR Congo
}

# ---------------------------------------------------------------------------
# Short display names for teams whose registry name_en differs from preferred
# All others use name_en from teams.json directly.
# ---------------------------------------------------------------------------
TEAM_DISPLAY_OVERRIDES: dict[str, str] = {
    "4":  "Czechia",    # registry: "Czech Republic"
    "16": "Türkiye",    # registry: "Turkey"
    "42": "DR Congo",   # registry: "Democratic Republic of the Congo"
}

# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------
# "local"  → read from LOCAL_JSON_PATH (default, avoids hitting the live API)
# "api"    → fetch live from https://worldcup26.ir/get/games
DATA_SOURCE: str = "local"
LOCAL_JSON_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/sampresp.json"
MATCH_TIMES_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/match_times.json"
TEAMS_JSON_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/teams.json"
RANK_SNAPSHOT_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/rank_snapshot.json"
SYNC_STATUS_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/sync_status.json"
SYNC_LOG_PATH: str = "/Users/shishirmathur/TProjects/fifa_fantasy/sync_log.jsonl"

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

# Map award key → team id. Only highest per team counts.
# Example: AWARDS = {"golden_ball": "37", "golden_boot": "33"}   # 37=Argentina, 33=France
AWARDS: dict[str, str] = {}

# Map contender name → their Dark Horse team id (must be Tier 3 or 4).
DARK_HORSE: dict[str, str] = {
    "Ojus":     "14",   # Paraguay
    "Ashwini":  "36",   # Norway
    "Shivansh": "38",   # Algeria
    "Ghanghas": "16",   # Türkiye
    "Shishir":  "4",    # Czechia
    "Nikhil":   "6",    # Bosnia and Herzegovina
    "Tushar":   "23",   # Sweden
}

# ---------------------------------------------------------------------------
# Auction data
# ---------------------------------------------------------------------------

# Remaining budget per contender after the auction (M)
BUDGETS: dict[str, int] = {
    "Ashwini":  5,
    "Tushar":   24,
    "Ojus":     15,
    "Ghanghas": 53,
    "Shishir":  0,
    "Shivansh": 2,
    "Nikhil":   11,
}

# Price paid at auction per team (M), indexed contender → {team_id → price}
AUCTION_PRICES: dict[str, dict[str, int]] = {
    "Ashwini":  {"5": 30, "33": 75, "26": 35, "36": 32, "48": 13, "42": 5,  "2": 5},
    "Tushar":   {"9": 40, "1":  30, "44": 30, "27": 20, "19": 12, "12": 11, "23": 26, "28": 7},
    "Ojus":     {"37": 85, "22": 38, "3":  22, "14": 28, "43": 11, "11": 1},
    "Ghanghas": {"39": 22, "46": 33, "10": 32, "8":  30, "32": 29, "16": 1},
    "Shishir":  {"17": 70, "21": 40, "13": 25, "15": 25, "18": 5,  "4":  35},
    "Shivansh": {"25": 45, "29": 65, "20": 18, "38": 30, "7":  5,  "24": 5,  "47": 25, "40": 5},
    "Nikhil":   {"45": 55, "41": 75, "34": 22, "31": 16, "6":  11, "30": 5,  "35": 5},
}

# ---------------------------------------------------------------------------
# WhatsApp publishing
# ---------------------------------------------------------------------------
# Internal group JID — the "120363...@g.us" id shown in the group debug logs.
# This lets send_group.js use getChatById() (instant) instead of getChats()
# (slow with many groups). To find it: run publish.py --find-groups
WHATSAPP_GROUP_ID: str = "918428058576-1528206449@g.us"
# prod -> 918428058576-1528206449@g.us
# test -> 120363029166681370@g.us

# Local daemon that holds a warm WhatsApp session (see whatsapp_sender/daemon.js).
# publish.py POSTs the message here instead of cold-starting Node on every send.
WHATSAPP_DAEMON_URL: str = "http://127.0.0.1:8765"

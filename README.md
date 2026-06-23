# FIFA Fantasy 2026

Tracks the FIFA World Cup 2026 and sends a live fantasy leaderboard to a WhatsApp group. Each player in the league owns a set of national teams; points are awarded for wins, goals scored, knockout progression, and dark horse runs.

---

## How it works

```
worldcup26.ir API
       │
       ▼
 games_client.py  ──── fetches & sorts finished matches
       │
       ▼
   scoring.py     ──── calculates fantasy points per team, aggregates per contender
       │
       ▼
   publish.py     ──── formats leaderboard, POSTs to WhatsApp daemon
       │
       ▼
 daemon.js        ──── persistent headless WhatsApp session (whatsapp-web.js)
       │
       ▼
  WhatsApp group
```

### Components

| File | Role |
|------|------|
| `config.py` | All settings: player rosters, team tiers, scoring constants, dark horse picks, WhatsApp config — everything is keyed by **team id** (see [Team identity](#team-identity)) |
| `teams.json` | Authoritative team registry — an id-keyed map (`{ "17": { "name_en": "Germany", … } }`) of all 48 World Cup teams |
| `games_client.py` | Fetches match data from the API (or a local JSON file); sorts games — finished first, then chronological; matches games to teams by id |
| `scoring.py` | Calculates points and builds the ranked leaderboard, per-user breakdowns, progressive timelines, and the value-for-money report |
| `publish.py` | Formats the message and sends it via the daemon; supports `--dry-run`, `--test`, `--daemon-status`, `--user`, `--all`, `--value` |
| `match_times.json` | Accurate IST kickoff times (joined to games by team id) overlaid on the API's `local_date` |
| `build_match_times.py` | One-time/refresh script that regenerates `match_times.json` from ESPN's schedule API |
| `TEAM_MAPPING.md` | Human-readable mapping report (id · FIFA code · name · tier · owner) for cross-verifying `config.py` |
| `whatsapp_sender/daemon.js` | Long-lived Node.js process that holds a warm WhatsApp session and exposes a local HTTP API (`POST /send`, `GET /health`) |
| `com.fifafantasy.whatsappd.plist` | macOS launchd agent — starts the daemon at login and auto-restarts it if it crashes |

### Scoring system

| Event | Points |
|-------|--------|
| Win | 2 pts |
| Draw | 1 pt each |
| Goal scored | tier multiplier × 1.0 / 1.5 / 2.0 / 3.0 (Tier 1 → 4) |
| Reach knockout round (R32) | 2 pts (Tier 1–3) / 5 pts (Tier 4) |
| Reach QF / SF / Final | +2 pts each stage |
| Champion / Runner-up | +10 / +5 pts |
| Dark Horse (Tier 3/4 team) — R16 / QF / SF | +1 / +3 / +5 pts |
| Tournament awards (Golden Ball, Boot, etc.) | 3–5 pts |

### Team identity

Teams are identified by their **stable numeric id** from `teams.json` everywhere — rosters, tiers, dark-horse picks, awards, the match-times overlay, and game-to-team matching. There is no name-based or fuzzy string matching anywhere in the pipeline, which keeps scoring robust against spelling variations in the API feed (e.g. "Democratic Republic of the Congo" vs "DR Congo").

- `config.py` structures are keyed by id, with the team name kept as an inline comment for readability.
- `TEAM_DISPLAY_OVERRIDES` in `config.py` supplies short display names for a few teams (e.g. `4 → "Czechia"`); everything else displays `name_en` straight from the registry.
- `TEAM_MAPPING.md` is the at-a-glance map of every id → team → tier → owner, for verifying `config.py` after roster changes.

---

## Setup

### Prerequisites

- Python 3.8+
- Node.js 18+
- `npm`

### 1. Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Install Node dependencies

```bash
cd whatsapp_sender
npm install
```

This downloads the pinned `whatsapp-web.js` fork (which fixes a `ready`-event bug in the upstream package) and Chromium via Puppeteer.

### 3. Configure your league

Edit `config.py` (all team references are **team ids** from `teams.json` — look them up there or in `TEAM_MAPPING.md`):

- **`CONTENDERS`** — map each player's name to their list of team ids
- **`DARK_HORSE`** — each player's chosen dark horse team id (must be Tier 3 or 4)
- **`TEAM_TIERS`** — team id → tier (1–4), drives goal multipliers and qualify bonuses
- **`AUCTION_PRICES`** — per contender, the price (in M) paid for each owned team id; powers the value-for-money report
- **`BUDGETS`** — each player's remaining auction budget (in M), shown in the value-for-money report
- **`WHATSAPP_GROUP_ID`** — the `…@g.us` JID of your WhatsApp group (run `python3 publish.py --find-groups` to find it)

### 4. First-time WhatsApp login (one-time QR scan)

Run the daemon in the foreground so the QR renders in your terminal:

```bash
node whatsapp_sender/daemon.js
```

Scan the QR with **WhatsApp → Settings → Linked Devices → Link a Device**. Once you see `[whatsapp] Ready.`, press `Ctrl-C`.

### 5. Start the daemon via launchd (macOS)

```bash
cp com.fifafantasy.whatsappd.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fifafantasy.whatsappd.plist
```

The daemon now starts automatically at login and restarts itself if it crashes. Logs (including any future QR codes) go to:

```bash
tail -f ~/Library/Logs/fifafantasy-whatsappd.log
```

> **macOS note:** the log path must be outside `~/Downloads`, `~/Documents`, and `~/Desktop` — those directories are TCC-protected and launchd cannot write to them. `~/Library/Logs` is the correct location.

---

## Usage

```bash
python3 publish.py                  # fetch live data and send leaderboard to the group
python3 publish.py --dry-run        # print the message without sending
python3 publish.py --test           # send a timestamped test message
python3 publish.py --daemon-status  # check whether the WhatsApp session is ready
python3 publish.py --find-groups    # list all WhatsApp groups and their JIDs
python3 publish.py --user <name>    # print one contender's per-team points breakdown
python3 publish.py --all            # print every contender's progressive points timeline (audit view)
python3 publish.py --value          # print every contender's value-for-money report (pts per auction M)
python3 publish.py --value <name>   # print just one contender's value-for-money report
```

The leaderboard shows **rank-movement indicators** versus the previous send (🟢▲ up, 🔴▼ down, ➡️ unchanged, 🆕 first appearance). Previous ranks are persisted in `rank_snapshot.json`, which is updated only on a real send (not on `--dry-run`).

`--user`, `--all`, and `--value` print to stdout only — they never send to WhatsApp — and are meant for auditing how points were calculated (every match event with its running cumulative total).

### Value for Money report

`--value` shows **how much each team is worth** — every team's accumulated fantasy points measured against the auction price the contender paid for it, expressed as **pts/M** (points per million spent). For each contender it lists every owned team sorted by pts/M, flags the **✅ best value** and **❌ worst value** picks, marks the **⭐ dark horse**, and shows the contender's totals (points, money spent, overall pts/M, and budget remaining).

Auction prices and budgets are configured per contender in `config.py` (`AUCTION_PRICES` keyed by team id, and `BUDGETS`). Example:

```
💰 FIFA Fantasy 2026 — Value for Money 💰

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tushar — 37 pts | 180M spent | 0.206 pts/M  |  Budget left: 20M
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔵 Morocco              T4   15M   18.0 pts  1.200 pts/M  ✅ Best value  ⭐ Dark Horse (+8 pts)
  🔴 Brazil               T1   90M   14.0 pts  0.156 pts/M
  🟡 Croatia              T2   45M    5.0 pts  0.111 pts/M  ❌ Worst value
...
```

### Example output

```
🏆 FIFA Fantasy 2026 — Leaderboard 🏆

➡️ Tushar  — 37 pts (7 matches)
🟢▲1 Shishir — 29 pts (6 matches)
🔴▼1 Ashwini — 24 pts (7 matches)
...

Data up to: Portugal 1-1 DR Congo (17 Jun 2026)
```

---

## Data source

Set `DATA_SOURCE` in `config.py`:

| Value | Behaviour |
|-------|-----------|
| `"api"` | Fetches live data from `https://worldcup26.ir/get/games` |
| `"local"` | Reads from `LOCAL_JSON_PATH` (useful for testing without hitting the API) |

When fetching from the API, the response is cached to `LOCAL_JSON_PATH` (`sampresp.json`) with sorted keys, so each refresh produces a clean git diff containing only the fields that actually changed (scores, `finished`, etc.) rather than spurious key-order noise. Newly finished matches are auto-committed.

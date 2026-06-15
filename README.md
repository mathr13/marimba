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
| `config.py` | All settings: player rosters, team tiers, scoring constants, dark horse picks, WhatsApp config |
| `games_client.py` | Fetches match data from the API (or a local JSON file); sorts games — finished first, then chronological |
| `scoring.py` | Calculates points and builds the ranked leaderboard |
| `publish.py` | Formats the message and sends it via the daemon; supports `--dry-run`, `--test`, `--daemon-status` |
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

Edit `config.py`:

- **`CONTENDERS`** — map each player's name to their list of national teams
- **`DARK_HORSE`** — each player's chosen dark horse team (must be Tier 3 or 4)
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
python3 publish.py                 # fetch live data and send leaderboard to the group
python3 publish.py --dry-run       # print the message without sending
python3 publish.py --test          # send a timestamped test message
python3 publish.py --daemon-status # check whether the WhatsApp session is ready
python3 publish.py --find-groups   # list all WhatsApp groups and their JIDs
```

### Example output

```
🏆 FIFA Fantasy 2026 — Leaderboard 🏆

Shishir — 29 pts (6 matches)
Tushar  — 26 pts (5 matches)
Ojus    — 11 pts (4 matches)
...

Data up to: Sweden 5-1 Tunisia (14 Jun 2026)
```

---

## Data source

Set `DATA_SOURCE` in `config.py`:

| Value | Behaviour |
|-------|-----------|
| `"api"` | Fetches live data from `https://worldcup26.ir/get/games` |
| `"local"` | Reads from `LOCAL_JSON_PATH` (useful for testing without hitting the API) |

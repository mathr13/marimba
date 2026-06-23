# Running the FIFA Fantasy API

## Prerequisites

- Python 3.8+

## Setup

Install dependencies:

```bash
pip3 install -r requirements.txt
```

## Start the server

```bash
python3 -m uvicorn main:app --reload
```

The `--reload` flag auto-restarts the server on code changes (useful during development).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hello` | Returns a Hello World message |
| GET | `/leaderboard` | Fetches live World Cup results and returns the fantasy leaderboard |

## Try it out

Once the server is running, open your browser or use curl:

```bash
curl http://localhost:8000/hello
```

Expected response:

```json
{"message": "Hello, World!"}
```

Interactive API docs (provided by FastAPI) are available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Publishing the leaderboard to WhatsApp

Sending runs through a **persistent local daemon** (`whatsapp_sender/daemon.js`, built on
[whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js)). The daemon authenticates
**once**, holds a warm session, and exposes a loopback-only HTTP API. `publish.py` then just
POSTs the message — each publish is a near-instant, reliable HTTP call with no browser
cold-start.

> **Why a daemon?** whatsapp-web.js's cold start is flaky on the current WhatsApp Web build
> (the `ready` event can stall, and an inject race can throw mid-startup). Doing that on every
> send is unreliable. The daemon pays that flaky init **once** at startup (it retries
> in-process and is backstopped by launchd), then stays ready. We use a patched fork pinned to
> an immutable commit (`whatsapp-web.js` in `whatsapp_sender/package.json`) that fixes the
> `ready`-never-fires bug.

### One-time setup

```bash
cd whatsapp_sender
npm install                      # installs the pinned whatsapp-web.js fork + puppeteer
```

Find your group's internal JID and put it in `config.py` as `WHATSAPP_GROUP_ID`
(the `…@g.us` value):

```bash
python3 publish.py --find-groups
```

### First login / re-link (QR scan)

The daemon needs a WhatsApp device link. The session is saved in
`whatsapp_sender/.wwebjs_auth/` and reused on every later run, so this is normally one-time
(repeat only if WhatsApp logs the session out). Run the daemon in the foreground so the QR
renders cleanly:

```bash
cd whatsapp_sender
node daemon.js
```

Scan the QR with **WhatsApp → Settings → Linked Devices → Link a Device**, wait for
`[whatsapp] Ready. Daemon serving on http://127.0.0.1:8765`, then `Ctrl-C`.

### Run the daemon in the background (launchd)

```bash
cp com.fifafantasy.whatsappd.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fifafantasy.whatsappd.plist
```

It now starts at login and auto-restarts if it dies (`KeepAlive`). Logs (and any future QR)
go to `~/Library/Logs/fifafantasy-whatsappd.log`:

```bash
tail -f ~/Library/Logs/fifafantasy-whatsappd.log
```

> **macOS gotcha:** the log path **must** live outside `~/Downloads`, `~/Documents`, and
> `~/Desktop`. Those are TCC-protected, and a launchd agent can't create files there — it
> fails instantly with `EX_CONFIG (78)` and no output. `~/Library/Logs` is the correct spot.
> If you move the project, also update the absolute paths in the plist (`ProgramArguments`,
> `WorkingDirectory`) and confirm `node`'s path matches `which node`.

To stop / reload:

```bash
launchctl unload ~/Library/LaunchAgents/com.fifafantasy.whatsappd.plist
```

### Send / preview

```bash
python3 publish.py --daemon-status   # check the session is ready
python3 publish.py --dry-run         # print the message without sending
python3 publish.py --test            # send a timestamped "test" to verify the pipe
python3 publish.py                   # fetch leaderboard and send to the group
```

If the daemon isn't running, `publish.py` prints the exact `launchctl` command to start it.

## Periodic data sync (resilience against API downtime)

The leaderboard publishing depends on fresh match data from the remote API. Because that API
is occasionally unreliable, we decouple the workflow into two independent pieces:

1. **Data syncer** (`sync_data.py`): runs on a **time-of-day-aware schedule** — every 30
   minutes during the 22:00–11:00 IST match window (when most games finish), every 3 hours
   the rest of the day — and silently fetches match data from the API, updating
   `sampresp.json` whenever successful. API failures are logged but don't block anything.
2. **Publisher** (`publish.py`): reads the local cache (`sampresp.json`) and publishes. A
   100% reliable local read — if the API is down, the publisher still sends the leaderboard
   using the most recent cached data.

### One-time setup

```bash
cp com.fifafantasy.datasync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fifafantasy.datasync.plist
```

launchd ticks the syncer every 30 minutes (the finest cadence), starting immediately (on
`RunAtLoad`). Each tick, `sync_data.py` decides whether to actually fetch based on the
current time window — every 30 min during the 22:00–11:00 IST match window, every 3 hours
otherwise — by comparing against `last_attempt` in `sync_status.json` (so cold-window ticks
don't hammer the API). When it does fetch, it retries up to 3 times with backoff if the API
is temporarily down and updates `sync_status.json` with the success/failure result. The
publish message includes a "Synced …" timestamp from that file.

To change the window hours or cadence, edit the constants at the top of `sync_data.py`
(`HOT_START_HOUR`, `HOT_END_HOUR`, `HOT_INTERVAL_MIN`, `COLD_INTERVAL_MIN`).

Monitor the sync logs:

```bash
tail -f ~/Library/Logs/fifafantasy-datasync.log
```

Force a manual run (for testing):

```bash
launchctl kickstart -k gui/$UID/com.fifafantasy.datasync
```

> **Note:** like the WhatsApp daemon, the data syncer's log **must** live outside
> `~/Downloads`, `~/Documents`, and `~/Desktop` (TCC protection). It goes to
> `~/Library/Logs/fifafantasy-datasync.log`. If you move the project, update the
> absolute paths in `com.fifafantasy.datasync.plist`.

### Syncing while the Mac is asleep (one-time setup)

By default, the `LaunchAgent` runs when the Mac is awake but does nothing during
deep sleep. **This matters most for the 22:00–11:00 IST match window — it's
overnight, exactly when the Mac is asleep and when we want 30-minute syncs.** To
keep data fresh then, the syncer re-arms a `pmset` wake event after each run at the
next desired wake time (30 min out in the hot window, up to 3 hours out otherwise),
so the Mac wakes from sleep to run the next sync. This requires two one-time setup
steps (both need `sudo`):

**1. NOPASSWD sudoers rule** — lets the background agent drive `pmset` silently
(without a password prompt the agent can't answer):

```bash
echo 'shishirmathur ALL=(root) NOPASSWD: /usr/bin/pmset' | sudo tee /etc/sudoers.d/fifafantasy-pmset
sudo chmod 440 /etc/sudoers.d/fifafantasy-pmset
sudo visudo -c        # validate syntax before trusting it
```

> **Security note:** the rule is scoped to the single binary `/usr/bin/pmset`
> (power scheduling only). It grants no other root access.

**2. Static daily backstop** — a `pmset repeat` wake at a fixed daily time that
restarts the rolling chain if it ever breaks (e.g. Mac powered off through a
scheduled wake):

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 22:00:00
```

Set this to the **start of the match window (22:00 IST)** so a broken chain
self-heals right when the frequent-sync window begins, rather than mid-day. With
this in place, even a fully broken chain recovers within 24 hours.

**Verify the schedule any time:**

```bash
pmset -g sched
```

After the next agent run you should see a single one-off `wakeorpoweron` event at
the next desired wake time (≤30 min out during the match window, up to 3h out
otherwise), plus the daily `repeat` entry.

> **Caveat:** `wakeorpoweron` reliably wakes from **sleep**. Powering on from a
> full shutdown via RTC is not guaranteed on laptops (especially on battery). Treat
> overnight freshness as "best-effort while sleeping," fully guaranteed once the Mac
> is awake.

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

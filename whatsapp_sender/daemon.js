/**
 * Persistent headless WhatsApp daemon.
 *
 * Authenticates ONCE, holds a warm "ready" session, and exposes a tiny
 * loopback-only HTTP API so publish.py can send instantly without paying the
 * flaky cold-start init cost on every message.
 *
 *   GET  /health            → { ready: <bool> }
 *   POST /send  {groupId,message} → 200 {ok:true} | 503 (warming up) | 500 (error)
 *
 * Cold start is inherently flaky (whatsapp-web.js can hit an inject race where
 * Chrome reloads the WhatsApp Web page mid-injection). We absorb that IN-PROCESS
 * with a bounded init-retry loop (fresh client + Chrome cleanup per attempt)
 * rather than crashing and waiting on launchd's slow restart throttle. Once
 * ready, the session stays warm and sends are instant/reliable.
 *
 * launchd (KeepAlive=true) still backstops process death / disconnects / a
 * fully-exhausted init loop (exit 2).
 *
 * Env vars:
 *   WA_DAEMON_PORT — TCP port to bind on 127.0.0.1 (default 8765)
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { execSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.WA_DAEMON_PORT || '8765', 10);
const authPath = path.join(__dirname, '.wwebjs_auth');

const MAX_INIT_ATTEMPTS = 8;     // in-process cold-start retries before giving up to launchd
const INIT_TIMEOUT_MS = 60000;   // per-attempt ceiling (catches the original ready-never-fires hang)
const QR_TIMEOUT_MS = 180000;    // generous window once a QR is shown (user needs time to scan)
const RETRY_DELAY_MS = 4000;     // pause between attempts

let client = null;
let ready = false;               // true while the WhatsApp session is usable
let serving = false;             // true once we've reached ready at least once (init done)
let awaitingQrScan = false;      // true once a QR is displayed in the current attempt

// Puppeteer emits stray "Target closed" / "Execution context destroyed"
// rejections while a client is being torn down between retries. Those are
// benign noise — swallow them so Node 26 (which crashes on unhandled
// rejections by default) doesn't kill the daemon mid-retry.
process.on('unhandledRejection', err => {
    console.error('[whatsapp] unhandledRejection (ignored):', err && err.message);
});

function cleanupChrome() {
    // Kill any orphaned Chrome bound to THIS session profile (from a crashed or
    // timed-out previous attempt), then clear stale singleton locks.
    try {
        execSync(`pkill -f "${authPath}"`, { stdio: 'ignore' });
        execSync('sleep 1', { stdio: 'ignore' });
    } catch (_) { /* nothing to kill — fine */ }
    const lockDir = path.join(authPath, 'session');
    ['SingletonLock', 'SingletonCookie', 'SingletonSocket'].forEach(f => {
        try { fs.rmSync(path.join(lockDir, f)); } catch (_) {}
    });
}

function buildClient() {
    const c = new Client({
        authStrategy: new LocalAuth({ dataPath: authPath }),
        puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] },
    });

    c.on('qr', qr => {
        awaitingQrScan = true;
        console.log('[whatsapp] Login required — scan this QR code (one-time):');
        qrcode.generate(qr, { small: true });
    });
    c.on('loading_screen', (percent, msg) => {
        console.log(`[whatsapp] Loading session… ${percent}% ${msg || ''}`);
    });
    c.on('authenticated', () => console.log('[whatsapp] Authenticated.'));
    c.on('ready', () => {
        ready = true;
        console.log(`[whatsapp] Ready. Daemon serving on http://127.0.0.1:${PORT}`);
    });
    c.on('disconnected', reason => {
        ready = false;
        // Only bail to launchd if a LIVE serving session dropped. During init
        // recycling, transient disconnects are expected and handled in-process.
        if (serving) {
            console.error('[whatsapp] Disconnected:', reason, '— exiting for launchd to relaunch.');
            process.exit(1);
        } else {
            console.error('[whatsapp] Disconnected during init:', reason);
        }
    });
    return c;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// Wait for the `ready` flag to flip true. Success is the ready EVENT — NOT
// initialize() resolving, because the patched fork can resolve initialize()
// after swallowing a mid-startup "Target closed" error without ever going ready.
async function waitForReady() {
    const start = Date.now();
    while (!ready) {
        const limit = awaitingQrScan ? QR_TIMEOUT_MS : INIT_TIMEOUT_MS;
        if (Date.now() - start > limit) return false;
        await sleep(1000);
    }
    return true;
}

async function start() {
    for (let attempt = 1; attempt <= MAX_INIT_ATTEMPTS; attempt++) {
        cleanupChrome();
        awaitingQrScan = false;
        ready = false;
        client = buildClient();
        console.log(`[whatsapp] Init attempt ${attempt}/${MAX_INIT_ATTEMPTS}…`);

        // Fire init but DON'T gate success on it resolving; gate on `ready`.
        client.initialize().catch(err =>
            console.error(`[whatsapp] initialize() rejected on attempt ${attempt}: ${err.message}`));

        if (await waitForReady()) {
            serving = true;
            return; // genuinely ready
        }

        console.error(`[whatsapp] Attempt ${attempt} never reached ready; recycling.`);
        // Bound destroy() so a wedged browser can't hang the retry loop, then
        // force-kill any lingering Chrome before the next attempt.
        try { await Promise.race([client.destroy(), sleep(8000)]); } catch (_) {}
        cleanupChrome();
        if (attempt < MAX_INIT_ATTEMPTS) await sleep(RETRY_DELAY_MS);
    }
    console.error('[whatsapp] Exhausted init attempts. Exiting (exit 2) for launchd to relaunch.');
    process.exit(2);
}

// ---------------------------------------------------------------------------
// HTTP API (loopback only)
// ---------------------------------------------------------------------------
function sendJson(res, status, body) {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(body));
}

const server = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
        return sendJson(res, 200, { ready });
    }

    if (req.method === 'POST' && req.url === '/send') {
        let raw = '';
        req.on('data', chunk => { raw += chunk; });
        req.on('end', async () => {
            if (!ready || !client) {
                return sendJson(res, 503, { ok: false, error: 'session not ready' });
            }
            let body;
            try {
                body = JSON.parse(raw || '{}');
            } catch (_) {
                return sendJson(res, 400, { ok: false, error: 'invalid JSON' });
            }
            const { groupId, message } = body;
            if (!groupId || !message) {
                return sendJson(res, 400, { ok: false, error: 'groupId and message are required' });
            }
            try {
                const chat = await client.getChatById(groupId);
                await chat.sendMessage(message);
                console.log(`[whatsapp] Message sent to "${chat.name}".`);
                return sendJson(res, 200, { ok: true, chat: chat.name });
            } catch (err) {
                console.error('[whatsapp] Send error:', err.message);
                return sendJson(res, 500, { ok: false, error: err.message });
            }
        });
        return;
    }

    sendJson(res, 404, { ok: false, error: 'not found' });
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`[whatsapp] HTTP server bound to 127.0.0.1:${PORT} (waiting for ready)…`);
});

start();

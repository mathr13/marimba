/**
 * Headless WhatsApp group sender.
 * Called automatically by publish.py via subprocess.
 *
 * Env vars:
 *   WA_GROUP_ID   — group's internal @g.us JID (fast direct lookup, no getChats)
 *   WA_MSG_FILE   — path to a UTF-8 text file containing the message
 *
 * Exit codes:
 *   0 — message sent
 *   1 — bad input / auth failure / send error
 *   2 — timed out waiting for the session to become ready
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const authPath = path.join(__dirname, '.wwebjs_auth');

// 1) Kill any orphaned Chrome left running against THIS session profile.
//    A live Chrome holding the profile is the usual reason `ready` never fires
//    after `authenticated` — the new instance attaches to a half-synced session.
try {
    execSync(`pkill -f "${authPath}"`, { stdio: 'ignore' });
    // Give the OS a moment to release file handles before we touch the locks.
    execSync('sleep 1', { stdio: 'ignore' });
} catch (_) { /* nothing to kill — fine */ }

// 2) Now that no Chrome owns the profile, clear stale singleton locks.
const lockDir = path.join(authPath, 'session');
['SingletonLock', 'SingletonCookie', 'SingletonSocket'].forEach(f => {
    try { fs.rmSync(path.join(lockDir, f)); } catch (_) {}
});

const groupId = process.env.WA_GROUP_ID;
const msgFile = process.env.WA_MSG_FILE;

if (!groupId) { console.error('ERROR: WA_GROUP_ID is required.'); process.exit(1); }
if (!msgFile) { console.error('ERROR: WA_MSG_FILE is required.'); process.exit(1); }

const message = fs.readFileSync(msgFile, 'utf8').trim();
if (!message) { console.error('ERROR: Message file is empty.'); process.exit(1); }

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: authPath }),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] },
});

// 3) Hard ceiling: if `ready` never fires, never hang the Python parent forever.
const READY_TIMEOUT_MS = 60000;
let settled = false;

const readyTimer = setTimeout(async () => {
    if (settled) return;
    settled = true;
    console.error(`[whatsapp] Timed out after ${READY_TIMEOUT_MS / 1000}s waiting for ready. Aborting so it can be retried.`);
    try { await client.destroy(); } catch (_) {}
    process.exit(2);
}, READY_TIMEOUT_MS);

client.on('qr', qr => {
    console.log('[whatsapp] First-time login — scan this QR code:');
    qrcode.generate(qr, { small: true });
});

client.on('loading_screen', (percent, msg) => {
    console.log(`[whatsapp] Loading session… ${percent}% ${msg || ''}`);
});

client.on('authenticated', () => console.log('[whatsapp] Authenticated.'));

client.on('ready', async () => {
    if (settled) return;
    settled = true;
    clearTimeout(readyTimer);
    console.log('[whatsapp] Ready. Looking up group by ID…');
    try {
        const chat = await client.getChatById(groupId);
        await chat.sendMessage(message);
        console.log(`[whatsapp] Message sent to "${chat.name}".`);
        // Let Chrome flush the outbound message to WhatsApp's servers.
        await new Promise(r => setTimeout(r, 4000));
        await client.destroy();
        process.exit(0);
    } catch (err) {
        console.error('[whatsapp] ERROR:', err.message);
        try { await client.destroy(); } catch (_) {}
        process.exit(1);
    }
});

client.on('auth_failure', msg => {
    if (settled) return;
    settled = true;
    clearTimeout(readyTimer);
    console.error('[whatsapp] Auth failed:', msg);
    process.exit(1);
});

client.initialize();

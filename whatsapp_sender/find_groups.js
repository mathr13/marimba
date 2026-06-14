/**
 * Lists all WhatsApp groups and their JIDs.
 * Run via: python3 publish.py --find-groups
 * Copy the JID for your group into WHATSAPP_GROUP_ID in config.py.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const fs = require('fs');
const path = require('path');

const lockDir = path.join(__dirname, '.wwebjs_auth', 'session');
['SingletonLock', 'SingletonCookie', 'SingletonSocket'].forEach(f => {
    try { fs.rmSync(path.join(lockDir, f)); } catch (_) {}
});

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(__dirname, '.wwebjs_auth') }),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] },
});

client.on('authenticated', () => console.log('[whatsapp] Authenticated.'));

client.on('ready', async () => {
    console.log('[whatsapp] Fetching groups...\n');
    const chats = await client.getChats();
    const groups = chats.filter(c => c.isGroup);
    console.log(`Found ${groups.length} groups:\n`);
    groups.forEach(g => console.log(`  ${g.id._serialized.padEnd(30)}  "${g.name}"`));
    console.log('\nCopy the JID for your group into WHATSAPP_GROUP_ID in config.py.');
    await client.destroy();
});

client.on('auth_failure', msg => {
    console.error('[whatsapp] Auth failed:', msg);
    process.exit(1);
});

client.initialize();

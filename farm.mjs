import WebSocket from 'ws';
import https from 'https';
import { readFileSync } from 'fs';

// ═══ CONFIG ═══
const API_BASE = "https://islands.games";
const WS_URLS = [
  "wss://game-production-87db.up.railway.app/",
  "wss://game-production-87deb.up.railway.app/",
  "wss://islands.games:8787",
];
let WS_URL = WS_URLS[0];
const STAT_PRIORITY = "str";
const ATTACK_INTERVAL = 1000;
const STATE_INTERVAL = 200;

// ═══ MAIN ACCOUNT ═══
let MAIN_TOKEN = "";
try {
  // Read token from env or file
  MAIN_TOKEN = process.env.MAIN_TOKEN || "";
} catch(e) {}

let token = MAIN_TOKEN || null;
let name = MAIN_TOKEN ? "xbyteid" : null;
let ws = null;
let connected = false;
let gameData = {};
let attacks = 0;
let allocs = 0;
let msgCount = 0;
let startTime = Date.now();
let running = true;

// Graceful shutdown
process.on('SIGINT', () => { running = false; setTimeout(() => process.exit(0), 1000); });
process.on('SIGTERM', () => { running = false; setTimeout(() => process.exit(0), 1000); });

function generateName() {
  return "xbyte" + Math.random().toString(36).substring(2, 6);
}

async function guestAuth(guestName) {
  return new Promise((resolve) => {
    const data = JSON.stringify({ username: guestName });
    const url = new URL(`${API_BASE}/api/auth/guest`);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/137.0.0.0 Mobile Safari/537.36'
      },
      timeout: 15000
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const d = JSON.parse(body);
          resolve({ token: d.sessionToken, name: d.username, char: d.char });
        } catch(e) { resolve(null); }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.write(data);
    req.end();
  });
}

async function authenticate() {
  if (token) {
    console.log(`[*] Using: ${name}`);
    return true;
  }
  
  for (let i = 0; i < 5; i++) {
    const guestName = generateName();
    console.log(`[*] Guest: ${guestName}`);
    const result = await guestAuth(guestName);
    if (result && result.token) {
      token = result.token;
      name = result.name;
      console.log(`[+] Logged in: ${name} (char=${result.char})`);
      return true;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  console.log("[!] Auth failed");
  return false;
}

function connectWS() {
  return new Promise((resolve) => {
    try {
      ws = new WebSocket(WS_URL, {
        headers: {
          'Origin': 'https://islands.games',
          'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
          'Accept-Language': 'en-US,en;q=0.9',
          'Pragma': 'no-cache',
          'Cache-Control': 'no-cache'
        },
        rejectUnauthorized: false,
        perMessageDeflate: false,
        handshakeTimeout: 10000,
        followRedirects: true
      });

      ws.on('open', () => {
        ws.send(JSON.stringify({
          t: "hello",
          auth: token,
          name: name,
          color: [139, 92, 246]
        }));
        connected = true;
        console.log("[+] WS connected!");
        resolve(true);
      });

      ws.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          const t = msg.t;
          msgCount++;
          gameData[t] = msg;

          if (t === 'welcome') console.log(`[+] Welcome! id=${msg.id}`);
          if (t === 'xp') {
            console.log(`[+] Lv${msg.level} XP:${msg.xp}/${msg.next} STR:${msg.str} Free:${msg.free}`);
            if (msg.free > 0) {
              console.log(`[*] Allocating ${msg.free} -> ${STAT_PRIORITY}`);
              for (let i = 0; i < msg.free; i++) {
                setTimeout(() => send({t:'allocate',stat:STAT_PRIORITY}), i * 300);
                allocs++;
              }
            }
          }
          if (t === 'inv') console.log(`[+] M:${msg.meat} W:${msg.wood} G:${msg.gold} U:${msg.usdc}`);
          if (t === 'stats' && msg.mobKills > 0) console.log(`[+] Kills: ${msg.mobKills}`);
          if (t === 'death') { console.log("[!] DIED! Reviving..."); send({t:'revive'}); }
          if (t === 'error') {
            console.log(`[!] Error: ${msg.msg}`);
            if (/auth|token|session/i.test(msg.msg)) {
              connected = false;
              token = null;
            }
          }
        } catch(e) {}
      });

      ws.on('close', () => { connected = false; console.log("[!] WS closed"); });
      ws.on('error', (e) => { connected = false; console.log(`[!] WS error: ${e.message}`); });
      
      // Timeout
      setTimeout(() => { if (!connected) { try { ws.close(); } catch(e) {} resolve(false); } }, 15000);
      
    } catch(e) {
      console.log(`[!] WS failed: ${e.message}`);
      resolve(false);
    }
  });
}

function send(msg) {
  if (ws && connected) {
    try { ws.send(JSON.stringify(msg)); return true; } catch(e) { connected = false; }
  }
  return false;
}

function status() {
  const elapsed = ((Date.now() - startTime) / 60000).toFixed(1);
  const xp = gameData.xp || {};
  const inv = gameData.inv || {};
  const stats = gameData.stats || {};
  console.log(`\n${'='.repeat(35)}`);
  console.log(` ${name} Lv${xp.level||'?'} | STR:${xp.str||0} VIT:${xp.vit||0} AGI:${xp.agi||0} Free:${xp.free||0}`);
  console.log(` M:${inv.meat||0} W:${inv.wood||0} G:${inv.gold||0} U:${inv.usdc||0}`);
  console.log(` Kills:${stats.mobKills||0} Atk:${attacks} Alloc:${allocs} Msgs:${msgCount}`);
  console.log(` Time: ${elapsed}min`);
  console.log(`${'='.repeat(35)}\n`);
}

async function main() {
  console.log(`\n${'='.repeat(35)}`);
  console.log(` Islands Farm Bot - NODE.JS`);
  console.log(` Stat: ${STAT_PRIORITY} | Atk: ${ATTACK_INTERVAL}ms`);
  console.log(`${'='.repeat(35)}\n`);

  if (!await authenticate()) return;

  let reconnectCount = 0;
  let lastAttack = 0;
  let lastStatus = 0;

  while (running) {
    try {
      if (!token) {
        console.log("[*] Re-auth...");
        if (!await authenticate()) { await new Promise(r => setTimeout(r, 10000)); continue; }
      }

      if (!connected) {
        reconnectCount++;
        if (reconnectCount > 10) {
          console.log("[!] Too many reconnects, re-auth...");
          token = null;
          reconnectCount = 0;
          continue;
        }
        console.log(`[*] Connecting to ${WS_URL}... (${reconnectCount})`);
        if (!await connectWS()) {
          // Try next URL
          const idx = WS_URLS.indexOf(WS_URL);
          if (idx < WS_URLS.length - 1) {
            WS_URL = WS_URLS[idx + 1];
            console.log(`[*] Trying: ${WS_URL}`);
          } else {
            WS_URL = WS_URLS[0];
            await new Promise(r => setTimeout(r, 5000));
          }
          continue;
        }
        reconnectCount = 0;
      }

      const now = Date.now();

      // Send state (keepalive)
      send({t:'state', x:0, y:0, moving:false, facing:'down'});

      // Attack
      if (now - lastAttack >= ATTACK_INTERVAL) {
        if (send({t:'attack'})) attacks++;
        lastAttack = now;
      }

      // Status every 5 min
      if (now - lastStatus >= 300000) {
        status();
        lastStatus = now;
      }

      await new Promise(r => setTimeout(r, STATE_INTERVAL));

    } catch(e) {
      console.log(`[!] Error: ${e.message}`);
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  status();
  if (ws) try { ws.close(); } catch(e) {}
  console.log("[*] Bot stopped");
}

main();

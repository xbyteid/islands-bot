#!/usr/bin/env node
/**
 * Islands Farm Bot - Puppeteer (Termux)
 * Fully automatic: open game -> guest login -> tutorial -> farm
 * Uses real Chrome TLS = no WS blocking
 * 
 * Setup:
 *   pkg install nodejs chromium -y
 *   npm install puppeteer-core
 *   node farm_auto.mjs
 */

import puppeteer from 'puppeteer-core';

const GAME_URL = 'https://islands.games/';
const STAT = 'str';
const ATTACK_MS = 1000;
const STATE_MS = 200;

console.log('='.repeat(40));
console.log(' Islands Farm Bot - AUTO');
console.log(' Stat:', STAT, '| Atk:', ATTACK_MS + 'ms');
console.log('='.repeat(40));

// Launch Chrome
console.log('[*] Launching Chrome...');
const browser = await puppeteer.launch({
  executablePath: '/data/data/com.termux/files/usr/bin/chromium',
  headless: 'new',
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--no-first-run',
    '--no-zygote',
    '--single-process',
    '--disable-extensions'
  ]
});

const page = await browser.newPage();
await page.setViewport({ width: 800, height: 600 });

// Inject bot hooks BEFORE navigation
await page.evaluateOnNewDocument(() => {
  window.__farm = { ws: null, xp: null, inv: null, stats: null, attacks: 0, allocs: 0 };
  
  const origSend = WebSocket.prototype.send;
  WebSocket.prototype.send = function(data) {
    if (!window.__farm.ws && this.readyState === WebSocket.OPEN) {
      window.__farm.ws = this;
      console.log('[FARM] WS captured!');
      
      this.addEventListener('message', (e) => {
        try {
          const d = JSON.parse(e.data);
          if (d.t === 'xp') {
            window.__farm.xp = d;
            // Auto-allocate STR
            if (d.free > 0) {
              console.log('[FARM] Allocating ' + d.free + ' -> str');
              for (let i = 0; i < d.free; i++) {
                setTimeout(() => {
                  if (window.__farm.ws && window.__farm.ws.readyState === 1) {
                    window.__farm.ws.send(JSON.stringify({t:'allocate',stat:'str'}));
                    window.__farm.allocs++;
                  }
                }, i * 300);
              }
            }
          }
          if (d.t === 'inv') window.__farm.inv = d;
          if (d.t === 'stats') window.__farm.stats = d;
          if (d.t === 'death') {
            console.log('[FARM] DIED! Reviving...');
            window.__farm.ws.send(JSON.stringify({t:'revive'}));
          }
        } catch(ex) {}
      });
    }
    return origSend.call(this, data);
  };
});

// Load game
console.log('[*] Loading game...');
await page.goto(GAME_URL, { waitUntil: 'networkidle2', timeout: 30000 });
console.log('[+] Game loaded!');

// Guest login
console.log('[*] Logging in as guest...');
try {
  await page.waitForSelector('button', { timeout: 5000 });
  
  // Click "Set sail as guest"
  const buttons = await page.$$('button');
  for (const btn of buttons) {
    const text = await btn.evaluate(el => el.textContent);
    if (text.includes('guest') || text.includes('Guest')) {
      await btn.click();
      console.log('[+] Clicked guest button');
      break;
    }
  }
  
  await new Promise(r => setTimeout(r, 2000));
  
  // Type name
  const input = await page.$('input[placeholder]');
  if (input) {
    const name = 'xbyte' + Math.random().toString(36).substring(2, 6);
    await input.type(name);
    console.log('[+] Name: ' + name);
    
    // Click "Set sail"
    const btns2 = await page.$$('button');
    for (const btn of btns2) {
      const text = await btn.evaluate(el => el.textContent);
      if (text.includes('Set sail') && !text.includes('guest')) {
        await btn.click();
        console.log('[+] Clicked Set sail');
        break;
      }
    }
  }
} catch(e) {
  console.log('[!] Login:', e.message);
}

// Wait for game to load
console.log('[*] Waiting for game...');
await new Promise(r => setTimeout(r, 10000));

// Complete tutorial
console.log('[*] Tutorial...');
for (let i = 0; i < 15; i++) {
  try {
    const clicked = await page.evaluate(() => {
      const btns = document.querySelectorAll('button');
      for (const btn of btns) {
        const text = btn.textContent.trim();
        if (['Next', "Let's go", 'Finish', 'OK', 'Close'].includes(text)) {
          btn.click();
          return text;
        }
      }
      return null;
    });
    if (clicked) {
      console.log('[+] Tutorial: ' + clicked);
      await new Promise(r => setTimeout(r, 1500));
    } else {
      break;
    }
  } catch(e) { break; }
}

console.log('[+] Tutorial done!');

// Start farming loop
console.log('[*] Starting farm loop...');
let lastAttack = 0;
let lastStatus = 0;

const farm = setInterval(() => {
  page.evaluate((attackMs) => {
    const f = window.__farm;
    if (!f || !f.ws || f.ws.readyState !== 1) return;
    
    const now = Date.now();
    
    // Keep-alive state
    f.ws.send(JSON.stringify({t:'state',x:0,y:0,moving:false,facing:'down'}));
    
    // Attack
    if (now - (f.lastAttack || 0) >= attackMs) {
      f.ws.send(JSON.stringify({t:'attack'}));
      f.attacks++;
      f.lastAttack = now;
    }
  }, ATTACK_MS);
}, STATE_MS);

// Status report
const statusLoop = setInterval(async () => {
  const data = await page.evaluate(() => {
    const f = window.__farm;
    if (!f) return null;
    return {
      attacks: f.attacks,
      allocs: f.allocs,
      xp: f.xp,
      inv: f.inv,
      stats: f.stats,
      wsState: f.ws ? f.ws.readyState : -1
    };
  });
  
  if (data) {
    const xp = data.xp || {};
    const inv = data.inv || {};
    const stats = data.stats || {};
    console.log(`[STATUS] Lv${xp.level||'?'} STR:${xp.str||0} Free:${xp.free||0} | Atk:${data.attacks} Alloc:${data.allocs} | Kills:${stats.mobKills||0} | M:${inv.meat||0} W:${inv.wood||0} G:${inv.gold||0} U:${inv.usdc||0} | WS:${data.wsState}`);
  }
}, 300000);

// Handle shutdown
process.on('SIGINT', async () => {
  console.log('\n[!] Shutting down...');
  clearInterval(farm);
  clearInterval(statusLoop);
  await browser.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  clearInterval(farm);
  clearInterval(statusLoop);
  await browser.close();
  process.exit(0);
});

// Take screenshot for debugging
await page.screenshot({ path: '/sdcard/Download/farm_start.png' });
console.log('[+] Screenshot saved to Download/farm_start.png');
console.log('[+] BOT RUNNING! Ctrl+C to stop');

// Keep alive
await new Promise(() => {});

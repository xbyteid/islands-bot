#!/usr/bin/env python3
"""Islands Farm Bot v21 — Secure signing architecture.
Private key NEVER enters browser JS. All signing via Python bridge.
Anti-ban humanized farming + tree/gold cycling.
"""
import asyncio, json, time, sys, os, traceback, random
from playwright.async_api import async_playwright

WALLET_FILE = '/root/.hermes/profiles/alon/vault/wallets/solana_main.json'
NACL_FILE = '/root/islands-bot/tweetnacl.min.js'
STATE_FILE = '/root/islands-bot/farm_state.json'
LOG_FILE = '/root/islands-bot/farm.log'

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f: f.write(line + '\n')
    except: pass

# === LOAD KEY (Python only, NEVER in JS) ===
with open(WALLET_FILE) as f: wallet = json.load(f)
pk_bytes = wallet['private_key_bytes']
addr = wallet['address']

# Public key bytes (safe to share — it's the address)
pub_bytes = pk_bytes[32:]

# === LOAD NACL FOR SERVER-SIDE SIGNING ===
import nacl.signing
import nacl.bindings
seed = bytes(pk_bytes[:32])
signing_key = nacl.signing.SigningKey(seed)
verify_key = signing_key.verify_key
pub_key_bytes = bytes(verify_key)

# Base58 encode for address
def b58_encode(data):
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    n = int.from_bytes(data, 'big')
    result = ''
    while n > 0:
        n, remainder = divmod(n, 58)
        result = alphabet[remainder] + result
    for byte in data:
        if byte == 0: result = '1' + result
        else: break
    return result

pubkey_b58 = b58_encode(pub_key_bytes)
log(f'Wallet: {pubkey_b58[:16]}... (key in Python only)')

# === JS INJECT — NO PRIVATE KEY, ONLY PUBLIC KEY + SIGN BRIDGE ===
# This code has ZERO secret material. It requests signatures from Python via fetch.
INJECT_JS = """
(function() {
  const pubBytes = new Uint8Array(""" + json.dumps(list(pub_bytes)) + """);
  
  // Base58 encode for address display
  const A='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  function b58(b){
    let n=BigInt('0x'+[...b].map(x=>x.toString(16).padStart(2,'0')).join('')),s='';
    while(n>0n){s=A[Number(n%58n)]+s;n/=58n;}
    for(let i=0;i<b.length&&b[i]===0;i++)s='1'+s;
    return s;
  }
  const p58 = b58(pubBytes);
  
  class PubKey {
    constructor(b){this._bytes=b;}
    toBase58(){return p58;}
    toBuffer(){return this._bytes;}
    toString(){return p58;}
    toJSON(){return p58;}
    equals(o){return o?.toBase58?.()===p58;}
  }
  
  const pubKey = new PubKey(pubBytes);
  
  // Sign via Python bridge — NO key in JS
  async function sign(message) {
    let msgBytes;
    if (message instanceof Uint8Array) msgBytes = message;
    else if (typeof message === 'string') msgBytes = new TextEncoder().encode(message);
    else msgBytes = new Uint8Array(Object.values(message));
    
    // Convert to base64 for transport
    let binary = '';
    for (let i = 0; i < msgBytes.length; i++) binary += String.fromCharCode(msgBytes[i]);
    const b64 = btoa(binary);
    
    // Request signature from Python via page bridge
    const resp = await window.__signBridge(b64);
    // Response is base64-encoded signature
    const sigBytes = Uint8Array.from(atob(resp), c => c.charCodeAt(0));
    return sigBytes;
  }
  
  // Phantom-compatible wallet interface
  window.solana = {
    isPhantom: true,
    publicKey: pubKey,
    connected: true,
    connect: async () => ({ publicKey: pubKey }),
    disconnect: async () => {},
    signMessage: async (m) => ({ signature: await sign(m), publicKey: pubKey }),
    on: () => {},
    request: async (r) => {
      if (r?.method === 'connect') return { publicKey: p58 };
      if (r?.method === 'signMessage') return { signature: await sign(r.params?.message) };
      return null;
    }
  };
  if (!window.phantom) window.phantom = {};
  window.phantom.solana = window.solana;
  
  // === GAME DATA HOOKS (no secrets needed) ===
  const OrigWS = window.WebSocket;
  window._ws = null; window._wsOpen = false;
  window._lootLog = []; window._invData = {meat:0,gold:0,wood:0};
  window._xpData = {level:1,str:0,free:0}; window._dead = false;
  window._worldData = null;
  window._treePositions = []; window._goldPositions = [];
  window._resourceMode = 'tree';
  window._currentPos = {x:0,y:0};
  
  // Anti-ban state
  window._antiBan = {
    facing:'down',
    faces:['down','up','left','right','down','left','down'],
    lastFaceChange:0,
    faceInterval:8000 + Math.random()*12000,
    lastAfk:Date.now(),
    afkInterval:180000 + Math.random()*180000,
    afkActive:false,
    afkUntil:0,
    sessionStart:Date.now(),
    sessionMax:7200000 + Math.random()*7200000,
    messagesSent:0,
    lastMsg:0,
    msgInterval:120000 + Math.random()*180000,
    chatMessages:[
      'gg','nice','lol','wow','bruh','hmm','ok','ty',
      'lets go','sheesh','no way','w','F','L',
      'anyone selling?','how much wood?','where gold?',
      'need help','this game is fun','laggy today',
      'how to get land?','price check?','anyone wanna trade?',
      'im tired','brb','afk for a bit','back',
    ],
    totalAttacks:0,
    lastActivity:Date.now(),
  };
  
  function rand(min,max){return Math.floor(Math.random()*(max-min+1))+min;}
  function jitter(val,pct){return val+Math.floor(val*(Math.random()*2-1)*pct);}
  function pick(arr){return arr[Math.floor(Math.random()*arr.length)];}
  
  window.WebSocket = function(url, proto) {
    const ws = proto ? new OrigWS(url, proto) : new OrigWS(url);
    window._ws = ws;
    ws.addEventListener('open', function(){ window._wsOpen = true; });
    ws.addEventListener('message', function(evt) {
      try {
        if (typeof evt.data === 'string') {
          const d = JSON.parse(evt.data);
          if (d.t === 'loot') window._lootLog.push(d);
          if (d.t === 'inv') window._invData = {meat:d.meat||0, gold:d.gold||0, wood:d.wood||0};
          if (d.t === 'xp') window._xpData = {level:d.level||1, str:d.str||0, free:d.free||0};
          if (d.t === 'death') window._dead = true;
          if (d.t === 'world') {
            window._worldData = d;
            if (d.treeHits) {
              for (const th of d.treeHits) {
                let found = false;
                for (const t of window._treePositions) { if (t[0]===th.x&&t[1]===th.y) {found=true;break;} }
                if (!found) window._treePositions.push([th.x, th.y]);
              }
            }
            if (d.goldHits) {
              for (const gh of d.goldHits) {
                let found = false;
                for (const g of window._goldPositions) { if (g[0]===gh.x&&g[1]===gh.y) {found=true;break;} }
                if (!found) window._goldPositions.push([gh.x, gh.y]);
              }
            }
            if (d.golds) {
              for (const g of d.golds) {
                let found = false;
                for (const gp of window._goldPositions) { if (gp[0]===g.x&&gp[1]===g.y) {found=true;break;} }
                if (!found) window._goldPositions.push([g.x, g.y]);
              }
            }
          }
        }
      } catch(e) {}
    });
    return ws;
  };
  window.WebSocket.prototype = OrigWS.prototype;
  
  // Fallback positions
  const TREE_FALLBACK = [
    [23680,16000],[23040,16000],[24256,16000],
    [23680,15232],[23040,15232],[24256,15232],
    [23680,16448],[23040,16448],[24256,16448],
    [23360,16000],[23680,14656],[24000,16000],
    [23360,15232],[23680,15680],[24000,15232],
    [23360,16448],[24000,16448],[24256,14656],
  ];
  const GOLD_FALLBACK = [
    [18112,20352],[18816,20544],[19072,20096],[19968,20992],
    [19200,19968],[19904,19904],[19904,19840],[19392,20096],
    [19712,20480],[18432,20672],
  ];
  window._treePositions = [...TREE_FALLBACK];
  window._goldPositions = [...GOLD_FALLBACK];
  
  let attackLoop = null, cycleLoop = null, modeLoop = null, antiBanLoop = null;
  let currentIdx = 0;
  
  window._getResourceList = function() {
    if (window._resourceMode === 'gold')
      return window._goldPositions.length > 0 ? window._goldPositions : GOLD_FALLBACK;
    return window._treePositions.length > 0 ? window._treePositions : TREE_FALLBACK;
  };
  
  window._humanMoveTo = function(tx, ty) {
    if (!window._ws || window._ws.readyState !== 1) return;
    const cx = window._currentPos.x || tx;
    const cy = window._currentPos.y || ty;
    const dist = Math.sqrt((tx-cx)**2 + (ty-cy)**2);
    if (dist > 2000) {
      const steps = rand(2, 4);
      for (let i = 1; i <= steps; i++) {
        const ratio = i / steps;
        const mx = Math.floor(cx + (tx-cx)*ratio + jitter(0, 0.02));
        const my = Math.floor(cy + (ty-cy)*ratio + jitter(0, 0.02));
        setTimeout(function() {
          if (window._ws && window._ws.readyState === 1)
            window._ws.send(JSON.stringify({t:'state',x:mx,y:my,moving:true,facing:1,boat:false,bd:'down',vcx:mx,vcy:my,vr:734}));
        }, i * rand(100, 300));
      }
    }
    const jx = tx + rand(-50, 50);
    const jy = ty + rand(-50, 50);
    setTimeout(function() {
      if (window._ws && window._ws.readyState === 1) {
        window._ws.send(JSON.stringify({t:'state',x:jx,y:jy,moving:false,facing:1,boat:false,bd:window._antiBan.facing,vcx:jx,vcy:jy,vr:734}));
        window._currentPos = {x:jx, y:jy};
      }
    }, dist > 2000 ? rand(400, 800) : rand(50, 200));
  };
  
  window._sendCmd = function(msg) {
    if (!window._ws || window._ws.readyState !== 1) return;
    try { window._ws.send(JSON.stringify(msg)); } catch(e) {}
  };
  
  window._startAttack = function() {
    if (attackLoop) return;
    window._resourceMode = 'tree';
    currentIdx = 0;
    const startPos = window._getResourceList()[0];
    window._humanMoveTo(startPos[0], startPos[1]);
    
    function doAttack() {
      if (!window._ws || window._ws.readyState !== 1) return;
      if (window._antiBan.afkActive && Date.now() < window._antiBan.afkUntil) return;
      try {
        const resources = window._getResourceList();
        if (resources.length === 0) return;
        const pos = resources[currentIdx % resources.length];
        const jx = pos[0] + rand(-30, 30);
        const jy = pos[1] + rand(-30, 30);
        window._ws.send(JSON.stringify({t:'state',x:jx,y:jy,moving:false,facing:1,boat:false,bd:window._antiBan.facing,vcx:jx,vcy:jy,vr:734}));
        const hits = rand(1, 3);
        for (let i = 0; i < hits; i++) window._ws.send(JSON.stringify({t:'attack'}));
        window._antiBan.totalAttacks += hits;
        window._antiBan.lastActivity = Date.now();
      } catch(e) {}
      attackLoop = setTimeout(doAttack, jitter(60, 0.4));
    }
    doAttack();
    
    function doCycle() {
      currentIdx++;
      const resources = window._getResourceList();
      if (resources.length > 0) {
        const pos = resources[currentIdx % resources.length];
        window._humanMoveTo(pos[0], pos[1]);
      }
      cycleLoop = setTimeout(doCycle, rand(1500, 3500));
    }
    cycleLoop = setTimeout(doCycle, rand(1500, 3500));
    
    function doModeSwitch() {
      window._resourceMode = window._resourceMode === 'tree' ? 'gold' : 'tree';
      currentIdx = 0;
      const resources = window._getResourceList();
      if (resources.length > 0) window._humanMoveTo(resources[0][0], resources[0][1]);
      modeLoop = setTimeout(doModeSwitch, rand(45000, 120000));
    }
    modeLoop = setTimeout(doModeSwitch, rand(45000, 90000));
    
    antiBanLoop = setTimeout(function antiBanTick() {
      const ab = window._antiBan;
      const now = Date.now();
      
      if (!ab.afkActive && now - ab.lastAfk > ab.afkInterval) {
        ab.afkActive = true; ab.afkUntil = now + rand(10000, 30000);
        ab.lastAfk = now; ab.afkInterval = rand(180000, 360000);
      }
      if (ab.afkActive && now >= ab.afkUntil) ab.afkActive = false;
      
      if (now - ab.lastFaceChange > ab.faceInterval) {
        ab.facing = pick(ab.faces);
        ab.lastFaceChange = now; ab.faceInterval = rand(8000, 20000);
      }
      
      if (now - ab.lastMsg > ab.msgInterval && ab.messagesSent < 10) {
        const msg = pick(ab.chatMessages);
        if (window._ws && window._ws.readyState === 1) {
          window._ws.send(JSON.stringify({t:'chat', msg:msg}));
          ab.messagesSent++; ab.lastMsg = now; ab.msgInterval = rand(120000, 300000);
        }
      }
      
      if (!ab.afkActive && Math.random() < 0.15) {
        const resources = window._getResourceList();
        if (resources.length > 0) {
          const base = resources[currentIdx % resources.length];
          const wx = base[0] + rand(-200, 200);
          const wy = base[1] + rand(-200, 200);
          if (window._ws && window._ws.readyState === 1)
            window._ws.send(JSON.stringify({t:'state',x:wx,y:wy,moving:true,facing:1,boat:false,bd:ab.facing,vcx:wx,vcy:wy,vr:734}));
        }
      }
      
      if (now - ab.sessionStart > ab.sessionMax) {
        if (window._ws) window._ws.close();
        return;
      }
      
      antiBanLoop = setTimeout(antiBanTick, rand(3000, 8000));
    }, rand(3000, 8000));
  };
  
  window._getStats = function() {
    const loots = {wood:0, gold:0, meat:0};
    for (const l of window._lootLog) {
      if (l.item === 'wood') loots.wood++;
      else if (l.item === 'gold') loots.gold++;
      else if (l.item === 'meat') loots.meat++;
    }
    const ab = window._antiBan;
    return {
      loots:loots, inv:window._invData, xp:window._xpData, dead:window._dead,
      total:window._lootLog.length, wsOpen:window._wsOpen,
      mode:window._resourceMode,
      trees:window._treePositions.length, golds:window._goldPositions.length,
      antiBan: {
        afk:ab.afkActive, facing:ab.facing, attacks:ab.totalAttacks,
        msgs:ab.messagesSent,
        sessionAge:Math.floor((Date.now()-ab.sessionStart)/60000)+'m',
        sessionMax:Math.floor(ab.sessionMax/60000)+'m',
      },
      worldInfo: window._worldData ? {
        players:window._worldData.players?.length||0,
        mobs:window._worldData.mobs?.length||0,
        treesChopped:window._worldData.trees?.length||0,
        goldHits:window._worldData.goldHits?.length||0,
        treeHits:window._worldData.treeHits?.length||0
      } : null
    };
  };
  window._resetStats = function() { window._lootLog = []; window._dead = false; };
  
  console.log('[HOOK] v21 Secure (no private key in JS): ' + p58);
})();
"""

async def run_bot():
    session_duration = random.randint(7200, 14400)
    log(f'Session target: {session_duration//60}min (secure mode)')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        ctx = await browser.new_context(
            viewport={"width":1280,"height":720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        
        # === SECURE SIGNING BRIDGE ===
        # Intercept fetch to http://sign.local/sign → sign in Python
        async def handle_sign(route):
            try:
                body = await route.request.post_data()
                data = json.loads(body)
                msg_b64 = data['message']
                import base64
                msg_bytes = base64.b64decode(msg_b64)
                
                # Sign in Python — key NEVER leaves this process
                sig = signing_key.sign(msg_bytes).signature
                sig_b64 = base64.b64encode(sig).decode()
                
                await route.fulfill(
                    status=200,
                    content_type='application/json',
                    body=json.dumps({'signature': sig_b64})
                )
            except Exception as e:
                log(f'Sign error: {e}')
                await route.fulfill(status=500, body='sign error')
        
        await page.route('http://sign.local/sign', handle_sign)
        
        # Inject JS (no secrets)
        await ctx.add_init_script(INJECT_JS)
        
        log(f'Loading ({pubkey_b58[:12]}...)')
        await page.goto('https://islands.games', wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(random.uniform(3, 7))
        
        await page.locator('button:has-text("Connect Wallet")').first.click()
        log('Connecting...')
        await asyncio.sleep(random.uniform(8, 15))
        
        for _ in range(15):
            try:
                for t in ["Let's go","Next","Got it","OK","Finish"]:
                    btn = page.locator(f'button:has-text("{t}")').first
                    if await btn.is_visible(timeout=500):
                        await btn.click()
                        await asyncio.sleep(random.uniform(0.3, 1.2))
                        break
                else: break
            except: break
        try: await page.locator('button:has-text("Play")').first.click(timeout=3000)
        except: pass
        await asyncio.sleep(random.uniform(3, 8))
        
        await page.evaluate('''()=>{
            document.querySelectorAll('.sp-close, button[aria-label="Close"]').forEach(b=>b.click());
            document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim()==='Finish')b.click();});
        }''')
        
        for _ in range(20):
            ok = await asyncio.wait_for(page.evaluate('()=>({open:window._wsOpen,ws:!!window._ws})'), timeout=5)
            if ok.get('open'): break
            await asyncio.sleep(random.uniform(0.8, 1.5))
        log(f'WS: {ok}')
        
        await page.evaluate('()=>window._startAttack()')
        log('=== FARMING (SECURE v21) ===')
        start = time.time()
        
        while True:
            await asyncio.sleep(random.uniform(55, 70))
            
            if time.time() - start > session_duration:
                log(f'Session max ({session_duration//60}m) reached, rotating...')
                break
            
            try:
                stats = await asyncio.wait_for(page.evaluate('window._getStats()'), timeout=10)
                e = time.time() - start
                loots = stats.get('loots', {})
                inv = stats.get('inv', {})
                xp = stats.get('xp', {})
                wi = stats.get('worldInfo', {})
                ab = stats.get('antiBan', {})
                mode = stats.get('mode', '?')
                trees = stats.get('trees', 0)
                golds = stats.get('golds', 0)
                
                afk_str = 'AFK' if ab.get('afk') else 'ACT'
                log(f'[{e/60:.1f}m] {afk_str} Mode:{mode} | T:{trees} G:{golds} | Loot W:{loots.get("wood")} G:{loots.get("gold")} M:{loots.get("meat")} | Inv W:{inv.get("wood")} G:{inv.get("gold")} M:{inv.get("meat")} | Lv:{xp.get("level")} Atk:{ab.get("attacks")}')
                
                if stats.get('dead'):
                    log('DIED! Reviving...')
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    await page.evaluate('()=>window._sendCmd({t:"revive"})')
                
                if xp.get('free', 0) > 0:
                    await asyncio.sleep(random.uniform(0.2, 0.8))
                    await page.evaluate('()=>window._sendCmd({t:"allocate",stat:"str"})')
                    log('Allocated STR')
                
                with open(STATE_FILE, 'w') as f: json.dump(stats, f, indent=2)
                await page.screenshot(path='/root/islands-bot/farm_v21.png')
            except Exception as e:
                log(f'Read err: {e}')
        
        await browser.close()

async def main():
    while True:
        try: await run_bot()
        except Exception as e: log(f'FATAL: {e}\n{traceback.format_exc()}')
        delay = random.uniform(20, 60)
        log(f'Restart in {delay:.0f}s...')
        await asyncio.sleep(delay)

if __name__ == '__main__':
    asyncio.run(main())

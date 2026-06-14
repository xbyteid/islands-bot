#!/usr/bin/env python3
"""Islands Farm Bot v20 — Anti-ban humanized farming.
Dynamic tree + gold with randomized behavior patterns.
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

with open(WALLET_FILE) as f: wallet = json.load(f)
pk_bytes = wallet['private_key_bytes']
pk_js = ",".join(str(b) for b in pk_bytes)
addr = wallet['address']
with open(NACL_FILE) as f: nacl_js = f.read()

INJECT = nacl_js + """
(function() {
  const pk=new Uint8Array([""" + pk_js + """]),pub=pk.slice(32),sk=pk;
  const A='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  function b58(b){let n=BigInt('0x'+[...b].map(x=>x.toString(16).padStart(2,'0')).join('')),s='';while(n>0n){s=A[Number(n%58n)]+s;n/=58n;}for(let i=0;i<b.length&&b[i]===0;i++)s='1'+s;return s;}
  const p58=b58(pub);
  class PubKey{constructor(b){this._bytes=b;}toBase58(){return p58;}toBuffer(){return this._bytes;}toString(){return p58;}toJSON(){return p58;}equals(o){return o?.toBase58?.()===p58;}}
  const pubKey=new PubKey(pub);
  function sign(m){let b;if(m instanceof Uint8Array)b=m;else if(typeof m==='string')b=new TextEncoder().encode(m);else b=new Uint8Array(Object.values(m));return nacl.sign.detached(b,sk);}
  window.solana={isPhantom:true,publicKey:pubKey,connected:true,
    connect:async()=>({publicKey:pubKey}),disconnect:async()=>{},
    signMessage:async(m)=>({signature:sign(m),publicKey:pubKey}),
    on:()=>{},request:async(r)=>{if(r?.method==='connect')return{publicKey:p58};if(r?.method==='signMessage')return{signature:sign(r.params?.message)};return null;}
  };
  if(!window.phantom)window.phantom={};window.phantom.solana=window.solana;
  
  // === RANDOM HELPERS ===
  function rand(min,max){return Math.floor(Math.random()*(max-min+1))+min;}
  function jitter(val,pct){return val+Math.floor(val*(Math.random()*2-1)*pct);}
  function pick(arr){return arr[Math.floor(Math.random()*arr.length)];}
  
  // === ANTI-BAN STATE ===
  window._antiBan={
    facing:'down',
    faces:['down','up','left','right','down','left','down'], // weighted
    lastFaceChange:0,
    faceInterval:rand(8000,20000),
    lastAfk:Date.now(),
    afkInterval:rand(180000,360000), // 3-6 min
    afkActive:false,
    afkUntil:0,
    sessionStart:Date.now(),
    sessionMax:rand(7200000,14400000), // 2-4 hours
    messagesSent:0,
    lastMsg:0,
    msgInterval:rand(120000,300000), // 2-5 min
    chatMessages:[
      'gg','nice','lol','wow','bruh','hmm','ok','ty',
      'lets go','sheesh','no way','w',' W','F','L',
      'anyone selling?','how much wood?','where gold?',
      'need help','this game is fun','laggy today',
      'how to get land?','price check?','anyone wanna trade?',
      'im tired','brb','afk for a bit','back',
    ],
    totalAttacks:0,
    lastActivity:Date.now(),
  };
  
  const OrigWS=window.WebSocket;
  window._ws=null;window._wsOpen=false;
  window._lootLog=[];window._invData={meat:0,gold:0,wood:0};
  window._xpData={level:1,str:0,free:0};window._dead=false;
  window._worldData=null;
  window._treePositions=[];
  window._goldPositions=[];
  window._resourceMode='tree';
  window._currentPos={x:0,y:0};
  
  window.WebSocket=function(url,proto){
    const ws=proto?new OrigWS(url,proto):new OrigWS(url);
    window._ws=ws;
    ws.addEventListener('open',function(){window._wsOpen=true;});
    ws.addEventListener('message',function(evt){
      try{if(typeof evt.data==='string'){
        const d=JSON.parse(evt.data);
        if(d.t==='loot')window._lootLog.push(d);
        if(d.t==='inv')window._invData={meat:d.meat||0,gold:d.gold||0,wood:d.wood||0};
        if(d.t==='xp')window._xpData={level:d.level||1,str:d.str||0,free:d.free||0};
        if(d.t==='death')window._dead=true;
        if(d.t==='world'){
          window._worldData=d;
          if(d.treeHits){
            for(const th of d.treeHits){
              let found=false;
              for(const t of window._treePositions){if(t[0]===th.x&&t[1]===th.y){found=true;break;}}
              if(!found) window._treePositions.push([th.x,th.y]);
            }
          }
          if(d.goldHits){
            for(const gh of d.goldHits){
              let found=false;
              for(const g of window._goldPositions){if(g[0]===gh.x&&g[1]===gh.y){found=true;break;}}
              if(!found) window._goldPositions.push([gh.x,gh.y]);
            }
          }
          if(d.golds){
            for(const g of d.golds){
              let found=false;
              for(const gp of window._goldPositions){if(gp[0]===g.x&&gp[1]===g.y){found=true;break;}}
              if(!found) window._goldPositions.push([g.x,g.y]);
            }
          }
        }
      }}catch(e){}
    });
    return ws;
  };
  window.WebSocket.prototype=OrigWS.prototype;
  
  // Fallback positions
  const TREE_FALLBACK=[
    [23680,16000],[23040,16000],[24256,16000],
    [23680,15232],[23040,15232],[24256,15232],
    [23680,16448],[23040,16448],[24256,16448],
    [23360,16000],[23680,14656],[24000,16000],
    [23360,15232],[23680,15680],[24000,15232],
    [23360,16448],[24000,16448],[24256,14656],
  ];
  const GOLD_FALLBACK=[
    [18112,20352],[18816,20544],[19072,20096],[19968,20992],
    [19200,19968],[19904,19904],[19904,19840],[19392,20096],
    [19712,20480],[18432,20672],
  ];
  
  window._treePositions=[...TREE_FALLBACK];
  window._goldPositions=[...GOLD_FALLBACK];
  
  let attackLoop=null;
  let cycleLoop=null;
  let modeLoop=null;
  let antiBanLoop=null;
  let currentIdx=0;
  
  window._getResourceList=function(){
    if(window._resourceMode==='gold'){
      return window._goldPositions.length>0 ? window._goldPositions : GOLD_FALLBACK;
    }
    return window._treePositions.length>0 ? window._treePositions : TREE_FALLBACK;
  };
  
  // === HUMANIZED MOVE ===
  window._humanMoveTo=function(tx,ty){
    if(!window._ws||window._ws.readyState!==1)return;
    const cx=window._currentPos.x||tx;
    const cy=window._currentPos.y||ty;
    const dist=Math.sqrt((tx-cx)**2+(ty-cy)**2);
    
    if(dist>2000){
      // Long distance: walk in 2-4 steps
      const steps=rand(2,4);
      for(let i=1;i<=steps;i++){
        const ratio=i/steps;
        const mx=Math.floor(cx+(tx-cx)*ratio+jitter(0,0.02));
        const my=Math.floor(cy+(ty-cy)*ratio+jitter(0,0.02));
        setTimeout(function(){
          if(window._ws&&window._ws.readyState===1){
            window._ws.send(JSON.stringify({t:'state',x:mx,y:my,moving:true,facing:1,boat:false,bd:'down',vcx:mx,vcy:my,vr:734}));
          }
        },i*rand(100,300));
      }
    }
    
    // Final position with jitter
    const jx=tx+rand(-50,50);
    const jy=ty+rand(-50,50);
    setTimeout(function(){
      if(window._ws&&window._ws.readyState===1){
        window._ws.send(JSON.stringify({t:'state',x:jx,y:jy,moving:false,facing:1,boat:false,bd:window._antiBan.facing,vcx:jx,vcy:jy,vr:734}));
        window._currentPos={x:jx,y:jy};
      }
    },dist>2000?rand(400,800):rand(50,200));
  };
  
  window._sendCmd=function(msg){
    if(!window._ws||window._ws.readyState!==1)return;
    try{window._ws.send(JSON.stringify(msg));}catch(e){}
  };
  
  // === MAIN ATTACK LOOP (RANDOMIZED) ===
  window._startAttack=function(){
    if(attackLoop)return;
    
    window._resourceMode='tree';
    currentIdx=0;
    
    const startPos=window._getResourceList()[0];
    window._humanMoveTo(startPos[0],startPos[1]);
    
    // Attack with randomized timing
    function doAttack(){
      if(!window._ws||window._ws.readyState!==1)return;
      if(window._antiBan.afkActive&&Date.now()<window._antiBan.afkUntil)return;
      
      try{
        const resources=window._getResourceList();
        if(resources.length===0)return;
        const pos=resources[currentIdx%resources.length];
        const jx=pos[0]+rand(-30,30);
        const jy=pos[1]+rand(-30,30);
        
        // State update
        window._ws.send(JSON.stringify({t:'state',x:jx,y:jy,moving:false,facing:1,boat:false,bd:window._antiBan.facing,vcx:jx,vcy:jy,vr:734}));
        
        // Random attack count: 1-3 hits
        const hits=rand(1,3);
        for(let i=0;i<hits;i++){
          window._ws.send(JSON.stringify({t:'attack'}));
        }
        window._antiBan.totalAttacks+=hits;
        window._antiBan.lastActivity=Date.now();
      }catch(e){}
      
      // Next attack with jitter: 40-80ms base
      const delay=jitter(60,0.4); // ~40-80ms
      attackLoop=setTimeout(doAttack,delay);
    }
    doAttack();
    
    // Cycle resources with randomized timing
    function doCycle(){
      currentIdx++;
      const resources=window._getResourceList();
      if(resources.length>0){
        const pos=resources[currentIdx%resources.length];
        window._humanMoveTo(pos[0],pos[1]);
      }
      // Next cycle: 1.5-3.5s random
      cycleLoop=setTimeout(doCycle,rand(1500,3500));
    }
    cycleLoop=setTimeout(doCycle,rand(1500,3500));
    
    // Mode switch with randomized timing
    function doModeSwitch(){
      if(window._resourceMode==='tree'){
        window._resourceMode='gold';
      } else {
        window._resourceMode='tree';
      }
      currentIdx=0;
      const resources=window._getResourceList();
      if(resources.length>0) window._humanMoveTo(resources[0][0],resources[0][1]);
      // Next switch: 45-120s random
      modeLoop=setTimeout(doModeSwitch,rand(45000,120000));
    }
    modeLoop=setTimeout(doModeSwitch,rand(45000,90000));
    
    // === ANTI-BAN BEHAVIOR LOOP ===
    antiBanLoop=setTimeout(function antiBanTick(){
      const ab=window._antiBan;
      const now=Date.now();
      
      // 1. AFK simulation (pause 10-30s every 3-6 min)
      if(!ab.afkActive && now-ab.lastAfk > ab.afkInterval){
        ab.afkActive=true;
        ab.afkUntil=now+rand(10000,30000);
        ab.lastAfk=now;
        ab.afkInterval=rand(180000,360000);
        console.log('[ANTI-BAN] AFK pause for '+((ab.afkUntil-now)/1000)+'s');
      }
      if(ab.afkActive && now>=ab.afkUntil){
        ab.afkActive=false;
        console.log('[ANTI-BAN] Back from AFK');
      }
      
      // 2. Facing change (random direction every 8-20s)
      if(now-ab.lastFaceChange > ab.faceInterval){
        ab.facing=pick(ab.faces);
        ab.lastFaceChange=now;
        ab.faceInterval=rand(8000,20000);
      }
      
      // 3. Chat simulation (random message every 2-5 min)
      if(now-ab.lastMsg > ab.msgInterval && ab.messagesSent<10){
        const msg=pick(ab.chatMessages);
        if(window._ws&&window._ws.readyState===1){
          window._ws.send(JSON.stringify({t:'chat',msg:msg}));
          ab.messagesSent++;
          ab.lastMsg=now;
          ab.msgInterval=rand(120000,300000);
          console.log('[ANTI-BAN] Chat: '+msg);
        }
      }
      
      // 4. Small random movement (wander around current spot)
      if(!ab.afkActive && Math.random()<0.15){
        const resources=window._getResourceList();
        if(resources.length>0){
          const base=resources[currentIdx%resources.length];
          const wx=base[0]+rand(-200,200);
          const wy=base[1]+rand(-200,200);
          if(window._ws&&window._ws.readyState===1){
            window._ws.send(JSON.stringify({t:'state',x:wx,y:wy,moving:true,facing:1,boat:false,bd:ab.facing,vcx:wx,vcy:wy,vr:734}));
          }
        }
      }
      
      // 5. Session rotation check (reconnect every 2-4 hours)
      if(now-ab.sessionStart > ab.sessionMax){
        console.log('[ANTI-BAN] Session max reached, triggering reconnect');
        if(window._ws) window._ws.close();
        return; // stop the loop, Python will restart
      }
      
      antiBanLoop=setTimeout(antiBanTick,rand(3000,8000));
    },rand(3000,8000));
  };
  
  window._getStats=function(){
    const loots={wood:0,gold:0,meat:0};
    for(const l of window._lootLog){
      if(l.item==='wood')loots.wood++;
      else if(l.item==='gold')loots.gold++;
      else if(l.item==='meat')loots.meat++;
    }
    const ab=window._antiBan;
    return {
      loots:loots,inv:window._invData,xp:window._xpData,dead:window._dead,
      total:window._lootLog.length,wsOpen:window._wsOpen,
      mode:window._resourceMode,
      trees:window._treePositions.length,
      golds:window._goldPositions.length,
      antiBan:{
        afk:ab.afkActive,
        facing:ab.facing,
        attacks:ab.totalAttacks,
        msgs:ab.messagesSent,
        sessionAge:Math.floor((Date.now()-ab.sessionStart)/60000)+'m',
        sessionMax:Math.floor(ab.sessionMax/60000)+'m',
      },
      worldInfo:window._worldData?{
        players:window._worldData.players?.length||0,
        mobs:window._worldData.mobs?.length||0,
        treesChopped:window._worldData.trees?.length||0,
        goldHits:window._worldData.goldHits?.length||0,
        treeHits:window._worldData.treeHits?.length||0
      }:null
    };
  };
  window._resetStats=function(){window._lootLog=[];window._dead=false;};
  
  console.log('[HOOK] v20 Anti-Ban Ready: '+p58);
})();
"""

async def run_bot():
    session_duration = random.randint(7200, 14400)  # 2-4 hours
    log(f'Session target: {session_duration//60}min')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        ctx = await browser.new_context(viewport={"width":1280,"height":720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        await ctx.add_init_script(INJECT)
        page = await ctx.new_page()
        
        log(f'Loading ({addr[:12]}...)')
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
        log('=== FARMING (ANTI-BAN v20) ===')
        start = time.time()
        
        while True:
            # Randomized check interval: 55-70s
            await asyncio.sleep(random.uniform(55, 70))
            
            # Check session duration
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
                log(f'[{e/60:.1f}m] {afk_str} Mode:{mode} | T:{trees} G:{golds} | Loot W:{loots.get("wood")} G:{loots.get("gold")} M:{loots.get("meat")} | Inv W:{inv.get("wood")} G:{inv.get("gold")} M:{inv.get("meat")} | Lv:{xp.get("level")} Atk:{ab.get("attacks")} Msg:{ab.get("msgs")}')
                
                if stats.get('dead'):
                    log('DIED! Reviving...')
                    await asyncio.sleep(random.uniform(0.5, 2.0))
                    await page.evaluate('()=>window._sendCmd({t:"revive"})')
                
                if xp.get('free', 0) > 0:
                    await asyncio.sleep(random.uniform(0.2, 0.8))
                    await page.evaluate('()=>window._sendCmd({t:"allocate",stat:"str"})')
                    log('Allocated STR')
                
                with open(STATE_FILE, 'w') as f: json.dump(stats, f, indent=2)
                await page.screenshot(path='/root/islands-bot/farm_v20.png')
            except Exception as e:
                log(f'Read err: {e}')
        
        await browser.close()

async def main():
    while True:
        try: 
            await run_bot()
        except Exception as e: 
            log(f'FATAL: {e}\n{traceback.format_exc()}')
        
        # Randomized restart delay: 20-60s (looks like natural reconnect)
        delay = random.uniform(20, 60)
        log(f'Restart in {delay:.0f}s...')
        await asyncio.sleep(delay)

if __name__ == '__main__':
    asyncio.run(main())

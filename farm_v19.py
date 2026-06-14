#!/usr/bin/env python3
"""Islands Farm Bot v19 — Dynamic tree + gold farming.
Auto-detects resources from world data. Cycles trees and golds.
"""
import asyncio, json, time, sys, os, traceback
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
  
  const OrigWS=window.WebSocket;
  window._ws=null;window._wsOpen=false;
  window._lootLog=[];window._invData={meat:0,gold:0,wood:0};
  window._xpData={level:1,str:0,free:0};window._dead=false;
  window._worldData=null;
  window._treePositions=[];  // dynamic from world data
  window._goldPositions=[];  // dynamic from world data
  window._resourceMode='tree'; // 'tree' or 'gold'
  
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
          // Auto-detect tree positions from treeHits
          if(d.treeHits){
            const newTrees=[];
            for(const th of d.treeHits){
              const key=th.x+','+th.y;
              // Deduplicate
              let found=false;
              for(const t of window._treePositions){if(t[0]===th.x&&t[1]===th.y){found=true;break;}}
              if(!found) newTrees.push([th.x,th.y]);
            }
            if(newTrees.length>0) window._treePositions=window._treePositions.concat(newTrees);
          }
          // Auto-detect gold positions from goldHits or golds
          if(d.goldHits){
            const newGolds=[];
            for(const gh of d.goldHits){
              let found=false;
              for(const g of window._goldPositions){if(g[0]===gh.x&&g[1]===gh.y){found=true;break;}}
              if(!found) newGolds.push([gh.x,gh.y]);
            }
            if(newGolds.length>0) window._goldPositions=window._goldPositions.concat(newGolds);
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
  
  // Fallback hardcoded positions (from initial exploration)
  const TREE_FALLBACK=[
    [23680,16000],[23040,16000],[24256,16000],
    [23680,15232],[23040,15232],[24256,15232],
    [23680,16448],[23040,16448],[24256,16448],
    [23360,16000],[23680,14656],[24000,16000],
    [23360,15232],[23680,15680],[24000,15232],
    [23360,16448],[24000,16448],[24256,14656],
  ];
  // Gold positions from world exploration (tile*64)
  const GOLD_FALLBACK=[
    [18112,20352],[18816,20544],[19072,20096],[19968,20992],
    [19200,19968],[19904,19904],[19904,19840],[19392,20096],
    [19712,20480],[18432,20672],
  ];
  
  // Initialize with fallbacks
  window._treePositions=[...TREE_FALLBACK];
  window._goldPositions=[...GOLD_FALLBACK];
  
  let attackInterval=null;
  let currentIdx=0;
  let modeSwitchTimer=null;
  
  // Get current resource list based on mode
  window._getResourceList=function(){
    if(window._resourceMode==='gold'){
      return window._goldPositions.length>0 ? window._goldPositions : GOLD_FALLBACK;
    }
    return window._treePositions.length>0 ? window._treePositions : TREE_FALLBACK;
  };
  
  window._startAttack=function(){
    if(attackInterval)return;
    
    // Start with trees
    window._resourceMode='tree';
    currentIdx=0;
    
    const startPos=window._getResourceList()[0];
    window._moveTo(startPos[0],startPos[1]);
    
    // Main attack loop - 50ms
    attackInterval=setInterval(function(){
      if(!window._ws||window._ws.readyState!==1)return;
      try{
        const resources=window._getResourceList();
        if(resources.length===0)return;
        const pos=resources[currentIdx%resources.length];
        const msg=JSON.stringify({t:'state',x:pos[0],y:pos[1],moving:false,facing:1,boat:false,bd:'down',vcx:pos[0],vcy:pos[1],vr:734});
        window._ws.send(msg);
        window._ws.send(JSON.stringify({t:'attack'}));
        window._ws.send(JSON.stringify({t:'attack'}));
      }catch(e){}
    },50);
    
    // Cycle resources every 1.5s
    setInterval(function(){
      currentIdx++;
      const resources=window._getResourceList();
      if(resources.length>0){
        const pos=resources[currentIdx%resources.length];
        window._moveTo(pos[0],pos[1]);
      }
    },1500);
    
    // Switch between tree/gold every 60 seconds
    modeSwitchTimer=setInterval(function(){
      if(window._resourceMode==='tree'){
        window._resourceMode='gold';
        currentIdx=0;
        const golds=window._goldPositions.length>0?window._goldPositions:GOLD_FALLBACK;
        if(golds.length>0) window._moveTo(golds[0][0],golds[0][1]);
      } else {
        window._resourceMode='tree';
        currentIdx=0;
        const trees=window._treePositions.length>0?window._treePositions:TREE_FALLBACK;
        if(trees.length>0) window._moveTo(trees[0][0],trees[0][1]);
      }
    },60000);
  };
  
  window._moveTo=function(x,y){
    if(!window._ws||window._ws.readyState!==1)return;
    try{window._ws.send(JSON.stringify({t:'state',x:x,y:y,moving:true,facing:1,boat:false,bd:'down',vcx:x,vcy:y,vr:734}));}catch(e){}
  };
  
  window._sendCmd=function(msg){
    if(!window._ws||window._ws.readyState!==1)return;
    try{window._ws.send(JSON.stringify(msg));}catch(e){}
  };
  
  window._getStats=function(){
    const loots={wood:0,gold:0,meat:0};
    for(const l of window._lootLog){
      if(l.item==='wood')loots.wood++;
      else if(l.item==='gold')loots.gold++;
      else if(l.item==='meat')loots.meat++;
    }
    
    return {
      loots:loots,inv:window._invData,xp:window._xpData,dead:window._dead,
      total:window._lootLog.length,wsOpen:window._wsOpen,
      mode:window._resourceMode,
      trees:window._treePositions.length,
      golds:window._goldPositions.length,
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
  
  console.log('[HOOK] v19 Ready (tree+gold): '+p58);
})();
"""

async def run_bot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        ctx = await browser.new_context(viewport={"width":1280,"height":720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        await ctx.add_init_script(INJECT)
        page = await ctx.new_page()
        
        log(f'Loading ({addr[:12]}...)')
        await page.goto('https://islands.games', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        await page.locator('button:has-text("Connect Wallet")').first.click()
        log('Connecting...')
        await page.wait_for_timeout(12000)
        
        for _ in range(15):
            try:
                for t in ["Let's go","Next","Got it","OK","Finish"]:
                    btn = page.locator(f'button:has-text("{t}")').first
                    if await btn.is_visible(timeout=500):
                        await btn.click(); await page.wait_for_timeout(500); break
                else: break
            except: break
        try: await page.locator('button:has-text("Play")').first.click(timeout=3000)
        except: pass
        await page.wait_for_timeout(5000)
        
        await page.evaluate('''()=>{
            document.querySelectorAll('.sp-close, button[aria-label="Close"]').forEach(b=>b.click());
            document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim()==='Finish')b.click();});
        }''')
        
        for _ in range(20):
            ok = await asyncio.wait_for(page.evaluate('()=>({open:window._wsOpen,ws:!!window._ws})'), timeout=5)
            if ok.get('open'): break
            await page.wait_for_timeout(1000)
        log(f'WS: {ok}')
        
        await page.evaluate('()=>window._startAttack()')
        log('=== FARMING (TREE + GOLD) ===')
        start = time.time()
        
        while True:
            await page.wait_for_timeout(60000)
            try:
                stats = await asyncio.wait_for(page.evaluate('window._getStats()'), timeout=10)
                e = time.time() - start
                loots = stats.get('loots', {})
                inv = stats.get('inv', {})
                xp = stats.get('xp', {})
                wi = stats.get('worldInfo', {})
                mode = stats.get('mode', '?')
                trees = stats.get('trees', 0)
                golds = stats.get('golds', 0)
                log(f'[{e/60:.1f}m] Mode:{mode} | Trees:{trees} Golds:{golds} | Loot: W:{loots.get("wood")} G:{loots.get("gold")} M:{loots.get("meat")} | Inv: W:{inv.get("wood")} G:{inv.get("gold")} M:{inv.get("meat")} | Lv:{xp.get("level")} Free:{xp.get("free")}')
                if wi:
                    log(f'  World: players={wi.get("players")} mobs={wi.get("mobs")} treeHits={wi.get("treeHits")} goldHits={wi.get("goldHits")}')
                
                if stats.get('dead'):
                    log('DIED!')
                    await page.evaluate('()=>window._sendCmd({t:"revive"})')
                
                if xp.get('free', 0) > 0:
                    await page.evaluate('()=>window._sendCmd({t:"allocate",stat:"str"})')
                    log('Allocated STR')
                
                with open(STATE_FILE, 'w') as f: json.dump(stats, f, indent=2)
                await page.screenshot(path='/root/islands-bot/farm_v19.png')
            except Exception as e:
                log(f'Read err: {e}')
        
        await browser.close()

async def main():
    while True:
        try: await run_bot()
        except Exception as e: log(f'FATAL: {e}\n{traceback.format_exc()}')
        log('Restart 30s...')
        await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(main())

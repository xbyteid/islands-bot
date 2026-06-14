javascript:void(function(){
  if(window.__farmBot){console.log('Bot already running!');return;}
  
  window.__farmBot = {
    attacks: 0,
    allocs: 0,
    running: true,
    interval: null,
    stateInterval: null,
    statusInterval: null
  };
  
  var b = window.__farmBot;
  
  // Find the game's WS by hooking send
  var origSend = WebSocket.prototype.send;
  b.ws = null;
  
  WebSocket.prototype.send = function(data) {
    if (!b.ws && this.readyState === WebSocket.OPEN) {
      b.ws = this;
      console.log('[FARM] WS captured!');
      
      // Monitor messages for XP/inv updates
      this.addEventListener('message', function(e) {
        try {
          var d = JSON.parse(e.data);
          if (d.t === 'xp') {
            b.xp = d;
            if (d.free > 0) {
              console.log('[FARM] ' + d.free + ' free points -> allocating STR');
              for (var i = 0; i < d.free; i++) {
                setTimeout(function(){send({t:'allocate',stat:'str'});}, i*300);
                b.allocs++;
              }
            }
          }
          if (d.t === 'inv') b.inv = d;
          if (d.t === 'stats') b.stats = d;
          if (d.t === 'death') {
            console.log('[FARM] DIED! Reviving...');
            send({t:'revive'});
          }
        } catch(ex) {}
      });
    }
    return origSend.call(this, data);
  };
  
  function send(msg) {
    if (b.ws && b.ws.readyState === WebSocket.OPEN) {
      b.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }
  
  // Auto-attack every 1s
  b.interval = setInterval(function() {
    if (!b.running) return;
    if (send({t:'attack'})) b.attacks++;
  }, 1000);
  
  // Keep-alive state every 200ms
  b.stateInterval = setInterval(function() {
    if (!b.running) return;
    send({t:'state',x:0,y:0,moving:false,facing:'down'});
  }, 200);
  
  // Status every 5 min
  b.statusInterval = setInterval(function() {
    var xp = b.xp || {};
    var inv = b.inv || {};
    var stats = b.stats || {};
    console.log('[FARM] Lv' + (xp.level||'?') + ' STR:' + (xp.str||0) + ' Free:' + (xp.free||0) + ' Atk:' + b.attacks + ' Alloc:' + b.allocs + ' Kills:' + (stats.mobKills||0));
    console.log('[FARM] Meat:' + (inv.meat||0) + ' Wood:' + (inv.wood||0) + ' Gold:' + (inv.gold||0) + ' USDC:' + (inv.usdc||0));
  }, 300000);
  
  console.log('[FARM] Bot started! Auto-attack + auto-STR');
  console.log('[FARM] Stop: window.__farmBot.running=false');
  console.log('[FARM] Start: window.__farmBot.running=true');
  
  // Inject status bar
  var bar = document.createElement('div');
  bar.id = 'farm-status';
  bar.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#000;color:#0f0;padding:5px 10px;font:12px monospace;z-index:99999;text-align:center;';
  bar.textContent = 'FARM BOT: ON | Atk: 0 | Alloc: 0';
  document.body.appendChild(bar);
  
  setInterval(function(){
    if(bar) bar.textContent = 'FARM BOT: ' + (b.running?'ON':'OFF') + ' | Atk:' + b.attacks + ' | Alloc:' + b.allocs;
  }, 1000);
  
})();

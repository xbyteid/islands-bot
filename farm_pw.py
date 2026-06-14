#!/usr/bin/env python3
"""Islands Farming Bot v9 — Playwright-based with WS interception
Uses browser's own WS connection (game JS handles auth/WS natively).
Injects JS to control character and monitor game state.
"""

import os, sys, json, time, random, string, signal, logging
from datetime import datetime
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('farm')

GAME_URL = "https://islands.games/"
SCREENSHOT_DIR = "/root/islands-bot/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Graceful shutdown
running = True
def handle_sig(sig, frame):
    global running
    log.info("Shutdown signal received")
    running = False
signal.signal(signal.SIGTERM, handle_sig)
signal.signal(signal.SIGINT, handle_sig)


class IslandsFarmBot:
    def __init__(self):
        self.browser = None
        self.page = None
        self.ctx = None
        self.ws = None
        self.state = {
            'name': '', 'lv': 1, 'hp': 10, 'max_hp': 10,
            'xp': 0, 'next_xp': 0, 'str': 0,
            'x': 0, 'y': 0,
            'inv': [], 'gold': 0, 'trees_chopped': 0,
            'attacks': 0, 'loot_found': 0, 'errors': 0,
            'start_time': time.time(),
        }
        self.ws_messages = []
        self.tutorial_done = False

    def start(self):
        """Launch browser and load game"""
        log.info("Starting browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.ctx = self.browser.new_context(viewport={"width": 1280, "height": 720})
        self.page = self.ctx.new_page()

        # Track WS connections
        def on_ws(ws):
            log.info(f"WS connected: {ws.url}")
            self.ws = ws
            def on_recv(data):
                self._handle_ws_msg(data, 'recv')
            def on_sent(data):
                self._handle_ws_msg(data, 'send')
            ws.on("framereceived", on_recv)
            ws.on("framesent", on_sent)
            ws.on("close", lambda: log.warning("WS CLOSED!"))
        self.page.on("websocket", on_ws)

        # Inject game control JS after page load
        self.page.add_init_script("""
            // Override attack to capture responses
            window.__farmState = { attacks: 0, msgs: [], lastAttack: null };
        """)

        log.info("Loading game...")
        self.page.goto(GAME_URL, timeout=30000)
        self.page.wait_for_timeout(3000)
        log.info(f"Page title: {self.page.title()}")

    def login_guest(self):
        """Login as guest player"""
        import random, string
        suffix = ''.join(random.choices(string.digits, k=4))
        name = f"xbyte{suffix}"
        self.state['name'] = name
        log.info(f"Logging in as guest: {name}")

        # Click "Set sail as guest"
        try:
            self.page.get_by_text("Set sail as guest").click(timeout=5000)
            self.page.wait_for_timeout(1500)
        except:
            log.warning("Guest button not found, might already be in game")
            return True

        # Type name
        try:
            inp = self.page.get_by_placeholder("e.g. Captain Reef")
            inp.fill(name, timeout=5000)
            self.page.wait_for_timeout(500)
        except:
            log.warning("Name input not found")
            return False

        # Click "Set sail"
        try:
            self.page.get_by_text("Set sail", exact=True).click(timeout=5000)
            log.info("Clicked Set sail, waiting for game...")
            self.page.wait_for_timeout(10000)
        except:
            log.warning("Set sail button not found")
            return False

        return True

    def do_tutorial(self):
        """Complete the tutorial if present"""
        log.info("Checking for tutorial...")
        for attempt in range(20):
            try:
                # Look for tutorial buttons
                for btn_text in ["Let's go", "Next", "Finish", "Close", "Done", "OK"]:
                    btn = self.page.get_by_text(btn_text, exact=True)
                    if btn.is_visible(timeout=500):
                        log.info(f"Tutorial: clicking '{btn_text}'")
                        btn.click()
                        self.page.wait_for_timeout(1500)
                        break
                else:
                    # Check if tutorial is gone
                    tutorial = self.page.query_selector('.tutorial, .dialog, .modal, [class*="tutorial"]')
                    if not tutorial:
                        self.tutorial_done = True
                        log.info("Tutorial complete!")
                        return True
            except:
                pass
            self.page.wait_for_timeout(1000)

        self.tutorial_done = True
        log.info("Tutorial attempts exhausted, proceeding...")
        return True

    def _handle_ws_msg(self, data, direction):
        """Process WS messages"""
        try:
            s = str(data)
            self.ws_messages.append((direction, s, time.time()))

            # Keep only last 100 messages
            if len(self.ws_messages) > 100:
                self.ws_messages = self.ws_messages[-50:]

            if direction == 'recv':
                try:
                    msg = json.loads(s)
                    t = msg.get('t', '')

                    if t == 'welcome':
                        you = msg.get('you', {})
                        self.state['lv'] = you.get('lv', 1)
                        self.state['hp'] = you.get('hp', 10)
                        self.state['str'] = you.get('str', 0)
                        self.state['xp'] = you.get('xp', 0)
                        self.state['next_xp'] = you.get('nextXp', 0)
                        loc = you.get('loc', {})
                        self.state['x'] = loc.get('x', 0)
                        self.state['y'] = loc.get('y', 0)
                        self.state['inv'] = you.get('inv', [])
                        log.info(f"Welcome! Lv{self.state['lv']} HP={self.state['hp']} STR={self.state['str']} @ ({self.state['x']},{self.state['y']})")

                    elif t == 'anim':
                        anim = msg.get('anim', '')
                        if anim == 'chop':
                            self.state['trees_chopped'] += 1
                            log.info(f"Chop! #{self.state['trees_chopped']}")

                    elif t == 'inv':
                        self.state['inv'] = msg.get('inv', [])
                        self.state['loot_found'] += 1
                        log.info(f"Inventory update: {self.state['inv']}")

                    elif t == 'xp':
                        self.state['xp'] = msg.get('xp', 0)
                        self.state['next_xp'] = msg.get('nextXp', 0)
                        log.info(f"XP: {self.state['xp']}/{self.state['next_xp']}")

                    elif t == 'hp':
                        self.state['hp'] = msg.get('hp', 0)
                        self.state['max_hp'] = msg.get('max', self.state['max_hp'])

                    elif t == 'gold':
                        self.state['gold'] = msg.get('gold', 0)
                        log.info(f"Gold: {self.state['gold']}")

                    elif t == 'damage':
                        log.info(f"Damage: {json.dumps(msg)[:100]}")

                    elif t == 'death':
                        log.info(f"Death: {json.dumps(msg)[:100]}")

                    elif t == 'pos':
                        self.state['x'] = msg.get('x', self.state['x'])
                        self.state['y'] = msg.get('y', self.state['y'])

                    elif t == 'level':
                        self.state['lv'] = msg.get('lv', self.state['lv'])
                        log.info(f"LEVEL UP! Lv{self.state['lv']}")

                    elif t == 'str':
                        self.state['str'] = msg.get('str', self.state['str'])
                        log.info(f"STR: {self.state['str']}")

                    elif t == 'error':
                        log.warning(f"Server error: {msg.get('msg', s[:100])}")
                        self.state['errors'] += 1

                except json.JSONDecodeError:
                    pass
        except:
            pass

    def send_ws(self, msg_dict):
        """Send message through game's WS via browser JS"""
        try:
            msg_json = json.dumps(msg_dict)
            self.page.evaluate(f"""
                () => {{
                    // Find the game's WS connection
                    const ws = window.__gameWs || null;
                    if (ws && ws.readyState === 1) {{
                        ws.send('{msg_json}');
                        return true;
                    }}
                    return false;
                }}
            """)
            return True
        except Exception as e:
            log.warning(f"WS send failed: {e}")
            return False

    def attack(self):
        """Send attack command via game JS"""
        try:
            # Try clicking on nearby trees/resources with game's own click handler
            result = self.page.evaluate("""
                () => {
                    // Method 1: Direct WS send if we captured it
                    if (window.__gameWs && window.__gameWs.readyState === 1) {
                        window.__gameWs.send(JSON.stringify({t: 'attack'}));
                        return 'ws_direct';
                    }
                    // Method 2: Keyboard attack (space bar or click)
                    document.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', code: 'Space'}));
                    document.dispatchEvent(new KeyboardEvent('keyup', {key: ' ', code: 'Space'}));
                    return 'keyboard';
                }
            """)
            self.state['attacks'] += 1
            return result
        except Exception as e:
            log.warning(f"Attack failed: {e}")
            return None

    def move_to(self, x, y):
        """Move character to position"""
        try:
            self.page.evaluate(f"""
                () => {{
                    if (window.__gameWs && window.__gameWs.readyState === 1) {{
                        window.__gameWs.send(JSON.stringify({{t: 'move', path: [[{x}, {y}]]}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            return True
        except:
            return False

    def capture_game_ws(self):
        """Try to capture the game's WS object from browser context"""
        try:
            result = self.page.evaluate("""
                () => {
                    // Look for WS in various places
                    // SvelteKit might store it in component state
                    
                    // Method 1: Check if we injected it earlier
                    if (window.__gameWs) return 'found_injected';
                    
                    // Method 2: Monkey-patch WebSocket to capture next connection
                    if (!window.__wsCaptured) {
                        const OrigWS = window.WebSocket;
                        window.WebSocket = function(...args) {
                            const ws = new OrigWS(...args);
                            window.__gameWs = ws;
                            console.log('[FARM] Captured WS:', args[0]);
                            return ws;
                        };
                        window.WebSocket.prototype = OrigWS.prototype;
                        window.__wsCaptured = true;
                        return 'patched';
                    }
                    
                    return 'already_patched';
                }
            """)
            log.info(f"WS capture: {result}")
            return result
        except Exception as e:
            log.warning(f"WS capture failed: {e}")
            return None

    def inject_game_hooks(self):
        """Inject hooks to capture game's WS and state"""
        try:
            self.page.evaluate("""
                () => {
                    // Capture WS by monkey-patching
                    const OrigWS = window.WebSocket;
                    window.__gameWs = null;
                    window.WebSocket = function(...args) {
                        const ws = new OrigWS(...args);
                        window.__gameWs = ws;
                        
                        // Log all messages
                        const origOnMsg = ws.onmessage;
                        ws.addEventListener('message', (e) => {
                            try {
                                const d = JSON.parse(e.data);
                                if (d.t === 'welcome') window.__welcome = d;
                                if (d.t === 'inv') window.__inv = d;
                                if (d.t === 'xp') window.__xp = d;
                                if (d.t === 'gold') window.__gold = d;
                            } catch(ex) {}
                        });
                        
                        console.log('[FARM] WS captured!');
                        return ws;
                    };
                    window.WebSocket.prototype = OrigWS.prototype;
                    
                    // Also try to capture existing WS via XMLHttpRequest proxy
                    // (some games store WS in closures)
                    console.log('[FARM] Hooks installed');
                }
            """)
            log.info("Game hooks injected")
        except Exception as e:
            log.warning(f"Hook injection failed: {e}")

    def get_game_state(self):
        """Get game state from browser"""
        try:
            state = self.page.evaluate("""
                () => {
                    return {
                        wsReady: window.__gameWs ? window.__gameWs.readyState : -1,
                        welcome: window.__welcome || null,
                        inv: window.__inv || null,
                        xp: window.__xp || null,
                        gold: window.__gold || null,
                    };
                }
            """)
            return state
        except:
            return None

    def screenshot(self, name=None):
        """Take screenshot"""
        if not name:
            name = f"farm_{int(time.time())}"
        path = f"{SCREENSHOT_DIR}/{name}.png"
        try:
            self.page.screenshot(path=path)
            return path
        except:
            return None

    def status_report(self):
        """Generate status report"""
        elapsed = time.time() - self.state['start_time']
        mins = elapsed / 60
        return (
            f"🎮 Islands Bot Status\n"
            f"👤 {self.state['name']} Lv{self.state['lv']}\n"
            f"❤️ HP: {self.state['hp']}/{self.state['max_hp']}\n"
            f"⚔️ STR: {self.state['str']}\n"
            f"📊 XP: {self.state['xp']}/{self.state['next_xp']}\n"
            f"🪓 Attacks: {self.state['attacks']} | Trees: {self.state['trees_chopped']}\n"
            f"🎒 Loot: {self.state['loot_found']} | Gold: {self.state['gold']}\n"
            f"📍 Pos: ({self.state['x']},{self.state['y']})\n"
            f"❌ Errors: {self.state['errors']}\n"
            f"⏱️ Uptime: {mins:.1f} min\n"
            f"📡 WS: {'connected' if self.ws else 'disconnected'}"
        )

    def run_farm_loop(self):
        """Main farming loop"""
        log.info("Starting farm loop...")
        cycle = 0
        last_status = time.time()
        last_screenshot = time.time()

        while running:
            try:
                cycle += 1

                # Check if WS is still alive
                ws_state = self.page.evaluate("() => window.__gameWs ? window.__gameWs.readyState : -1")
                if ws_state != 1:
                    log.warning(f"WS state: {ws_state}, attempting reconnect...")
                    self.page.reload(timeout=30000)
                    self.page.wait_for_timeout(5000)
                    self.inject_game_hooks()
                    self.page.wait_for_timeout(3000)
                    # Re-login if needed
                    try:
                        guest_btn = self.page.get_by_text("Set sail as guest")
                        if guest_btn.is_visible(timeout=2000):
                            self.login_guest()
                            self.page.wait_for_timeout(5000)
                    except:
                        pass
                    continue

                # Attack
                result = self.attack()
                if cycle % 10 == 0:
                    log.info(f"Cycle {cycle}: attack={result}, attacks={self.state['attacks']}")

                # Status report every 5 min
                if time.time() - last_status > 300:
                    log.info(self.status_report())
                    last_status = time.time()

                # Screenshot every 10 min
                if time.time() - last_screenshot > 600:
                    self.screenshot(f"farm_{cycle}")
                    last_screenshot = time.time()

                # Random delay between attacks (1-3 sec)
                time.sleep(random.uniform(1, 3))

            except Exception as e:
                log.error(f"Farm loop error: {e}")
                self.state['errors'] += 1
                time.sleep(5)

    def stop(self):
        """Clean shutdown"""
        log.info("Stopping bot...")
        self.screenshot("final")
        log.info(self.status_report())
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass


def main():
    bot = IslandsFarmBot()
    try:
        bot.start()

        # Step 1: Inject WS capture hooks BEFORE game connects
        bot.inject_game_hooks()

        # Step 2: Login as guest
        if not bot.login_guest():
            log.error("Login failed!")
            bot.screenshot("login_fail")
            bot.stop()
            return

        # Step 3: Wait for WS to be captured
        log.info("Waiting for WS capture...")
        for i in range(30):
            ws_state = bot.get_game_state()
            if ws_state and ws_state.get('wsReady') == 1:
                log.info("WS captured and ready!")
                break
            time.sleep(1)
        else:
            log.warning("WS not captured, continuing anyway...")

        # Step 4: Complete tutorial
        bot.do_tutorial()
        bot.page.wait_for_timeout(3000)

        # Step 5: Screenshot initial state
        bot.screenshot("game_start")
        log.info(f"Game started! State: {json.dumps(bot.state, indent=2)}")

        # Step 6: Run farming loop
        bot.run_farm_loop()

    except KeyboardInterrupt:
        log.info("Interrupted by user")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bot.stop()


if __name__ == "__main__":
    main()

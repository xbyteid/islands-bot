# Islands Farm Bot v20 🏝️

Automated farming bot for [islands.games](https://islands.games) — headless Playwright-based with anti-ban system.

## Features

- 🌲 **Tree + Gold farming** — auto-detects resources from world data, cycles between them
- 🛡️ **Anti-ban system** — randomized timing, humanized movement, AFK simulation, chat messages
- ⚔️ **Auto-attack** — randomized 1-3 hits per tick with position jitter
- 📊 **Auto-allocate** — STR stat points on level up
- 💀 **Auto-revive** — instant revive on death
- 🔄 **Session rotation** — reconnects every 2-4 hours with random delays
- 🎯 **Dynamic resource detection** — finds trees/golds from server world data

## Anti-Ban Details

| Feature | Details |
|---------|---------|
| Attack timing | 40-80ms randomized (not fixed) |
| Resource cycle | 1.5-3.5s random interval |
| Mode switch | 45-120s random (tree ↔ gold) |
| AFK simulation | 10-30s pause every 3-6 min |
| Movement | Step-by-step walking + position jitter |
| Chat | Random messages every 2-5 min |
| Facing | Random direction changes |
| Session | 2-4h rotation with 20-60s reconnect delay |

## Requirements

- Python 3.10+
- Playwright (`pip install playwright && playwright install chromium`)
- Phantom wallet private key (Solana)

## Setup

1. Clone the repo
2. Place your wallet JSON at `~/.hermes/profiles/alon/vault/wallets/solana_main.json`
3. Ensure `tweetnacl.min.js` is in the same directory
4. Run: `python3 farm.py`

## Wallet Format

```json
{
  "address": "YourSolanaAddress",
  "private_key_bytes": [1, 2, 3, ...]
}
```

## Running as Service

```bash
sudo cp islands-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now islands-bot
journalctl -u islands-bot -f
```

## How It Works

1. Launches headless Chromium via Playwright
2. Injects wallet + WebSocket hook before page loads
3. Connects wallet to islands.games
4. Intercepts game WebSocket messages (loot, inventory, xp, world data)
5. Auto-detects tree/gold positions from `world.treeHits` / `world.goldHits`
6. Sends humanized attack + movement commands via WS
7. Rotates between trees and golds every 45-120s
8. Auto-revives, allocates stats, reconnects on session timeout

## Disclaimer

For educational purposes only. Use at your own risk. Bot behavior may be detected by game anti-cheat systems.

## License

MIT

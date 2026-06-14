# Islands Farm Bot v21 🏝️🔒

Automated farming bot for [islands.games](https://islands.games) — headless Playwright-based with **secure signing architecture** and anti-ban system.

## 🔒 Security (v21)

**Private key NEVER enters browser JavaScript.** All signing happens server-side in Python via `page.route()` bridge.

```
v18-v20 (INSECURE):          v21 (SECURE):
Browser JS ← full key        Browser JS ← public key only
Key in closure (leaked)      Key in Python memory only
GitHub = wallet drained      GitHub = safe (no key material)
```

- Browser only has **public key** (32 bytes = wallet address)
- `signMessage` → fetch `http://sign.local/sign` → Python signs with `nacl` → returns signature
- Even if repo leaks, attacker gets **zero key material**
- Vault file has `chmod 600` (root-only read)

## Features

- 🌲 **Tree + Gold farming** — auto-detects resources from world data, cycles between them
- 🛡️ **Anti-ban system** — randomized timing, humanized movement, AFK simulation, chat messages
- 🔒 **Secure signing** — private key in Python only, never in browser
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
- PyNaCl (`pip install pynacl`)
- Solana wallet JSON file (see below)

## Setup

1. Clone the repo
2. Install dependencies: `pip install playwright pynacl && playwright install chromium`
3. Place your wallet JSON at the path configured in `WALLET_FILE` (default: `~/.hermes/profiles/alon/vault/wallets/solana_main.json`)
4. Run: `python3 farm.py`

**⚠️ NEVER commit your wallet file to git.** The vault path is gitignored by default.

## Wallet Format

```json
{
  "address": "YourSolanaAddress",
  "private_key_bytes": [1, 2, 3, ...]
}
```

- `private_key_bytes`: 64-byte Ed25519 keypair (seed + public key)
- File must have `chmod 600` permissions

## Running as Service

```bash
sudo cp islands-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now islands-bot
journalctl -u islands-bot -f
```

## How It Works

1. Launches headless Chromium via Playwright
2. Injects **public key only** + WebSocket hook before page loads
3. Registers `page.route('http://sign.local/sign')` — Python handles all signing
4. Connects wallet to islands.games (game sees valid Phantom wallet)
5. Intercepts game WebSocket messages (loot, inventory, xp, world data)
6. Auto-detects tree/gold positions from `world.treeHits` / `world.goldHits`
7. Sends humanized attack + movement commands via WS
8. Rotates between trees and golds every 45-120s
9. Auto-revives, allocates stats, reconnects on session timeout

## Architecture

```
┌─────────────────────────────────────────┐
│  Python Process                         │
│  ┌─────────────────────────────────┐    │
│  │ Private Key (nacl.SigningKey)   │    │
│  │ NEVER exported to JS            │    │
│  └──────────┬──────────────────────┘    │
│             │ page.route() bridge       │
│  ┌──────────▼──────────────────────┐    │
│  │ POST http://sign.local/sign     │    │
│  │ {message: base64} → {signature} │    │
│  └──────────┬──────────────────────┘    │
│             │                           │
│  ┌──────────▼──────────────────────┐    │
│  │ Playwright Browser              │    │
│  │ • Public key only               │    │
│  │ • WebSocket hook                │    │
│  │ • Anti-ban behavior             │    │
│  │ • Game farming logic            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Changelog

- **v21**: Secure signing architecture — key never enters browser JS
- **v20**: Anti-ban system (randomized timing, AFK, chat, session rotation)
- **v19**: Dynamic tree + gold detection from world data
- **v18**: Tree-targeting attack loop with auto-allocate

## Disclaimer

For educational purposes only. Use at your own risk. Bot behavior may be detected by game anti-cheat systems.

## License

MIT

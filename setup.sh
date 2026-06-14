#!/bin/bash
# Islands Farm Bot — Termux Setup
# Run this once: bash setup.sh

echo "=== Installing Node.js ==="
pkg install nodejs -y

echo "=== Installing ws module ==="
npm install ws

echo "=== Downloading bot ==="
cd ~
# If farm.mjs is in downloads:
if [ -f ~/storage/downloads/farm.mjs ]; then
  cp ~/storage/downloads/farm.mjs ~/farm.mjs
fi

echo "=== Done! Run: node ~/farm.mjs ==="

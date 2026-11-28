#!/bin/bash
# Serapi macOS launcher (development / unpacked build).
# Double-click in Finder or run from a terminal.
set -u
cd "$(dirname "$0")/electron" || exit 1

BIN_DIR="dist/mac-arm64"
if [ ! -x "$BIN_DIR/Serapi.app/Contents/MacOS/Serapi" ]; then
  echo "Electron build not found:"
  echo "  $PWD/$BIN_DIR/Serapi.app"
  echo "Run: cd electron && npm run dist:mac:dir"
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "Installing dependencies (first run)..."
  npm ci --no-audit --no-fund || exit 1
fi

exec "$BIN_DIR/Serapi.app/Contents/MacOS/Serapi"

#!/bin/bash

echo "================================================"
echo "  Starting Shiny Hunter Frontend Dashboard"
echo "================================================"
echo ""

cd "$(dirname "$0")"

if [ ! -d "node_modules" ]; then
    echo "[ERROR] Dependencies not installed!"
    echo "[INFO] Run 'npm install' first"
    exit 1
fi

echo "[INFO] Starting Vite dev server on http://localhost:3000"
echo "[INFO] Press Ctrl+C to stop"
echo ""

npm run dev

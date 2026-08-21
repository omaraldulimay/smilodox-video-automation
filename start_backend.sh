#!/bin/bash
# Starts the backend with DATA_ROOT pointed at the team's Shared Drive
# (state.db, uploads/, output/, manifests/, reference-images/ all live there
# so the whole team sees the same data via Drive sync).
set -e
cd "$(dirname "$0")"

export DATA_ROOT="/path/to/project Ablagen/Smilodox Video Automation"

pkill -f "uvicorn backend.main:app" 2>/dev/null || true
sleep 1

exec .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

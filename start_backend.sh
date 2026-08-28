#!/bin/bash
# Starts the backend with DATA_ROOT pointed at the team's Shared Drive --
# output/ and reference-images/ live there so the whole team sees them via
# Drive sync. state.db/uploads/manifests/brand_assets live locally instead
# (internal_data/, see backend/config.py) -- kept out of the Shared Drive on
# purpose, both to keep its root clean and to avoid Drive trying to sync an
# actively-written SQLite file.
set -e
cd "$(dirname "$0")"

export DATA_ROOT="/path/to/project Ablagen/Smilodox Video Automation"

pkill -f "uvicorn backend.main:app" 2>/dev/null || true
sleep 1

exec .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

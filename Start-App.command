#!/bin/bash
# ============================================================
# AD-Depth Vision Universal Direct Launcher
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Free port 8000 if occupied
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Clear Gatekeeper
xattr -cr "$DIR" 2>/dev/null || true

# Activate venv if present
if [ -f "backend/venv/bin/activate" ]; then
    source backend/venv/bin/activate
fi

# Run backend python runner
python3 backend/run.py

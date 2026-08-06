#!/bin/bash
# ============================================================
#  AD-Depth Vision — Universal Mac Launcher
#  Handles: venv setup, dependency install, port binding,
#  health-check, and browser auto-open.
#
#  Usage:  bash run.sh
#  This script bypasses Gatekeeper because you invoke bash
#  directly — no .command / .app double-click needed.
# ============================================================

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       🔮  AD-Depth Vision  —  Universal Launcher ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 0: Remove macOS quarantine flags ────────────────────
echo -e "${YELLOW}[0/7]${NC} Clearing macOS quarantine flags..."
xattr -cr "$SCRIPT_DIR" 2>/dev/null || true
echo -e "${GREEN}  ✅ Quarantine flags cleared.${NC}"

# ── Step 1: Check Python 3 ──────────────────────────────────
echo -e "${YELLOW}[1/7]${NC} Checking Python 3..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}  ❌ Python 3 not found!${NC}"
    echo ""
    echo "  Please install Python 3 from: https://www.python.org/downloads/"
    echo "  After installing, re-run: bash run.sh"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}  ✅ Found $PY_VERSION${NC}"

# ── Step 2: Self-healing Virtual Environment ─────────────────
echo -e "${YELLOW}[2/7]${NC} Checking Python virtual environment..."

NEEDS_VENV=false
if [ ! -f "$VENV_PYTHON" ]; then
    NEEDS_VENV=true
    echo -e "  ⚙️  No venv found. Will create one."
elif ! "$VENV_PYTHON" -c "import sys; print(sys.version)" &>/dev/null; then
    NEEDS_VENV=true
    echo -e "  ⚠️  Existing venv is broken (likely from another Mac). Rebuilding..."
    rm -rf "$VENV_DIR"
fi

if [ "$NEEDS_VENV" = true ]; then
    echo -e "  ⚙️  Creating fresh virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}  ✅ Virtual environment created.${NC}"
fi

# ── Step 3: Install/verify dependencies ──────────────────────
echo -e "${YELLOW}[3/7]${NC} Checking dependencies..."

# Quick check: try importing the heaviest packages
DEPS_OK=true
"$VENV_PYTHON" -c "import fastapi, uvicorn, torch, cv2, transformers" 2>/dev/null || DEPS_OK=false

if [ "$DEPS_OK" = false ]; then
    echo -e "  📦 Installing AI packages (PyTorch, Depth Anything V2, YOLOv8)..."
    echo -e "  ☕ This may take several minutes on first run..."
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet 2>/dev/null
    "$VENV_DIR/bin/pip" install --default-timeout=300 -r "$REQUIREMENTS"
    echo -e "${GREEN}  ✅ All dependencies installed.${NC}"
else
    echo -e "${GREEN}  ✅ All dependencies already installed.${NC}"
fi

# ── Step 4: Find available port ──────────────────────────────
echo -e "${YELLOW}[4/7]${NC} Finding available port..."

PORT=0
for TRY_PORT in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010; do
    if ! lsof -i :"$TRY_PORT" &>/dev/null; then
        PORT=$TRY_PORT
        break
    fi
done

if [ "$PORT" -eq 0 ]; then
    echo -e "${RED}  ❌ No available port found (tried 8000-8010).${NC}"
    echo "  Please close other applications using these ports and try again."
    exit 1
fi
echo -e "${GREEN}  ✅ Will use port $PORT${NC}"

# ── Step 5: Start backend server ─────────────────────────────
echo -e "${YELLOW}[5/7]${NC} Starting AI backend server..."

# Kill any leftover server on this port
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true

# Export port for the Python backend to read
export AD_DEPTH_PORT="$PORT"

# Start uvicorn in background
cd "$BACKEND_DIR"
"$VENV_PYTHON" -m uvicorn main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --log-level warning &
SERVER_PID=$!

# Trap to clean up server on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down server (PID $SERVER_PID)...${NC}"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    echo -e "${GREEN}✅ Server stopped. Goodbye!${NC}"
}
trap cleanup EXIT INT TERM

echo -e "  🚀 Server starting (PID $SERVER_PID)..."

# ── Step 6: Health-check loop ────────────────────────────────
echo -e "${YELLOW}[6/7]${NC} Waiting for server to be ready..."

MAX_WAIT=30
WAITED=0
SERVER_READY=false

while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    # Check if server process is still alive
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo -e "${RED}  ❌ Server process died unexpectedly.${NC}"
        echo ""
        echo "  Common fixes:"
        echo "  1. Make sure no other app is using port $PORT"
        echo "  2. Try: bash run.sh"
        echo "  3. If problem persists, delete backend/venv and re-run"
        exit 1
    fi

    # Try to reach the health endpoint
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
        SERVER_READY=true
        break
    fi

    sleep 1
    WAITED=$((WAITED + 1))
    # Show dots for progress
    printf "  ."
done
echo ""

if [ "$SERVER_READY" = false ]; then
    echo -e "${RED}  ❌ Server did not respond within ${MAX_WAIT}s.${NC}"
    echo "  Try deleting backend/venv and re-running: bash run.sh"
    exit 1
fi

echo -e "${GREEN}  ✅ Server is live and responding!${NC}"

# ── Step 7: Open browser ────────────────────────────────────
APP_URL="http://127.0.0.1:$PORT/app/"
echo -e "${YELLOW}[7/7]${NC} Opening app in browser..."
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉  AD-Depth Vision is running!                 ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║  URL: ${CYAN}$APP_URL${GREEN}             ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop the server.                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

open "$APP_URL" 2>/dev/null || echo -e "  💡 Open manually: $APP_URL"

# Keep script alive (server runs in background)
wait "$SERVER_PID"

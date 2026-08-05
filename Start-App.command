#!/bin/bash
# ============================================================
# AD-Depth Vision Universal 1-Click Launcher for macOS
# Works on any Mac (M1/M2/M3/M4 & Intel)
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "============================================================"
echo "🔮 Starting AD-Depth Vision Server..."
echo "============================================================"

# Remove macOS Gatekeeper Quarantine flags automatically
xattr -cr "$DIR" 2>/dev/null || true

# Free port 8000 if previously occupied
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install Python 3 from https://www.python.org/downloads/"
    read -p "Press Enter to exit..."
    exit 1
fi

# Set up local venv if not initialized
if [ ! -f "backend/venv/bin/python" ] || ! "backend/venv/bin/python" -c "import sys" 2>/dev/null; then
    echo "⚙️ Preparing local Python environment for this Mac..."
    rm -rf backend/venv
    python3 -m venv backend/venv
    echo "📦 Installing required AI packages (PyTorch, Depth Anything V2, YOLOv8)..."
    backend/venv/bin/pip install --upgrade pip --quiet
    backend/venv/bin/pip install --default-timeout=1000 -r backend/requirements.txt
fi

# Open browser automatically after short delay
(sleep 2 && open "http://127.0.0.1:8000/app/") &

# Start Backend Server
source backend/venv/bin/activate
cd backend
export UPLOAD_DIR="../uploads"
export PROCESSED_DIR="../processed"
echo "🚀 AD-Depth Vision is running!"
echo "👉 Open Web App at: http://127.0.0.1:8000/app/ or http://localhost:8000/app/"
echo "============================================================"
uvicorn main:app --host 0.0.0.0 --port 8000

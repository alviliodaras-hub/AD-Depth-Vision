#!/bin/bash
# ============================================================
# AD-Depth Vision Native Desktop Launcher
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "============================================================"
echo "🔮 Starting AD-Depth Vision Native Desktop App..."
echo "============================================================"

# Free port 8000 if occupied
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Clear Gatekeeper
xattr -cr "$DIR" 2>/dev/null || true

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

# Activate venv
source backend/venv/bin/activate

# Run Desktop App Runner
python3 backend/desktop_app.py

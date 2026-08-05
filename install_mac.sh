#!/bin/bash
# ============================================================
# AD-Depth Vision Installer for macOS
# Creates a portable, self-healing app bundle for any Mac
# ============================================================

set -e

APP_NAME="AD-Depth Vision"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR/$APP_NAME.app"
CONTENTS_DIR="$INSTALL_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║      🔮 AD-Depth Vision Installer for Mac    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found."
    echo "   Install it from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Found Python $PYTHON_VERSION"

# Clean previous install
if [ -d "$INSTALL_DIR" ]; then
    echo "🗑  Removing previous installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create app structure
echo "📁 Creating app bundle structure..."
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR/backend"
mkdir -p "$RESOURCES_DIR/frontend"
mkdir -p "$RESOURCES_DIR/uploads"
mkdir -p "$RESOURCES_DIR/processed"

# Copy source files
echo "📋 Copying application files..."
cp "$SCRIPT_DIR/backend/"*.py "$RESOURCES_DIR/backend/"
cp "$SCRIPT_DIR/backend/requirements.txt" "$RESOURCES_DIR/backend/"
cp -r "$SCRIPT_DIR/frontend/"* "$RESOURCES_DIR/frontend/"

# Create virtual environment inside the app bundle
echo "🐍 Creating isolated Python environment..."
python3 -m venv "$RESOURCES_DIR/venv"

echo "📦 Installing dependencies (this may take a few minutes)..."
"$RESOURCES_DIR/venv/bin/pip" install --upgrade pip --quiet
"$RESOURCES_DIR/venv/bin/pip" install --default-timeout=1000 -r "$RESOURCES_DIR/backend/requirements.txt" --quiet

echo "✅ Dependencies installed successfully."

# Create self-healing launcher script inside app
cat > "$MACOS_DIR/launch.sh" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$SCRIPT_DIR/../Resources"

# Clear Gatekeeper quarantine attribute automatically
xattr -dr com.apple.quarantine "$SCRIPT_DIR/../.." 2>/dev/null || true

# Self-healing Python environment check:
# Recreates venv automatically if app is copied to another Mac or user folder
VENV_DIR="$RESOURCES/venv"
CURRENT_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$CURRENT_PYTHON" ] || ! "$CURRENT_PYTHON" -c "import sys" 2>/dev/null; then
    echo "⚙️ Initializing Python environment for this Mac..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    "$VENV_DIR/bin/pip" install --default-timeout=1000 -r "$RESOURCES/backend/requirements.txt"
fi

source "$VENV_DIR/bin/activate"

# Open browser after short delay
(sleep 3 && open "http://127.0.0.1:8000/app/") &

# Start the server
cd "$RESOURCES/backend"
export UPLOAD_DIR="$RESOURCES/uploads"
export PROCESSED_DIR="$RESOURCES/processed"
uvicorn main:app --host 127.0.0.1 --port 8000
LAUNCHER
chmod +x "$MACOS_DIR/launch.sh"

# Create main executable inside app
cat > "$MACOS_DIR/ADDepthVision" << 'EXEC'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
osascript -e "tell application \"Terminal\" to do script \"'$SCRIPT_DIR/launch.sh'\""
EXEC
chmod +x "$MACOS_DIR/ADDepthVision"

# Create 1-click launcher command at root (bypasses Gatekeeper completely)
cat > "$SCRIPT_DIR/Start-AD-Depth-Vision.command" << 'CMD'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
xattr -dr com.apple.quarantine "$DIR/AD-Depth Vision.app" 2>/dev/null || true
chmod -R +x "$DIR/AD-Depth Vision.app"
open "$DIR/AD-Depth Vision.app"
CMD
chmod +x "$SCRIPT_DIR/Start-AD-Depth-Vision.command"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AD-Depth Vision</string>
    <key>CFBundleDisplayName</key>
    <string>AD-Depth Vision</string>
    <key>CFBundleIdentifier</key>
    <string>com.addepthvision.app</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>ADDepthVision</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         ✅ Installation Complete!             ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║  App created at:                             ║"
echo "║  $INSTALL_DIR"
echo "║                                              ║"
echo "║  To run: Double-click 'AD-Depth Vision.app'  ║"
echo "║  Or double-click 'Start-AD-Depth-Vision.command'║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

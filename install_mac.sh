#!/bin/bash
# ============================================================
# AD-Depth Vision Installer for macOS
# Creates a portable, self-contained app bundle
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

# Create the launcher script
cat > "$MACOS_DIR/launch.sh" << 'LAUNCHER'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES="$SCRIPT_DIR/../Resources"

# Activate venv
source "$RESOURCES/venv/bin/activate"

# Open browser after a short delay
(sleep 3 && open "http://127.0.0.1:8000/app/") &

# Start the server
cd "$RESOURCES/backend"
export UPLOAD_DIR="$RESOURCES/uploads"
export PROCESSED_DIR="$RESOURCES/processed"
uvicorn main:app --host 127.0.0.1 --port 8000
LAUNCHER
chmod +x "$MACOS_DIR/launch.sh"

# Create the main executable
cat > "$MACOS_DIR/ADDepthVision" << 'EXEC'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
osascript -e "tell application \"Terminal\" to do script \"'$SCRIPT_DIR/launch.sh'\""
EXEC
chmod +x "$MACOS_DIR/ADDepthVision"

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
echo "║  Or drag it to your Applications folder.     ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

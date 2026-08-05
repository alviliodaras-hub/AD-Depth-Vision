#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
xattr -dr com.apple.quarantine "$DIR/AD-Depth Vision.app" 2>/dev/null || true
chmod -R +x "$DIR/AD-Depth Vision.app"
open "$DIR/AD-Depth Vision.app"

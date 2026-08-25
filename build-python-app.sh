#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"

if [[ ! -f "$SCRIPT_DIR/block-jam-3d-icon.png" ]]; then
  echo "The bundled Block Jam 3D icon is missing from this package." >&2
  exit 1
fi

python3 -m pip install --upgrade -r "$SCRIPT_DIR/requirements.txt"
rm -rf "$DIST_DIR/Build" "$DIST_DIR/Bot Player.app" "$DIST_DIR/Bot-Player-macOS.dmg"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Bot Player" \
  --osx-bundle-identifier "com.botplayer.iphone-mirroring" \
  --distpath "$DIST_DIR" \
  --workpath "$DIST_DIR/Build" \
  --add-data "$SCRIPT_DIR/block-jam-3d-icon.png:." \
  "$SCRIPT_DIR/bot_player.py"

APP_PATH="$DIST_DIR/Bot Player.app"
APP_EXECUTABLE="$APP_PATH/Contents/MacOS/Bot Player"
if [[ ! -x "$APP_EXECUTABLE" ]]; then
  echo "PyInstaller did not create a double-clickable Bot Player.app." >&2
  exit 1
fi

DMG_ROOT="$DIST_DIR/dmg-root"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R "$APP_PATH" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -volname "Bot Player" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DIST_DIR/Bot-Player-macOS.dmg"
rm -rf "$DMG_ROOT"
echo "Created $DIST_DIR/Bot-Player-macOS.dmg without an Xcode build."
echo "Double-click $APP_PATH to open the complete Bot Player app, or drag it to Applications first."
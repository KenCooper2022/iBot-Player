#!/bin/bash
#
# Bot Player — Mac double-click launcher
# Finds Python, creates a private runtime, installs dependencies, and starts
# the complete Bot Player window. No terminal command is needed from the user.
#

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clear the quarantine flag after the user has approved this launcher once.
xattr -d com.apple.quarantine "$0" 2>/dev/null || true

REBUILD_REQUESTED=false
if [[ "${1:-}" == "--rebuild" ]]; then
  REBUILD_REQUESTED=true
elif [[ -n "${1:-}" ]]; then
  echo "Usage: DOUBLE-CLICK-TO-RUN (Mac).command [--rebuild]"
  exit 2
fi

APP_PATH="$HOME/Applications/Bot Player.app"
APP_EXECUTABLE="$APP_PATH/Contents/MacOS/Bot Player"
BUILD_REVISION="2026-08-25-window-capture-tcc-repair"
APP_REVISION_FILE="$APP_PATH/Contents/Resources/bot-player-build-revision.txt"
STAGED_APP_PATH="$SCRIPT_DIR/dist/Bot Player.app"
STAGED_APP_EXECUTABLE="$STAGED_APP_PATH/Contents/MacOS/Bot Player"
STAGED_REVISION_FILE="$STAGED_APP_PATH/Contents/Resources/bot-player-build-revision.txt"

echo ""
echo "  ========================================"
echo "    Bot Player"
echo "  ========================================"
echo ""

if [[ ! -f "$SCRIPT_DIR/block-jam-3d-icon.png" ]]; then
  echo "  [ERROR] The bundled Block Jam 3D icon is missing from this package."
  read -r -p "  Re-download the complete test ZIP, then press Return to close..." _
  exit 1
fi

if [[ "$REBUILD_REQUESTED" != true && -x "$APP_EXECUTABLE" ]]; then
  if [[ ! -f "$APP_REVISION_FILE" || "$(cat "$APP_REVISION_FILE" 2>/dev/null)" != "$BUILD_REVISION" ]]; then
    echo "  The installed Bot Player.app is older than this package."
    echo "  Replacing it now ensures permissions are checked against the newest signed app."
    echo "  This can require Screen Recording and Accessibility approval again."
  else
    echo "  Opening the existing approved Bot Player.app..."
    open "$APP_PATH"
    exit 0
  fi
fi

if [[ -x "$APP_EXECUTABLE" ]]; then
  echo "  Rebuilding will replace $APP_PATH."
  echo "  The new local build must be signed with an Apple Development certificate in this Mac's keychain."
else
  echo "  Bot Player.app is not installed yet. Building it once for $APP_PATH..."
fi
echo ""

PYTHON=""

python_is_usable() {
  local candidate="$1"
  if [[ ! -x "$candidate" ]] && ! command -v "$candidate" >/dev/null 2>&1; then
    return 1
  fi
  local version major minor
  version="$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)"
  major="${version%%.*}"
  minor="${version#*.}"
  [[ "${major:-0}" -ge 3 && "${minor:-0}" -ge 10 ]]
}

find_python() {
  local candidate
  for candidate in python3 python; do
    if python_is_usable "$candidate"; then
      PYTHON="$candidate"
      return 0
    fi
  done
  for candidate in \
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "/opt/homebrew/opt/python@3.12/bin/python3" \
    "/usr/local/bin/python3" \
    "/usr/local/opt/python@3.12/bin/python3"; do
    if python_is_usable "$candidate"; then
      PYTHON="$candidate"
      return 0
    fi
  done
  return 1
}

install_python() {
  echo "  Python 3.10+ was not found."
  echo ""
  if ! command -v brew >/dev/null 2>&1; then
    echo "  Homebrew is not installed."
    echo "  The official Homebrew installer is needed to install Python automatically."
    read -r -p "  Press Return to install Homebrew, or Control-C to cancel..." _
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || return 1
    if [[ -x "/opt/homebrew/bin/brew" ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -x "/usr/local/bin/brew" ]]; then
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi

  echo "  Installing Python with Homebrew..."
  brew install python@3.12 || brew install python3 || return 1
  find_python
}

if ! find_python; then
  install_python || {
    echo ""
    echo "  Python could not be installed automatically."
    echo "  Download it from: https://www.python.org/downloads/macos/"
    read -r -p "  Press Return to close..." _
    exit 1
  }
fi

echo "  [OK] $("$PYTHON" --version 2>&1)"

VENV_DIR="$SCRIPT_DIR/.bot-player-venv"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "  Creating a private Bot Player runtime..."
  "$PYTHON" -m venv "$VENV_DIR" || {
    echo "  [ERROR] Could not create the private Python runtime."
    read -r -p "  Press Return to close..." _
    exit 1
  }
fi

VENV_PYTHON="$VENV_DIR/bin/python"
echo "  Installing or checking Bot Player packages..."
"$VENV_PYTHON" -m pip install --upgrade pip -q || {
  echo "  [ERROR] Could not prepare pip."
  read -r -p "  Press Return to close..." _
  exit 1
}
"$VENV_PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q || {
  echo "  [ERROR] Could not install Bot Player packages."
  echo "  Check your internet connection and double-click this launcher again."
  read -r -p "  Press Return to close..." _
  exit 1
}

echo "  Building the real Bot Player.app for macOS..."
rm -rf "$SCRIPT_DIR/dist/Build" "$STAGED_APP_PATH"
"$VENV_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Bot Player" \
  --osx-bundle-identifier "com.botplayer.iphone-mirroring" \
  --distpath "$SCRIPT_DIR/dist" \
  --workpath "$SCRIPT_DIR/dist/Build" \
  --add-data "$SCRIPT_DIR/block-jam-3d-icon.png:." \
  "$SCRIPT_DIR/bot_player.py" || {
    echo "  [ERROR] Could not build the Bot Player.app."
    read -r -p "  Press Return to close..." _
    exit 1
  }

if [[ ! -x "$STAGED_APP_EXECUTABLE" ]]; then
  echo "  [ERROR] Bot Player.app was not created."
  read -r -p "  Press Return to close..." _
  exit 1
fi
mkdir -p "$(dirname "$STAGED_REVISION_FILE")"
printf '%s\n' "$BUILD_REVISION" > "$STAGED_REVISION_FILE"
bash "$SCRIPT_DIR/sign-macos-app.sh" "$STAGED_APP_PATH" development || {
  echo "  [ERROR] Bot Player.app was not signed. The installed app was left unchanged."
  read -r -p "  Press Return to close..." _
  exit 1
}

INSTALL_DIRECTORY="$(dirname "$APP_PATH")"
INSTALL_STAGING_PATH="$INSTALL_DIRECTORY/.Bot Player.app.installing"
INSTALL_BACKUP_PATH="$INSTALL_DIRECTORY/.Bot Player.app.previous"
mkdir -p "$INSTALL_DIRECTORY"
rm -rf "$INSTALL_STAGING_PATH"
ditto "$STAGED_APP_PATH" "$INSTALL_STAGING_PATH" || {
  echo "  [ERROR] Could not prepare the replacement Bot Player.app."
  read -r -p "  Press Return to close..." _
  exit 1
}
if [[ ! -x "$INSTALL_STAGING_PATH/Contents/MacOS/Bot Player" ]]; then
  echo "  [ERROR] The replacement Bot Player.app is incomplete. The installed app was left unchanged."
  rm -rf "$INSTALL_STAGING_PATH"
  read -r -p "  Press Return to close..." _
  exit 1
fi
rm -rf "$INSTALL_BACKUP_PATH"
if [[ -e "$APP_PATH" ]] && ! mv "$APP_PATH" "$INSTALL_BACKUP_PATH"; then
  echo "  [ERROR] Could not prepare the installed Bot Player.app for replacement."
  rm -rf "$INSTALL_STAGING_PATH"
  read -r -p "  Press Return to close..." _
  exit 1
fi
if ! mv "$INSTALL_STAGING_PATH" "$APP_PATH"; then
  echo "  [ERROR] Could not install the replacement Bot Player.app. Restoring the previous app."
  if [[ -e "$INSTALL_BACKUP_PATH" ]]; then
    mv "$INSTALL_BACKUP_PATH" "$APP_PATH" || true
  fi
  read -r -p "  Press Return to close..." _
  exit 1
fi
rm -rf "$INSTALL_BACKUP_PATH"

echo ""
echo "  ========================================"
echo "    Ready! Opening installed Bot Player.app..."
echo "  ========================================"
echo ""
echo "  macOS will identify the controller as Bot Player.app in ~/Applications."
echo ""

open "$APP_PATH"
echo "  In the app's Mac setup checklist, approve Bot Player in Screen Recording"
echo "  and Accessibility. Do not approve Terminal or Python for the normal beta path."
exit 0
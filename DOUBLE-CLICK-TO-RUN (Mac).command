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

echo ""
echo "  ========================================"
echo "    Bot Player"
echo "  ========================================"
echo ""
echo "  Setting things up — this may take a minute..."
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

APP_PATH="$SCRIPT_DIR/dist/Bot Player.app"
APP_EXECUTABLE="$APP_PATH/Contents/MacOS/Bot Player"
BUILD_REVISION="2026-08-25-training-entry-no-manual-wizard"
APP_REVISION_FILE="$APP_PATH/Contents/Resources/bot-player-build-revision.txt"
if [[ ! -f "$SCRIPT_DIR/block-jam-3d-icon.png" ]]; then
  echo "  [ERROR] The bundled Block Jam 3D icon is missing from this package."
  read -r -p "  Re-download the complete test ZIP, then press Return to close..." _
  exit 1
fi
if [[ ! -x "$APP_EXECUTABLE" || "$SCRIPT_DIR/bot_player.py" -nt "$APP_EXECUTABLE" || "$SCRIPT_DIR/requirements.txt" -nt "$APP_EXECUTABLE" || "$SCRIPT_DIR/block-jam-3d-icon.png" -nt "$APP_EXECUTABLE" || "$0" -nt "$APP_EXECUTABLE" || ! -f "$APP_REVISION_FILE" || "$(cat "$APP_REVISION_FILE" 2>/dev/null)" != "$BUILD_REVISION" ]]; then
  echo "  Building the real Bot Player.app for macOS..."
  rm -rf "$SCRIPT_DIR/dist/Build" "$APP_PATH"
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
  mkdir -p "$(dirname "$APP_REVISION_FILE")"
  printf '%s\n' "$BUILD_REVISION" > "$APP_REVISION_FILE"
fi

if [[ ! -x "$APP_EXECUTABLE" ]]; then
  echo "  [ERROR] Bot Player.app was not created."
  read -r -p "  Press Return to close..." _
  exit 1
fi

echo ""
echo "  ========================================"
echo "    Ready! Opening Bot Player.app..."
echo "  ========================================"
echo ""
echo "  macOS will now identify the controller as Bot Player."
echo ""

open "$APP_PATH"
echo "  If macOS asks for permissions, enable Bot Player in Screen Recording"
echo "  and Accessibility. The app will ask for the safety notice first."
exit 0
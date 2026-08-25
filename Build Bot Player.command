#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Bot Player can only be packaged on macOS."
  read -r -p "Press Return to close..."
  exit 1
fi

./build-python-app.sh
open "$SCRIPT_DIR/dist/Bot Player.app"
echo
echo "Bot Player.app is ready and has been opened."
read -r -p "Press Return to close..."
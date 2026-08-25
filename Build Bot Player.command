#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Bot Player can only be packaged on macOS."
  read -r -p "Press Return to close..."
  exit 1
fi

echo
echo "This deliberately replaces ~/Applications/Bot Player.app with a newly built beta."
echo "The new bundle is first created at $SCRIPT_DIR/dist/Bot Player.app."
echo "macOS may require Screen Recording and Accessibility approval again after replacement."
read -r -p "Type REBUILD to continue, or press Return to cancel: " confirmation
if [[ "$confirmation" != "REBUILD" ]]; then
  echo "Nothing was replaced."
  exit 0
fi

"$SCRIPT_DIR/DOUBLE-CLICK-TO-RUN (Mac).command" --rebuild
echo
echo "The replacement Bot Player.app has been opened from ~/Applications."
read -r -p "Press Return to close..."
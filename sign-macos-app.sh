#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:?Usage: sign-macos-app.sh '/path/to/Bot Player.app'}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Bot Player signing can only run on macOS." >&2
  exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "The app bundle to sign does not exist: $APP_PATH" >&2
  exit 1
fi

IDENTITY_LIST="$(security find-identity -v -p codesigning 2>/dev/null || true)"
SIGNING_IDENTITY="${BOT_PLAYER_SIGNING_IDENTITY:-}"

identity_is_supported() {
  case "$1" in
    "Developer ID Application: "*|"Apple Development: "*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [[ -n "$SIGNING_IDENTITY" ]]; then
  if ! grep -Fq "\"$SIGNING_IDENTITY\"" <<<"$IDENTITY_LIST"; then
    echo "BOT_PLAYER_SIGNING_IDENTITY is not available in this Mac's keychain: $SIGNING_IDENTITY" >&2
    exit 1
  fi
  if ! identity_is_supported "$SIGNING_IDENTITY"; then
    echo "BOT_PLAYER_SIGNING_IDENTITY must be a Developer ID Application or Apple Development certificate." >&2
    exit 1
  fi
else
  SIGNING_IDENTITY="$(
    awk -F'"' '
      /"Developer ID Application: / { print $2; found = 1; exit }
      /"Apple Development: / && development == "" { development = $2 }
      END { if (!found && development != "") print development }
    ' <<<"$IDENTITY_LIST"
  )"
fi

if [[ -z "$SIGNING_IDENTITY" ]]; then
  cat >&2 <<'EOF'
No usable signing certificate was found.

Install a "Developer ID Application" certificate for a distributable build, or
an "Apple Development" certificate for local testing. You can select an
installed certificate explicitly with BOT_PLAYER_SIGNING_IDENTITY.

Bot Player refuses to produce an unsigned or ad-hoc-signed app bundle.
EOF
  exit 1
fi
if ! identity_is_supported "$SIGNING_IDENTITY"; then
  echo "Only Developer ID Application and Apple Development certificates may sign Bot Player." >&2
  exit 1
fi

echo "Signing Bot Player with: $SIGNING_IDENTITY"

# Sign native executables and libraries before sealing the outer app bundle.
while IFS= read -r -d '' nested_code; do
  codesign --force --sign "$SIGNING_IDENTITY" --options runtime --timestamp "$nested_code"
done < <(
  find "$APP_PATH/Contents" -type f \
    \( -perm -111 -o -name "*.dylib" -o -name "*.so" \) -print0
)

codesign --force --sign "$SIGNING_IDENTITY" --options runtime --timestamp "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo "Verified hardened-runtime signature for $APP_PATH"
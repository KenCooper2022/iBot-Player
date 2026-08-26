#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:?Usage: sign-macos-app.sh '/path/to/Bot Player.app' [development|distribution]}"
BUILD_MODE="${2:-development}"

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

case "$BUILD_MODE" in
  development)
    IDENTITY_PREFIX="Apple Development: "
    ;;
  distribution)
    IDENTITY_PREFIX="Developer ID Application: "
    ;;
  *)
    echo "Signing mode must be development or distribution." >&2
    exit 1
    ;;
esac

identity_matches_mode() {
  case "$1" in
    "$IDENTITY_PREFIX"*)
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
  if ! identity_matches_mode "$SIGNING_IDENTITY"; then
    echo "BOT_PLAYER_SIGNING_IDENTITY must be an identity beginning with $IDENTITY_PREFIX for $BUILD_MODE builds." >&2
    exit 1
  fi
else
  SIGNING_IDENTITY="$(
    awk -F'"' -v identity_prefix="$IDENTITY_PREFIX" '$2 ~ "^" identity_prefix { print $2; exit }' <<<"$IDENTITY_LIST"
  )"
fi

if [[ -z "$SIGNING_IDENTITY" ]]; then
  echo "No usable $IDENTITY_PREFIX certificate was found for this $BUILD_MODE build." >&2
  echo "Set BOT_PLAYER_SIGNING_IDENTITY to choose an installed matching certificate." >&2
  echo "Bot Player refuses to produce an unsigned or ad-hoc-signed app bundle." >&2
  exit 1
fi
if ! identity_matches_mode "$SIGNING_IDENTITY"; then
  echo "Only $IDENTITY_PREFIX certificates may sign this $BUILD_MODE build." >&2
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
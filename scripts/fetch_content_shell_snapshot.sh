#!/usr/bin/env bash
set -euo pipefail

PLATFORM=${PLATFORM:-Mac_Arm}
REVISION=${1:-}
SNAPSHOT_ROOT=${SNAPSHOT_ROOT:-../chromium-workspace/snapshots}

BASE_URL="https://commondatastorage.googleapis.com/chromium-browser-snapshots"

if [[ -z "$REVISION" ]]; then
  REVISION=$(curl -fsSL "$BASE_URL/$PLATFORM/LAST_CHANGE")
fi

SNAPSHOT_ROOT_ABS=$(cd "$(dirname "$0")/.." && mkdir -p "$SNAPSHOT_ROOT" && cd "$SNAPSHOT_ROOT" && pwd)
ZIP_PATH="$SNAPSHOT_ROOT_ABS/content-shell-$PLATFORM-$REVISION.zip"
DEST_DIR="$SNAPSHOT_ROOT_ABS/$PLATFORM-$REVISION"
URL="$BASE_URL/$PLATFORM/$REVISION/content-shell.zip"

echo "Platform: $PLATFORM"
echo "Revision: $REVISION"
echo "URL: $URL"

if [[ ! -f "$ZIP_PATH" ]]; then
  curl -fL --retry 3 --continue-at - "$URL" -o "$ZIP_PATH"
fi

rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
unzip -q "$ZIP_PATH" -d "$DEST_DIR"
xattr -dr com.apple.quarantine "$DEST_DIR" 2>/dev/null || true

echo "$DEST_DIR/content-shell/Content Shell.app/Contents/MacOS/Content Shell"

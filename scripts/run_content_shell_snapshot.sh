#!/usr/bin/env bash
set -euo pipefail

PLATFORM=${PLATFORM:-Mac_Arm}
REVISION=${1:-}
SNAPSHOT_ROOT=${SNAPSHOT_ROOT:-../chromium-workspace/snapshots}

if [[ -z "$REVISION" ]]; then
  REVISION=$(curl -fsSL "https://commondatastorage.googleapis.com/chromium-browser-snapshots/$PLATFORM/LAST_CHANGE")
fi

SNAPSHOT_ROOT_ABS=$(cd "$(dirname "$0")/.." && cd "$SNAPSHOT_ROOT" && pwd)
CONTENT_SHELL="$SNAPSHOT_ROOT_ABS/$PLATFORM-$REVISION/content-shell/Content Shell.app/Contents/MacOS/Content Shell"

if [[ ! -x "$CONTENT_SHELL" ]]; then
  echo "Content Shell not found: $CONTENT_SHELL" >&2
  echo "Run: scripts/fetch_content_shell_snapshot.sh $REVISION" >&2
  exit 1
fi

exec "$CONTENT_SHELL" "${@:2}"

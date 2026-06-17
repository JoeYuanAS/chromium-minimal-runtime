#!/usr/bin/env bash
set -euo pipefail

COMMIT=${1:-e0488508e67c7243b2f21e478727d1989f9d1e71}
WORKSPACE_ROOT=${WORKSPACE_ROOT:-../chromium-workspace}
SRC_DIR_NAME=${SRC_DIR_NAME:-src}
REMOTE_URL=${REMOTE_URL:-https://github.com/chromium/chromium.git}

WORKSPACE_ROOT_ABS=$(cd "$(dirname "$0")/.." && mkdir -p "$WORKSPACE_ROOT" && cd "$WORKSPACE_ROOT" && pwd)
SRC_DIR="$WORKSPACE_ROOT_ABS/$SRC_DIR_NAME"

SPARSE_PATHS=(
  .gn
  BUILD.gn
  DEPS
  LICENSE
  README.md
  build
  buildtools
  content/public
  content/shell
  scripts
  testing
  tools
)

rm -rf "$SRC_DIR"

git clone --depth=1 --filter=blob:none --no-checkout "$REMOTE_URL" "$SRC_DIR"
cd "$SRC_DIR"
git fetch --depth=1 --filter=blob:none origin "$COMMIT"
git sparse-checkout init --cone
git sparse-checkout set "${SPARSE_PATHS[@]}"
git checkout --detach "$COMMIT"

cat > .chromium_snapshot_commit <<EOF
commit $COMMIT
source $REMOTE_URL partial+sparse clone
EOF

git rev-parse HEAD
git sparse-checkout list
git count-objects -vH

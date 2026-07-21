#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

CHROMIUM_SRC=${CHROMIUM_SRC:-"$PROJECT_ROOT/../chromium-workspace/src"}
BUILD_DIR=${BUILD_DIR:-out/ContentShell}
DEST_ROOT=${DEST_ROOT:-"$PROJECT_ROOT/output/content-shell-minimal"}
APP_NAME=${APP_NAME:-"Content Shell.app"}
LAUNCHER_SOURCE=${LAUNCHER_SOURCE:-"$PROJECT_ROOT/src/content_shell_app_launcher.c"}
KEEP_DEBUG_SUPPORT=${KEEP_DEBUG_SUPPORT:-1}
KEEP_GPU_FALLBACKS=${KEEP_GPU_FALLBACKS:-1}

SOURCE_APP="$CHROMIUM_SRC/$BUILD_DIR/$APP_NAME"
DEST_APP="$DEST_ROOT/$APP_NAME"
MACOS_DIR="$DEST_APP/Contents/MacOS"
FRAMEWORK_C_DIR="$DEST_APP/Contents/Frameworks/Content Shell Framework.framework/Versions/C"
LIBRARIES_DIR="$FRAMEWORK_C_DIR/Libraries"

if [[ ! -d "$SOURCE_APP" ]]; then
  echo "Source app not found: $SOURCE_APP" >&2
  exit 1
fi

if [[ ! -f "$LAUNCHER_SOURCE" ]]; then
  echo "Launcher source not found: $LAUNCHER_SOURCE" >&2
  exit 1
fi

rm -rf "$DEST_APP"
mkdir -p "$DEST_ROOT"

rsync -a "$SOURCE_APP" "$DEST_ROOT/"

rm -f "$MACOS_DIR/content_shell.log"

if [[ -f "$MACOS_DIR/Content Shell.bin" ]]; then
  rm -f "$MACOS_DIR/Content Shell.bin"
fi
mv "$MACOS_DIR/Content Shell" "$MACOS_DIR/Content Shell.bin"

/usr/bin/clang -O2 -Wall -Wextra -arch arm64 "$LAUNCHER_SOURCE" \
  -o "$MACOS_DIR/Content Shell"

chmod +x "$MACOS_DIR/Content Shell" "$MACOS_DIR/Content Shell.bin"

# Keep debugging/CDP support by default. These files can be removed only in a
# separate runtime-only build after the replacement behavior is verified.
if [[ "$KEEP_DEBUG_SUPPORT" != "1" ]]; then
  rm -f "$LIBRARIES_DIR/libtest_trace_processor.dylib"
fi

if [[ "$KEEP_GPU_FALLBACKS" != "1" ]]; then
  rm -f "$LIBRARIES_DIR/libvk_swiftshader.dylib"
  rm -f "$LIBRARIES_DIR/libvulkan.dylib"
  rm -f "$LIBRARIES_DIR/vk_swiftshader_icd.json"
fi

strip -x "$FRAMEWORK_C_DIR/Content Shell Framework"
find "$LIBRARIES_DIR" -maxdepth 1 -type f -name "*.dylib" -exec strip -x {} \;

codesign --force --sign - "$MACOS_DIR/Content Shell.bin"
codesign --force --deep --sign - "$DEST_APP"
codesign --verify --verbose=6 "$DEST_APP"

du -sh "$DEST_APP"
echo "$DEST_APP"

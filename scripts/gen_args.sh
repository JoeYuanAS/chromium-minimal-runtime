#!/usr/bin/env bash
set -e

OUT_DIR=${1:-out/CollectorRelease}
mkdir -p "$OUT_DIR"
cat > "$OUT_DIR/args.gn" <<'ARGS'
is_debug = false
is_component_build = false
symbol_level = 0
blink_symbol_level = 0

enable_nacl = false
enable_printing = false
enable_basic_printing = false
enable_pdf = false
enable_plugins = false
enable_extensions = false
enable_web_speech = false
enable_webrtc = false
use_cups = false
use_kerberos = false
ARGS

echo "Generated $OUT_DIR/args.gn"

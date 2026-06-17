#!/usr/bin/env bash
set -e

# 说明：这是占位脚本。Chromium 拉取建议使用 depot_tools。
# 真实流程：
#   git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
#   export PATH="$PWD/depot_tools:$PATH"
#   fetch --nohooks chromium
#   cd src
#   gclient runhooks

echo "Install depot_tools, then run: fetch --nohooks chromium"

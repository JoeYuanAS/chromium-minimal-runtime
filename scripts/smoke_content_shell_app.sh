#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

APP=${1:-"$PROJECT_ROOT/output/content-shell-minimal/Content Shell.app"}
URL=${2:-"data:text/html,<html><body>content-shell-smoke-ok</body></html>"}

if [[ ! -d "$APP" ]]; then
  echo "App not found: $APP" >&2
  exit 1
fi

rm -f /tmp/content_shell.log
open -n "$APP" --args "$URL"

sleep 6

if ! pgrep -fl "Content Shell.bin|Contents/MacOS/Content Shell" >/tmp/content_shell_smoke_pids.txt; then
  echo "Content Shell did not stay running" >&2
  exit 1
fi

cat /tmp/content_shell_smoke_pids.txt
pkill -f "Content Shell.bin|Contents/MacOS/Content Shell" || true
sleep 1

if [[ -f "$APP/Contents/MacOS/content_shell.log" ]]; then
  echo "Unexpected bundle-local log file was created" >&2
  exit 1
fi

codesign --verify --verbose=6 "$APP"
echo "smoke ok: $APP"

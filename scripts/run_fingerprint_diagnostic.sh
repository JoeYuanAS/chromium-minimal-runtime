#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

APP=${APP:-"$PROJECT_ROOT/output/content-shell-minimal/Content Shell.app"}
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-8787}
PYTHON=${PYTHON:-python3}
REPORT_DIR=${REPORT_DIR:-"$PROJECT_ROOT/output/fingerprint-reports"}
REMOTE_DEBUGGING_PORT=${REMOTE_DEBUGGING_PORT:-}

if [[ ! -d "$APP" ]]; then
  echo "Content Shell app not found: $APP" >&2
  echo "Build/package it first, or pass APP=/path/to/Content\\ Shell.app" >&2
  exit 1
fi

ARGS=(
  "$PROJECT_ROOT/tools/fingerprint_diagnostic/server.py"
  --host "$HOST"
  --port "$PORT"
  --report-dir "$REPORT_DIR"
  --open-app
  --app "$APP"
)

if [[ -n "$REMOTE_DEBUGGING_PORT" ]]; then
  ARGS+=("--app-arg=--remote-debugging-port=$REMOTE_DEBUGGING_PORT")
fi

exec "$PYTHON" "${ARGS[@]}"

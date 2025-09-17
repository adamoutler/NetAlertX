#!/bin/sh
# Start (or restart) the NetAlertX Python backend under debugpy in background.
# This script is invoked by the VS Code task "Restart GraphQL".
# It exists to avoid complex inline command chains that were being mangled by the task runner.

set -e

LOG_DIR=/app/log
APP_DIR=/app/server
PY=python3
PORT_DEBUG=5678

mkdir -p "$LOG_DIR"
: > "$LOG_DIR/app_stdout.log"
: > "$LOG_DIR/app_stderr.log"

# Kill any prior debug/run instances
killall python3 2>/dev/null || true
sleep 1

if [ ! -d "$APP_DIR" ]; then
  echo "[start-graphql] ERROR: $APP_DIR not found. Run the 'Run Setup Script' task first." >&2
  exit 1
fi

cd "$APP_DIR"

# Launch using absolute module path for clarity; rely on cwd for local imports
nohup "$PY" -m debugpy --listen 0.0.0.0:${PORT_DEBUG} __main__.py \
  > "$LOG_DIR/app_stdout.log" 2> "$LOG_DIR/app_stderr.log" &
PID=$!

echo "[start-graphql] Launched NetAlertX backend (PID $PID) with debugpy on port ${PORT_DEBUG}."

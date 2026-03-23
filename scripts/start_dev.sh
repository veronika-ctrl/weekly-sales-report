#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.devserver"
LOG_DIR="$PID_DIR/logs"
BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/docs"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

mkdir -p "$LOG_DIR"

echo "➡️  Ensuring required tools exist..."
if [[ ! -x "$ROOT_DIR/venv/bin/python" ]]; then
  echo "❌ Could not find venv python at venv/bin/python. Run 'make install' first." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "❌ npm is required but not found in PATH." >&2
  exit 1
fi
if ! command -v lsof >/dev/null 2>&1; then
  echo "❌ lsof is required but not found in PATH." >&2
  exit 1
fi

stop_port () {
  local PORT=$1
  if lsof -ti tcp:$PORT >/dev/null 2>&1; then
    echo "🛑 Stopping processes on port $PORT..."
    lsof -ti tcp:$PORT | xargs kill
    # give processes a moment to shut down
    sleep 1
  fi
}

start_backend () {
  echo "🚀 Starting backend (uvicorn) on port $BACKEND_PORT..."
  (
    cd "$ROOT_DIR"
    "$ROOT_DIR/venv/bin/python" -m uvicorn weekly_report.api.routes:app --reload \
      > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
  )
}

start_frontend () {
  echo "🚀 Starting frontend (Next.js) on port $FRONTEND_PORT..."
  (
    cd "$ROOT_DIR"
    ulimit -n 10240 2>/dev/null || true
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    if [[ -s "$NVM_DIR/nvm.sh" ]]; then
      \. "$NVM_DIR/nvm.sh"
      [[ -f "$ROOT_DIR/.nvmrc" ]] && nvm use || nvm use 22
    fi
    cd "$ROOT_DIR/frontend"
    npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
  )
}

wait_for_url () {
  local NAME=$1
  local URL=$2
  local RETRIES=30
  local DELAY=1
  echo "⏳ Waiting for $NAME ($URL)..."
  for ((i=1; i<=RETRIES; i++)); do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "✅ $NAME is up."
      return 0
    fi
    sleep "$DELAY"
  done
  echo "❌ $NAME did not respond at $URL."
  return 1
}

print_log_hint () {
  local SERVICE=$1
  local LOGFILE=$2
  echo ""
  echo "👉 Check recent $SERVICE logs:"
  echo "----------------------------------------"
  tail -n 40 "$LOGFILE" || true
  echo "----------------------------------------"
}

echo "➡️  Clearing old PIDs/logs..."
rm -f "$PID_DIR"/*.pid
: > "$LOG_DIR/backend.log"
: > "$LOG_DIR/frontend.log"

stop_port "$BACKEND_PORT"
stop_port "$FRONTEND_PORT"

start_backend
start_frontend

BACKEND_HEALTH=0
FRONTEND_HEALTH=0

if ! wait_for_url "backend" "$BACKEND_URL"; then
  BACKEND_HEALTH=1
fi
if ! wait_for_url "frontend" "$FRONTEND_URL"; then
  FRONTEND_HEALTH=1
fi

echo ""
echo "📍 PIDs"
if [[ -f "$PID_DIR/backend.pid" ]]; then
  echo "  Backend:  $(cat "$PID_DIR/backend.pid") (log: $LOG_DIR/backend.log)"
fi
if [[ -f "$PID_DIR/frontend.pid" ]]; then
  echo "  Frontend: $(cat "$PID_DIR/frontend.pid") (log: $LOG_DIR/frontend.log)"
fi

if [[ $BACKEND_HEALTH -ne 0 ]]; then
  print_log_hint "backend" "$LOG_DIR/backend.log"
fi
if [[ $FRONTEND_HEALTH -ne 0 ]]; then
  print_log_hint "frontend" "$LOG_DIR/frontend.log"
fi

if [[ $BACKEND_HEALTH -ne 0 || $FRONTEND_HEALTH -ne 0 ]]; then
  echo "❗ Some services failed health checks. See logs above."
  exit 1
fi

echo ""
echo "🎉 Servers are running:"
echo "  • Backend:  http://127.0.0.1:${BACKEND_PORT}/docs"
echo "  • Frontend: http://localhost:${FRONTEND_PORT}"
echo "Logs stored in $LOG_DIR. Use 'tail -f' to inspect."



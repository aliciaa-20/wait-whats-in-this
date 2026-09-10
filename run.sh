#!/usr/bin/env bash
#
# Starts the FastAPI backend and the Vite frontend together for local
# development - so you don't have to juggle two terminals - waits until
# both are actually ready (not just started), opens the frontend in your
# default browser, and stops both cleanly with a single Ctrl+C.
#
# Cross-platform: macOS, Linux, and Windows (via Git Bash).
#
# Usage:
#   ./run.sh
#
# Env overrides:
#   BACKEND_PORT=8001 FRONTEND_PORT=5174 ./run.sh
#
# This is a dev convenience script, not a deployment script - when you
# actually deploy (backend behind uvicorn/gunicorn somewhere, frontend
# built as static assets, eventually wrapped for a mobile web app / PWA),
# that will be a separate, environment-specific setup. Keeping this
# simple now makes it easy to fork into a deploy script later without
# untangling anything.

set -euo pipefail

# ============================================================
# Platform detection
# ============================================================

case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
    *)                    IS_WINDOWS=0 ;;
esac

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT"

BACKEND_PID=""
FRONTEND_PID=""

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

# ============================================================
# Pre-flight checks - fail early with a clear, actionable message
# rather than a confusing half-started state.
# ============================================================

# Locate the venv's Python. Layout differs by platform: POSIX venvs use
# bin/, Windows venvs (including ones made from Git Bash against a
# native Windows Python) use Scripts/.
if [ -x "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -x "venv/Scripts/python.exe" ]; then
    PYTHON="venv/Scripts/python.exe"
elif [ -x "venv/Scripts/python" ]; then
    PYTHON="venv/Scripts/python"
else
    fail "Python virtual environment not found. Set it up first:
  python3 -m venv venv
  # macOS/Linux:
  ./venv/bin/pip install -r requirements.txt
  # Windows (Git Bash):
  ./venv/Scripts/pip install -r requirements.txt"
fi

if [ ! -d "frontend/node_modules" ]; then
    fail "frontend/node_modules not found. Install frontend deps first:
  cd frontend && npm install"
fi

command -v npm  >/dev/null 2>&1 || fail "npm not found on PATH. Install Node.js first."
command -v curl >/dev/null 2>&1 || fail "curl not found on PATH - needed to check readiness."

# node_modules/.bin scripts sometimes lose their executable bit when
# copied/synced (iCloud, external drives, some zip extractions) rather
# than installed fresh. No-op when permissions are already fine, and a
# no-op (not an error) on Windows, where it isn't meaningful.
chmod +x frontend/node_modules/.bin/* 2>/dev/null || true

# Refuse to start if the ports are already taken - this is exactly the
# situation that causes silent, confusing collisions (e.g. a leftover
# process from a previous run that didn't shut down cleanly).
port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":$port" -sTCP:LISTEN >/dev/null 2>&1
    else
        curl -s -o /dev/null --connect-timeout 1 "http://127.0.0.1:$port" 2>/dev/null
    fi
}

if port_in_use "$BACKEND_PORT"; then
    fail "Port $BACKEND_PORT is already in use - is the backend already running?
Stop whatever is using it, or run with a different port:
  BACKEND_PORT=8001 ./run.sh"
fi
if port_in_use "$FRONTEND_PORT"; then
    fail "Port $FRONTEND_PORT is already in use - is the frontend already running?
Stop whatever is using it, or run with a different port:
  FRONTEND_PORT=5174 ./run.sh"
fi

mkdir -p .run
BACKEND_LOG=".run/backend.log"
FRONTEND_LOG=".run/frontend.log"

# ============================================================
# Cleanup - stop both children on exit, Ctrl+C, or termination.
# Runs exactly once: the trap is cleared at the top so a second
# Ctrl+C (or the EXIT trap firing after INT already ran) can't
# re-enter it.
# ============================================================

cleanup() {
    trap - EXIT INT TERM
    echo
    echo "Stopping..."

    for pid in "$FRONTEND_PID" "$BACKEND_PID"; do
        [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null || true
    done

    # Give them a moment to shut down gracefully before forcing.
    sleep 1

    for pid in "$FRONTEND_PID" "$BACKEND_PID"; do
        [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    done

    wait 2>/dev/null || true
    echo "Stopped."
    exit 0
}
trap cleanup EXIT INT TERM

# ============================================================
# Start backend
# ============================================================

echo "Starting backend  (FastAPI/uvicorn) on port $BACKEND_PORT  -> $BACKEND_LOG"
"$PYTHON" -m uvicorn backend.app:app --reload --port "$BACKEND_PORT" \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# ============================================================
# Start frontend
#
# Uses `npm --prefix frontend` instead of `(cd frontend && npm ...)` so
# $! captures npm's own PID directly, with no subshell wrapper in
# between - subshell PIDs are one of the more fragile things to kill
# reliably across platforms, particularly on Windows.
# ============================================================

echo "Starting frontend (Vite dev server) on port $FRONTEND_PORT -> $FRONTEND_LOG"
npm --prefix frontend run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 \
    > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# ============================================================
# Wait for both to actually be ready - not just "started" - before
# declaring success or opening a browser tab.
# ============================================================

wait_for() {
    local url="$1" label="$2" pid="$3" log="$4" tries=60
    echo "Waiting for $label to become ready..."
    for _ in $(seq 1 "$tries"); do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo
            echo "ERROR: $label exited before becoming ready. Last lines of $log:"
            tail -n 20 "$log" 2>/dev/null || true
            exit 1
        fi
        if curl -s -o /dev/null "$url"; then
            return 0
        fi
        sleep 1
    done
    echo
    echo "ERROR: $label did not respond at $url within ${tries}s. Last lines of $log:"
    tail -n 20 "$log" 2>/dev/null || true
    exit 1
}

wait_for "$BACKEND_URL/health" "backend"  "$BACKEND_PID"  "$BACKEND_LOG"
wait_for "$FRONTEND_URL"       "frontend" "$FRONTEND_PID" "$FRONTEND_LOG"

echo
echo "======================================================================"
echo "Backend  : $BACKEND_URL  (docs at $BACKEND_URL/docs)"
echo "Frontend : $FRONTEND_URL"
echo "======================================================================"
echo "Logs: tail -f $BACKEND_LOG   /   tail -f $FRONTEND_LOG"
echo "Press Ctrl+C to stop both."
echo

# ============================================================
# Open the frontend in the default browser, cross-platform.
# Never fatal - if this fails, just print the URL and move on.
# ============================================================

open_browser() {
    local url="$1"
    if [ "$IS_WINDOWS" = "1" ]; then
        cmd.exe /c start "" "$url" >/dev/null 2>&1 && return 0
    elif command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null 2>&1 && return 0
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 && return 0
    fi
    echo "(Could not auto-open a browser - open $url manually.)"
}
open_browser "$FRONTEND_URL"

# ============================================================
# Keep running until either child exits on its own, or Ctrl+C fires
# the cleanup trap above.
# ============================================================

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done

echo "One of the processes exited unexpectedly - check the logs above."

#!/usr/bin/env bash

# Starts the FastAPI backend and the React/Vite frontend together for
# local development, so you don't have to juggle two terminals.
#
# Usage:
#   ./run.sh
#
# Stops both with a single Ctrl+C.
#
# This is a dev convenience script, not a deployment script - when
# you actually deploy (backend behind uvicorn/gunicorn somewhere,
# frontend built as static assets, eventually wrapped for a mobile
# web app / PWA), that will be a separate, environment-specific
# setup. Keeping this simple now makes it easy to fork into a
# deploy script later without untangling anything.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ ! -x "venv/bin/python" ]; then
    echo "ERROR: venv/bin/python not found. Set up the backend venv first:"
    echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "ERROR: frontend/node_modules not found. Install frontend deps first:"
    echo "  cd frontend && npm install"
    exit 1
fi

# node_modules/.bin scripts sometimes lose their executable bit when
# copied/synced (iCloud, external drives, some zip extractions) rather
# than installed fresh - this is a no-op when permissions are already
# fine, so it's safe to always run.
chmod +x frontend/node_modules/.bin/* 2>/dev/null || true

mkdir -p .run

BACKEND_LOG=".run/backend.log"
FRONTEND_LOG=".run/frontend.log"

echo "Starting backend  (FastAPI/uvicorn) on port $BACKEND_PORT  -> $BACKEND_LOG"
./venv/bin/python -m uvicorn backend.app:app --reload --port "$BACKEND_PORT" \
    > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend (Vite dev server) on port $FRONTEND_PORT -> $FRONTEND_LOG"
(cd frontend && npm run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1) \
    > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

cleanup() {
    echo
    echo "Stopping backend (pid $BACKEND_PID) and frontend (pid $FRONTEND_PID)..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# Poll for backend readiness instead of a blind sleep - importing the
# OCR stack (EasyOCR/torch) on first request/startup can take well
# over a couple of seconds, especially on a cold cache.
echo "Waiting for backend to become ready..."
for _ in $(seq 1 60); do
    if curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/health"; then
        break
    fi
    sleep 1
done

echo
echo "======================================================================"
echo "Backend  : http://127.0.0.1:$BACKEND_PORT  (docs at /docs)"
echo "Frontend : http://127.0.0.1:$FRONTEND_PORT"
echo "======================================================================"
echo "Logs: tail -f $BACKEND_LOG   /   tail -f $FRONTEND_LOG"
echo "Press Ctrl+C to stop both."
echo

# Exit (and trigger cleanup) if either process dies on its own.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done

echo "One of the processes exited unexpectedly - check the logs above."

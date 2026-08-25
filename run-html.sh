#!/usr/bin/env bash
# run-html.sh — sets up the environment (the first time) and runs the
# application with the WEB interface (HTML/CSS/JS in the browser).
#
# It is the counterpart of ./run.sh: same backend (cameras, YOLO, alerts,
# narrator), different interface. Use ./run.sh for the native desktop GUI
# (PySide6), which needs no browser.
#
# Usage:
#   ./run-html.sh                  starts and opens the browser at localhost:8000
#   ./run-html.sh --port 9000      listens on another port
#   ./run-html.sh --host 0.0.0.0   exposes it on the local network (NO auth!)
#   ./run-html.sh --no-browser     does not open the browser automatically
#   ./run-html.sh --reinstall      forces reinstalling dependencies
#
# Any other argument is passed straight through to src/main_web.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
REINSTALL=0

# --reinstall is consumed here; everything else goes to Python.
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--reinstall" ]; then
        REINSTALL=1
    else
        ARGS+=("$arg")
    fi
done

if [ ! -d "$VENV_DIR" ]; then
    echo "==> No virtual environment found at $VENV_DIR — creating it..."
    python3 -m venv "$VENV_DIR"
    REINSTALL=1
fi

# `python -m pip` instead of `$VENV_DIR/bin/pip`: the venv console scripts
# hardcode an absolute path in their shebang, so they break if the project
# folder is renamed/moved. The interpreter itself does not have that
# problem.
PYTHON="$VENV_DIR/bin/python"

# The web UI needs fastapi/uvicorn, which may be missing from a venv
# created before this interface existed — install them on demand.
if [ "$REINSTALL" = "0" ] && ! "$PYTHON" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "==> Web interface dependencies missing — installing them."
    REINSTALL=1
fi

if [ "$REINSTALL" = "1" ]; then
    echo "==> Installing dependencies (this can take a while the first time —"
    echo "    torch, ultralytics and insightface together are over 1GB of download)."
    "$PYTHON" -m pip install --upgrade pip -q
    "$PYTHON" -m pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    echo "==> .env not found — copying .env.example."
    echo "    Edit .env with your real camera credentials before continuing."
    cp .env.example .env
fi

echo "==> Starting Computer Vision Central (web interface)..."
exec "$PYTHON" src/main_web.py "${ARGS[@]+"${ARGS[@]}"}"

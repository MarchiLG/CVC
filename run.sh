#!/usr/bin/env bash
# run.sh — sets up the environment (the first time) and runs the
# application with the native desktop GUI (PySide6/Qt), no browser.
#
# For the WEB interface (HTML/CSS/JS in the browser), use ./run-html.sh —
# same backend, different interface.
#
# Usage:
#   ./run.sh              starts Computer Vision Central (desktop GUI)
#   ./run.sh --reinstall  forces reinstalling dependencies in the existing venv
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
REINSTALL=0
if [ "${1:-}" = "--reinstall" ]; then
    REINSTALL=1
fi

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

echo "==> Starting Computer Vision Central (desktop GUI)..."
exec "$PYTHON" src/main.py

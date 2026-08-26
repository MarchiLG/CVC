#!/usr/bin/env bash
# reset.sh — wipes every generated/local file so the next ./run.sh or
# ./run-html.sh starts from a clean install: virtual environment,
# Python caches, the SQLite event log, and the encrypted camera
# credentials (.env / .env.enc).
#
# What it does NOT touch, by default: config/cameras.yaml,
# config/tasks.yaml, config/app.yaml (your camera/task setup) and the
# downloaded model weights (*.pt / *.onnx) — those are expensive to
# redo and are not "generated state" in the same sense.
#
# Usage:
#   ./reset.sh                 asks for confirmation, then resets
#   ./reset.sh --yes           skips the confirmation prompt
#   ./reset.sh --purge-config  ALSO deletes config/cameras.yaml,
#                               config/tasks.yaml and config/app.yaml
#   ./reset.sh --purge-models  ALSO deletes downloaded *.pt / *.onnx weights
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ASSUME_YES=0
PURGE_CONFIG=0
PURGE_MODELS=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=1 ;;
        --purge-config) PURGE_CONFIG=1 ;;
        --purge-models) PURGE_MODELS=1 ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Usage: ./reset.sh [--yes] [--purge-config] [--purge-models]" >&2
            exit 1
            ;;
    esac
done

echo "This will permanently delete:"
echo "  - .venv/ (the Python virtual environment)"
echo "  - __pycache__/ and .pytest_cache/ (everywhere in the project)"
echo "  - data/*.db (the SQLite event log / employee database)"
echo "  - .env and .env.enc (your camera credentials — encrypted or not)"
echo "  - stray editor swap files (*.kate-swp)"
if [ "$PURGE_CONFIG" = "1" ]; then
    echo "  - config/cameras.yaml, config/tasks.yaml, config/app.yaml (--purge-config)"
fi
if [ "$PURGE_MODELS" = "1" ]; then
    echo "  - downloaded model weights: *.pt, *.onnx (--purge-models)"
fi
echo
echo "Your camera credentials are NOT recoverable after this — write them"
echo "down first if you have not backed up .env / .env.enc elsewhere."
echo

if [ "$ASSUME_YES" != "1" ]; then
    read -r -p "Continue? [y/N] " reply
    case "$reply" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Aborted."; exit 1 ;;
    esac
fi

echo "==> Stopping any running instance is your responsibility (Ctrl+C it first)."

echo "==> Removing virtual environment..."
rm -rf .venv

echo "==> Removing Python caches..."
find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache

echo "==> Removing the local database..."
rm -f data/*.db

echo "==> Removing camera credentials..."
rm -f .env .env.enc

echo "==> Removing stray editor swap files..."
find . -name "*.kate-swp" -not -path "./.venv/*" -delete 2>/dev/null || true

if [ "$PURGE_CONFIG" = "1" ]; then
    echo "==> Removing camera/task/app configuration..."
    rm -f config/cameras.yaml config/tasks.yaml config/app.yaml
fi

if [ "$PURGE_MODELS" = "1" ]; then
    echo "==> Removing downloaded model weights..."
    rm -f *.pt *.onnx
fi

echo
echo "Done. Run ./run.sh or ./run-html.sh to set up a fresh environment"
echo "(it will recreate .venv, and .env from .env.example if missing)."

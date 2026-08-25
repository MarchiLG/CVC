#!/usr/bin/env bash
# run.sh — configura o ambiente (na primeira vez) e roda a aplicação.
#
# Uso:
#   ./run.sh              inicia o Computer Vision Central
#   ./run.sh --reinstall  força a reinstalação das dependências no venv existente
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
REINSTALL=0
if [ "${1:-}" = "--reinstall" ]; then
    REINSTALL=1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Nenhum ambiente virtual encontrado em $VENV_DIR — criando..."
    python3 -m venv "$VENV_DIR"
    REINSTALL=1
fi

if [ "$REINSTALL" = "1" ]; then
    echo "==> Instalando dependências (pode demorar bastante na primeira vez —"
    echo "    torch, ultralytics e insightface juntos passam de 1GB de download)."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    echo "==> .env não encontrado — copiando .env.example."
    echo "    Edite .env com as credenciais reais das suas câmeras antes de continuar."
    cp .env.example .env
fi

echo "==> Iniciando Computer Vision Central..."
exec "$VENV_DIR/bin/python" src/main.py

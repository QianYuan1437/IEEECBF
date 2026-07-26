#!/bin/bash
# IEEECBF - Local start script
# Starts the Flask backend and serves the frontend

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONDA_BASE="/home/zhao/anaconda3"
ENV_NAME="ieeecbf"

echo "============================================"
echo "  IEEE CBF Paper Tracker"
echo "============================================"
echo ""

if [ ! -f "papers_data.json" ]; then
    echo "[!] papers_data.json not found."
    echo "    Run 'python fetch_papers.py' first, or start anyway with empty cache."
    echo ""
fi

echo "[*] Activating conda environment: ${ENV_NAME}"
source "${CONDA_BASE}/bin/activate" "${ENV_NAME}"

echo "[*] Starting Flask server on http://localhost:5000"
echo "    Frontend: http://localhost:5000"
echo "    API:      http://localhost:5000/api/health"
echo ""
echo "    Press Ctrl+C to stop."
echo ""

python -m backend.app

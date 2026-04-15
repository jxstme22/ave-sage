#!/usr/bin/env bash
# AVE SAGE — Quick Setup
# Usage: bash scripts/setup.sh
set -euo pipefail

echo "=========================================="
echo "  AVE SAGE — Self-Amplifying Intelligence "
echo "=========================================="
echo ""

# Check Python version
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required. Install Python 3.11+."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[✓] Python $PY_VERSION detected"

# Create virtual environment if not exists
if [ ! -d ".venv" ]; then
    echo "[→] Creating virtual environment..."
    python3 -m venv .venv
    echo "[✓] Virtual environment created"
else
    echo "[✓] Virtual environment exists"
fi

# Activate venv
source .venv/bin/activate
echo "[✓] Activated .venv"

# Install dependencies
echo "[→] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "[✓] Dependencies installed"

# Create data directory
mkdir -p data/chroma
echo "[✓] Data directories ready"

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[!] Created .env from .env.example — edit it with your API keys"
    else
        echo "[!] No .env file found — create one with your API keys"
    fi
else
    echo "[✓] .env file exists"
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys:"
echo "       - AVE_API_KEY (from cloud.ave.ai)"
echo "       - OPENROUTER_API_KEY (from openrouter.ai/keys)"
echo "       - TELEGRAM_BOT_TOKEN (from @BotFather)"
echo "    2. Run:  bash run.sh"
echo "    3. Open: http://localhost:8000"
echo "=========================================="

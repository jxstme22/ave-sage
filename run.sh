#!/usr/bin/env bash
# AVE SAGE — Run Script
# Usage: bash run.sh [mode]
# No args = run everything (API + Web UI + Telegram bot)
# Modes: api, web, bot, test, build-web, build-ext
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors ────────────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RESET='\033[0m'
log()  { echo -e "${GREEN}[AVE SAGE]${RESET} $*"; }
info() { echo -e "${CYAN}[AVE SAGE]${RESET} $*"; }
warn() { echo -e "${YELLOW}[AVE SAGE]${RESET} $*"; }

# ── Python venv ───────────────────────────────────────────────────
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    warn "No virtual environment found."
    warn "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# ── .env ──────────────────────────────────────────────────────────
if [ -f ".env" ]; then
    set -a; source .env; set +a
fi

# ── Helper: free a TCP port before binding ──────────────────────
kill_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        warn "Port $port in use — killing PID(s) $pids ..."
        kill -9 $pids 2>/dev/null || true
        sleep 0.5
    fi
}

# ── Helper: ensure Node deps installed ───────────────────────────
check_node_deps() {
    local dir="$1"
    if [ ! -d "$dir/node_modules" ]; then
        log "Installing Node dependencies in $(basename "$dir") ..."
        npm --prefix "$dir" install --silent
    fi
}

# ── Helper: wait for HTTP endpoint ───────────────────────────────
wait_for_api() {
    local url="$1" attempts=0 max=40
    info "Waiting for $url ..."
    while ! python -c "import urllib.request; urllib.request.urlopen('$url', timeout=2)" > /dev/null 2>&1; do
        sleep 0.5
        attempts=$((attempts + 1))
        if [ $attempts -ge $max ]; then
            warn "API did not respond after $((max / 2))s — continuing anyway."
            break
        fi
    done
}

MODE="${1:-all}"

case "$MODE" in
    # ── DEFAULT: run everything ───────────────────────────────────
    all)
        echo ""
        echo -e "  ${GREEN}▄▄▄  █ █ ██▀   ▄▄▀ ▄▄▄ ▄▄ ██▀${RESET}"
        echo -e "  ${GREEN}█▄█  ▀▄▀ █▄▄   ▀▄▀ ▄█▄ ██ █▄▄${RESET}"
        echo ""
        log "Starting AVE SAGE — full stack ..."
        echo ""

        # 1. Backend API
        log "Starting backend API ..."
        kill_port 8000
        python -m dashboard.app &
        API_PID=$!

        # 2. Telegram bot (optional — skip gracefully if token missing)
        BOT_PID=""
        if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
            # Kill any existing Telegram bot process before restarting
            existing_bot=$(pgrep -f 'scripts\.telegram_bot' 2>/dev/null || true)
            if [ -n "$existing_bot" ]; then
                warn "Killing existing Telegram bot (PID $existing_bot) ..."
                kill -9 $existing_bot 2>/dev/null || true
                sleep 0.5
            fi
            log "Starting Telegram bot ..."
            python -m scripts.telegram_bot &
            BOT_PID=$!
        else
            warn "TELEGRAM_BOT_TOKEN not set — skipping Telegram bot."
        fi

        # 3. Web UI dev server
        check_node_deps "$SCRIPT_DIR/web"
        log "Waiting for API to be ready ..."
        wait_for_api "http://localhost:8000/health"
        log "Starting Web UI dev server ..."
        npm --prefix "$SCRIPT_DIR/web" run dev &
        WEB_PID=$!

        echo ""
        echo -e "  ${CYAN}Backend API${RESET}   →  http://localhost:8000"
        echo -e "  ${CYAN}Web UI${RESET}        →  http://localhost:3000"
        [ -n "$BOT_PID" ] && echo -e "  ${CYAN}Telegram Bot${RESET}  →  running (PID $BOT_PID)"
        echo ""
        info "Press Ctrl+C to stop everything."
        echo ""

        trap "log 'Shutting down...'; kill $API_PID $WEB_PID ${BOT_PID:-} 2>/dev/null; exit 0" INT TERM
        wait || true
        ;;

    # ── Individual modes ──────────────────────────────────────────
    api|dashboard)
        log "Starting backend API on http://0.0.0.0:8000 ..."
        kill_port 8000
        python -m dashboard.app
        ;;
    web)
        log "Starting Web UI dev server on http://localhost:3000 ..."
        check_node_deps "$SCRIPT_DIR/web"
        npm --prefix "$SCRIPT_DIR/web" run dev
        ;;
    bot)
        log "Starting Telegram bot ..."
        python -m scripts.telegram_bot
        ;;
    build-web)
        log "Building Web UI ..."
        check_node_deps "$SCRIPT_DIR/web"
        npm --prefix "$SCRIPT_DIR/web" run build
        log "Build output: web/dist/"
        ;;
    build-ext)
        log "Building Chrome/Brave extension ..."
        check_node_deps "$SCRIPT_DIR/extension"
        npm --prefix "$SCRIPT_DIR/extension" run build
        log "Extension ready: extension/dist/"
        info "Load in Brave: brave://extensions → Developer mode → Load unpacked → extension/dist/"
        info "Full path: $SCRIPT_DIR/extension/dist/"
        ;;
    ext-dev)
        log "Starting extension dev server ..."
        check_node_deps "$SCRIPT_DIR/extension"
        npm --prefix "$SCRIPT_DIR/extension" run dev
        ;;
    test)
        log "Running test suite ..."
        python -m pytest tests/ -v
        ;;
    *)
        echo ""
        echo "Usage: bash run.sh [mode]"
        echo ""
        echo "  (no args)   Start EVERYTHING — API + Web UI + Telegram bot"
        echo "  api         Start backend API only (localhost:8000)"
        echo "  web         Start Web UI dev server only (localhost:3000)"
        echo "  bot         Start Telegram bot only"
        echo "  build-web   Build Web UI for production (web/dist/)"
        echo "  build-ext   Build Chrome/Brave extension (extension/dist/)"
        echo "  ext-dev     Start extension dev server"
        echo "  test        Run Python test suite"
        echo ""
        exit 1
        ;;
esac

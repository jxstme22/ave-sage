# AVE SAGE — How to Run

## Prerequisites

- Python 3.11+ (tested on 3.12)
- AVE Cloud API key — [cloud.ave.ai](https://cloud.ave.ai)
- OpenRouter API key — [openrouter.ai/keys](https://openrouter.ai/keys)
- (Optional) Telegram Bot Token — talk to [@BotFather](https://t.me/BotFather)

---

## 1. Quick Setup

```bash
# Clone & enter project
cd ave-sage

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

---

## 2. Environment Variables (.env)

| Variable | Required | Description |
|---|---|---|
| `AVE_API_KEY` | Yes | AVE Cloud API key |
| `AVE_SECRET_KEY` | For trading | AVE Cloud secret key (proxy wallet) |
| `API_PLAN` | No | `free` / `normal` / `pro` (default: free) |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM reasoning |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token for remote control |
| `OPENAI_API_KEY` | No | Only if using OpenAI embeddings |

---

## 3. Run Modes

### Dashboard only (default)
```bash
bash run.sh dashboard
# or just:
bash run.sh
```
Opens the web dashboard at **http://localhost:8000** with:
- Live intelligence feed via WebSocket
- Memory stats, signals, trade decisions
- REST API endpoints

### Telegram Bot only
```bash
bash run.sh bot
```
Control SAGE from Telegram with commands like `/status`, `/trade`, `/memory`, etc.

### Dashboard + Bot together
```bash
bash run.sh both
```
Runs both the dashboard and Telegram bot in parallel.

### Run tests
```bash
bash run.sh test
```

---

## 4. Configuration (config.yaml)

Key settings you may want to adjust:

```yaml
agent:
  llm_provider: "openrouter"
  reasoning_model: "anthropic/claude-sonnet-4-20250514"  # or any OpenRouter model
  dry_run: true              # SET false FOR LIVE TRADING
  max_position_usd: 50.0
  trade_confidence_min: 0.70

ave:
  chains:
    - solana
    - bsc
```

### Available OpenRouter Models
You can use any model from [openrouter.ai/models](https://openrouter.ai/models):
- `anthropic/claude-sonnet-4-20250514` (recommended)
- `openai/gpt-4o`
- `google/gemini-2.5-pro-preview-06-05`
- `meta-llama/llama-4-maverick`

---

## 5. API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/api/memory/stats` | GET | Memory chunk statistics |
| `/api/memory/recent?chain=solana` | GET | Recent memory events |
| `/api/memory/query?q=...` | GET | Semantic search |
| `/api/decisions` | GET | Recent trade decisions |
| `/api/positions/open` | GET | Open positions |
| `/api/positions/closed` | GET | Closed positions |
| `/api/sage/ask?q=...` | GET | Ask SAGE anything |
| `/api/feedback/stats` | GET | Win rate & outcomes |
| `/api/memory/health` | GET | Knowledge base health |
| `/api/signals/performance?signal_type=...` | GET | Signal performance |
| `/ws` | WebSocket | Live event stream |

---

## 6. Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/status` | System health & stats |
| `/memory` | Memory chunk statistics |
| `/query <text>` | Search knowledge base |
| `/signals` | Recent detected signals |
| `/decisions [n]` | Recent trade decisions |
| `/positions` | Open positions |
| `/closed` | Closed positions |
| `/performance <signal>` | Signal performance history |
| `/feedback` | Win rate & outcome stats |
| `/config` | View current config |
| `/dryrun on/off` | Toggle dry run mode |
| `/model <name>` | Switch LLM model |
| `/chains` | List active chains |
| `/health` | Full system health report |
| `/help` | Show all commands |

---

## 7. Docker

```bash
docker compose up -d
```

Dashboard will be available at **http://localhost:8000**.

---

## 8. Project Structure

```
ave-sage/
├── config.py / config.yaml    # Configuration
├── run.sh                     # Startup script
├── core/
│   ├── collector.py           # REST + WebSocket data collection
│   ├── chunker.py             # Event → MemoryChunk conversion
│   ├── embedder.py            # ChromaDB vector store
│   ├── rag_engine.py          # RAG retrieval + context building
│   ├── signal_detector.py     # Pattern detection (6 detectors)
│   └── feedback.py            # Outcome recording & learning loop
├── agents/
│   ├── sage_agent.py          # LLM reasoning via OpenRouter
│   ├── trade_agent.py         # Trade execution (dry-run + live)
│   └── memory_agent.py        # Knowledge base management
├── skills/
│   ├── ave_data_rest.py       # AVE Cloud data REST wrapper
│   ├── ave_data_wss.py        # AVE Cloud WebSocket wrapper
│   └── ave_trade_rest.py      # AVE Cloud trading wrapper
├── dashboard/
│   └── app.py                 # FastAPI server + UI
├── scripts/
│   ├── telegram_bot.py        # Telegram bot controller
│   └── setup.sh               # Setup script
└── tests/
    ├── test_pipeline.py       # Core pipeline tests
    └── test_extended.py       # Extended integration tests
```

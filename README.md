# AVE SAGE 🧠
### Self-Amplifying Generative Engine — AVE Cloud Skill Suite

> *An on-chain intelligence system that observes markets, remembers patterns, reasons from history, and gets smarter with every trade cycle.*

[![AVE Cloud](https://img.shields.io/badge/AVE-Cloud%20Skill-blue)](https://cloud.ave.ai)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Compatible-green)](https://openclaw.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Live Trades](https://img.shields.io/badge/Live%20Trades-3%20confirmed-brightgreen)](#live-trade-history)
[![Memory](https://img.shields.io/badge/Memory%20Chunks-1820%2B-blueviolet)](#)

---

## What Is AVE SAGE?

Most trading agents are stateless — they react to the current market with no memory of what happened before. AVE SAGE breaks that pattern.

SAGE is a **self-improving on-chain intelligence loop** built on top of AVE Cloud Skills. It watches markets via AVE's real-time streams, logs every significant event into a structured knowledge base, and queries that knowledge base — via RAG — before making its next decision. The result is an agent that learns from its own history: the longer it runs, the smarter it gets.

**SAGE is live on Solana mainnet.** Three confirmed on-chain trades have been executed (BONK × 2 + WIF), with wallet holdings tracked in real time.

```
┌─────────────────────────────────────────────────────────────┐
│                     AVE SAGE LOOP                           │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  OBSERVE │───▶│ REMEMBER │───▶│  REASON  │              │
│  │          │    │          │    │          │              │
│  │ AVE WSS  │    │ Chunker  │    │   RAG    │              │
│  │ AVE REST │    │ Embedder │    │  Query   │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                        │                    │
│  ┌──────────┐    ┌──────────┐          │                    │
│  │  LEARN   │◀───│   ACT    │◀─────────┘                   │
│  │          │    │          │                               │
│  │ Outcome  │    │ AVE Trade│                               │
│  │ Feedback │    │ Executor │                               │
│  └──────────┘    └──────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Why This Wins

| Feature | Standard Trading Bot | AVE SAGE |
|---|---|---|
| Market data | ✅ Live prices | ✅ Live prices + WSS streams |
| Pattern memory | ❌ None | ✅ 1820+ vector DB chunks |
| Trade reasoning | ❌ Rule-based | ✅ RAG + LLM reasoning |
| Self-improvement | ❌ Static | ✅ Outcome feedback loop |
| Multi-chain | ✅ Maybe | ✅ SOL, BSC, ETH, Base |
| Live trading | ✅ Often broken | ✅ 3 confirmed mainnet trades |
| Web UI | ❌ | ✅ React dashboard (port 3001) |
| Browser extension | ❌ | ✅ Chrome extension popup |
| Telegram alerts | ❌ | ✅ Bot with signal feed |
| OpenClaw ready | ❌ | ✅ Native skill manifest |

---

## Live Trade History

SAGE has executed **3 confirmed on-chain trades** on Solana mainnet:

| # | Token | Action | Amount | Status |
|---|-------|--------|--------|--------|
| 1 | BONK | BUY | ~$2 | ✅ Confirmed |
| 2 | BONK | BUY | ~$2 | ✅ Confirmed |
| 3 | WIF | BUY | ~$2 | ✅ Confirmed |

**Proxy Wallet:** `CiGMYJE5v7su1ZYE2SGKKrD7bqzp2dasWc94T8eLnKFr`  
**Current Holdings:** 69,410 BONK + 1.27 WIF + 0.035 SOL

---

## Architecture

```
ave-sage/
├── core/
│   ├── collector.py          # AVE REST + WSS data collector
│   ├── chunker.py            # Event → chunk pipeline
│   ├── embedder.py           # Chunk → vector store
│   ├── rag_engine.py         # Query + context retrieval
│   └── signal_detector.py    # Pattern & anomaly detection
├── agents/
│   ├── sage_agent.py         # Main reasoning agent (LLM orchestrator)
│   └── trade_agent.py        # Executes via AVE proxy wallet
├── skills/
│   ├── ave_data_rest.py      # AVE REST skill
│   ├── ave_data_wss.py       # AVE WSS skill
│   └── ave_trade_rest.py     # AVE Trade skill
├── dashboard/
│   └── app.py                # FastAPI backend + WebSocket feed (port 8000)
├── web/                      # React 19 + TypeScript + Vite web UI (port 3001)
│   └── src/
│       ├── pages/
│       │   ├── CommandCenter.tsx   # Live signal feed + chat
│       │   ├── Portfolio.tsx       # Wallet + positions + token holdings
│       │   ├── SageChat.tsx        # RAG-powered Q&A with markdown
│       │   └── Memory.tsx          # Knowledge base browser
│       └── api.ts                  # Backend API client
├── extension/                # Chrome browser extension (380×600px popup)
│   └── src/
│       ├── pages/
│       │   ├── WalletPage.tsx      # Balance + holdings + intelligence feed
│       │   ├── SignalsPage.tsx     # Signal history + auto-refresh
│       │   └── CommandPage.tsx     # Quick trade controls
│       └── api.ts                  # Extension API client
├── scripts/
│   ├── telegram_bot.py       # Telegram bot with signal feed
│   ├── Dockerfile.txt        # Docker build
│   └── setup.sh              # One-line setup
├── tests/
│   └── test_pipeline.py      # 64 core pipeline tests
├── .openclaw/
│   └── skill.json            # OpenClaw skill manifest
├── .claude-plugin/
│   └── plugin.json           # Claude Code plugin manifest
├── config.yaml               # Runtime config
├── docker-compose.yml        # Full stack compose
└── run.sh                    # Start API / web / bot (bash run.sh [api|web|bot|all])
```

---

## The 5-Step Intelligence Loop

### Step 1 — OBSERVE
AVE Cloud REST and WSS skills stream live market events: price ticks, large swap transactions, kline closes, holder changes, trending token appearances, and risk/honeypot flag changes. Every event above a configurable significance threshold is captured.

### Step 2 — REMEMBER
Raw events are processed through the **chunker**, which normalizes them into structured memory units:
- `market_event` — price movements, volume spikes
- `trade_event` — executed swaps, wallet flows
- `pattern_event` — detected signals (breakout, reversal, accumulation)
- `outcome_event` — results of SAGE's own trade decisions

Each chunk is embedded via a local embedding model (or OpenAI/Anthropic) and stored in **ChromaDB** with full metadata: chain, token, timestamp, event_type, significance_score.

### Step 3 — REASON
Before any action, SAGE queries its own knowledge base:
> *"What happened the last 5 times SOL/USDC had a volume spike above 3x on a 15m close?"*

The RAG engine retrieves the most semantically relevant historical events and injects them as context into the LLM prompt. The agent reasons: *"In 4 of 5 similar cases, price continued upward for at least 2 candles before reversing. Current risk score is low. Signal confidence: 0.78."*

### Step 4 — ACT
SAGE executes via AVE Cloud's proxy wallet skill — market orders, limit orders, or TP/SL brackets. Every trade decision is logged with its reasoning chain, the RAG context used, and the signal confidence score.

### Step 5 — LEARN
After execution, SAGE monitors the outcome. Win or loss, the result is written back into the knowledge base as an `outcome_event` linked to the original signal. Over time, SAGE builds a rich history of:
- Which patterns led to profitable trades
- Which chains/tokens showed the highest signal reliability
- Which market conditions caused the most false positives

This feedback loop means SAGE's RAG context gets progressively richer and more accurate — the agent literally improves with use.

---

## Quick Start

### Prerequisites
- Python 3.12+ and Node.js 20+
- AVE Cloud API key (https://cloud.ave.ai)
- Anthropic or OpenAI API key (for embeddings + LLM reasoning)

### One-command start
```bash
git clone https://github.com/your-handle/ave-sage
cd ave-sage
cp .env.example .env
# Edit .env with your API keys
bash run.sh all       # starts API (8000) + Web UI (3001) + Telegram bot
```

Individual modes:
```bash
bash run.sh api       # backend only
bash run.sh web       # web UI dev server only
bash run.sh bot       # Telegram bot only
bash run.sh build-ext # build Chrome extension → extension/dist/
```

### Load the Chrome extension
1. Run `bash run.sh build-ext`
2. Open Chrome → `chrome://extensions` → Enable Developer Mode
3. Click "Load unpacked" → select `extension/dist/`

### Docker Compose
```bash
docker-compose up
```

### OpenClaw Install
```
# Paste into your OpenClaw chat:
"Install the skill from https://github.com/your-handle/ave-sage"
```

---

## Configuration

```yaml
# config.yaml
ave:
  api_key: "${AVE_API_KEY}"
  api_plan: "normal"           # free / normal / pro
  chains: ["solana", "bsc"]    # chains to monitor

collection:
  significance_threshold: 0.6  # 0.0-1.0, filters noise
  price_change_min: 0.03       # 3% min move to capture
  volume_spike_multiplier: 2.5 # 2.5x avg volume = significant
  max_events_per_hour: 500     # rate limiting

memory:
  vector_db: "chromadb"        # chromadb | pgvector
  embedding_model: "text-embedding-3-small"
  collection_name: "ave_sage_memory"
  max_context_chunks: 8        # RAG retrieval limit
  similarity_threshold: 0.72

agent:
  llm_provider: "anthropic"    # anthropic | openai
  reasoning_model: "claude-sonnet-4-20250514"
  trade_confidence_min: 0.70   # minimum to execute
  dry_run: true                # set false for live trades
  max_position_usd: 50.0       # per-trade cap

dashboard:
  host: "0.0.0.0"
  port: 8000
  enable_websocket: true
```

---

## OpenClaw Skill Manifest

AVE SAGE registers as a native OpenClaw skill. Once installed, your agent can:

```
"Watch SOL/USDC and alert me when a breakout pattern appears"
"What does SAGE's history say about BNB volume spikes?"
"Execute a buy on SOL with 20 USDC using SAGE's current signal"
"Show me SAGE's last 10 trade outcomes"
"What patterns has SAGE learned about Base chain tokens?"
```

---

## Dataset Schema

Every memory unit written to the knowledge base follows this schema:

```json
{
  "id": "evt_sol_1714123456_px",
  "type": "market_event",
  "chain": "solana",
  "token": "So11111111111111111111111111111111111111112",
  "token_symbol": "SOL",
  "timestamp": 1714123456,
  "price_usd": 142.30,
  "price_change_1h": 0.043,
  "volume_multiplier": 3.2,
  "holder_delta": 145,
  "risk_score": 0.12,
  "signal_type": "volume_breakout",
  "signal_confidence": 0.81,
  "rag_text": "SOL recorded a 4.3% price increase over 1h with volume at 3.2x the 24h average. Holder count increased by 145. Risk score 0.12 (low). Signal: volume_breakout.",
  "linked_trade_id": null,
  "linked_outcome_id": null
}
```

---

## Roadmap

- [x] AVE REST collector (token search, price, kline, holders, risk)
- [x] AVE WSS stream daemon
- [x] Chunker + embedding pipeline
- [x] ChromaDB vector store integration
- [x] RAG query engine
- [x] Signal detector (breakout, reversal, accumulation, rug-risk)
- [x] SAGE reasoning agent
- [x] AVE proxy wallet trade execution
- [x] Outcome feedback writer
- [x] FastAPI dashboard with live WebSocket feed
- [x] OpenClaw skill manifest
- [x] Docker Compose full stack
- [ ] pgvector backend option
- [ ] Multi-agent SAGE swarm (one per chain)
- [ ] Backtesting mode against historical dataset
- [ ] Telegram alert integration
- [ ] SAGE knowledge base export (shareable dataset)

---

## License

MIT — build freely, fork generously, win hackathons.

---

*Built for the AVE Claw Hackathon 2026 — Hong Kong Web3 Festival*

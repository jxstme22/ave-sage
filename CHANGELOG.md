# CHANGELOG — AVE SAGE

## v1.3.0 — Self-Improvement Engine (2026-04-16)

Added trading guardrails, strategy performance tracking, and adaptive parameter self-tuning.
SAGE now learns from its own trade outcomes and adjusts risk, sizing, and confidence thresholds automatically.

---

### Trading Rules Engine (`core/rules_engine.py`)

- **9 pre-trade guardrail checks**: chain whitelist, token blacklist, risk score, liquidity floor, daily loss limit, drawdown halt, concurrent position cap, post-loss cooldown, position-vs-liquidity ratio.
- All trades must pass every rule before execution. Blocked trades are logged with the failing rule name and reason.
- Configurable via `config.yaml` agent settings or constructor dict.

### Strategy Ledger (`core/strategy_ledger.py`)

- **Per signal_type × chain performance tracking**: win rate, total trades, average win/loss percentages, cumulative P&L.
- JSON-persisted to `./data/strategy_ledger.json` — survives restarts.
- **SelfTuner**: Adaptive parameter optimization based on historical performance:
  - Win rate >60% → increase position size (up to 1.5×), relax confidence threshold.
  - Win rate <40% → decrease position size (min 0.3×), tighten confidence threshold.
  - R:R ratio adjustments for TP/SL percentages.
  - Minimum 5 samples before tuning activates.

### Dashboard Integration

- Intelligence loop now applies self-tuned parameters before LLM decisions.
- Rules engine gate blocks trades that fail any guardrail check, broadcasting `rule_blocked` events via WebSocket.
- Closed positions feed back into both the rules engine (daily P&L tracking) and strategy ledger (win/loss recording).
- **New API endpoints**: `/api/rules/status`, `/api/strategy/ledger`, `/api/strategy/tune`.

### Telegram Bot

- **3 new commands**: `/rules` (guardrail status), `/ledger` (strategy performance), `/tune` (trigger self-tuning).
- Total commands: 21.

### Trade Agent

- `Position` dataclass now includes `signal_type` for ledger tracking.
- `closed_positions()` output includes `signal_type` for downstream recording.

### Tests

- **27 new tests** in `tests/test_self_improvement.py`: rules engine (each rule + stateful accumulation), strategy ledger (persistence, win rate, edge cases), self-tuner (adaptive sizing, confidence, caps/floors, tune_all).
- **64/64 total tests passing.**

---

## v1.2.0 — Official AVE Cloud Skill SDK Integration (2026-04-16)

Migrated all AVE Cloud API calls to use the official [ave-cloud-skill](https://github.com/AveCloud/ave-cloud-skill) SDK.
Fixed critical mismatches in base URLs, endpoint paths, and trade API authentication.

---

### Official SDK Integration

- **Cloned `ave-cloud-skill`** repo into project root. SDK provides correct base URLs, HMAC signing, rate limiting, and typed responses.
- All modules now add `ave-cloud-skill/scripts` to `sys.path` and import from `ave.config`, `ave.headers`, `ave.http_async`.

### Data API Migration

- **skills/ave_data_rest.py**: Rewritten to use official SDK. Fixed base URL from `https://cloud.ave.ai/api/v2` → `https://data.ave-api.xyz/v2`. Fixed all endpoint paths:
  - Token search: `/token/search` → `/tokens`
  - Token detail: `/token/detail?chain=&address=` → `/tokens/{addr}-{chain}`
  - Klines: `/token/kline` → `/klines/token/{addr}-{chain}`
  - Risk: `/token/risk` → `/contracts/{addr}-{chain}`
  - Trending: `/token/trending` → `/tokens/trending`
  - Holders: `/token/holders` → `/tokens/top100/{addr}-{chain}`
  - Transactions: `/token/txs` → `/txs/{pair}-{chain}`
  - Added: batch price, rankings, wallet tokens, signals endpoints.
- **skills/ave_data_wss.py**: Updated WSS URL from `wss://stream.ave.ai/ws` → `wss://wss.ave-api.xyz`. Uses `ave_access_key` param.
- **core/collector.py**: Removed `httpx` dependency. Now uses `ave.http_async.async_get` with `ave.headers.data_headers()`. Fixed all endpoint paths to match official API. WSS collector uses official URL.

### Trade API Migration

- **skills/ave_trade_rest.py**: Complete rewrite. Fixed base URL from `https://cloud.ave.ai/api/v2` → `https://bot-api.ave.ai`. Fixed authentication from `X-API-KEY`+`X-SIGNATURE` (hex HMAC of body) → `AVE-ACCESS-KEY`+`AVE-ACCESS-TIMESTAMP`+`AVE-ACCESS-SIGN` (base64 HMAC of timestamp+method+path+body). Fixed all endpoints:
  - Market order: `/trade/proxy/order` → `/v1/thirdParty/tx/sendSwapOrder`
  - Limit order → `/v1/thirdParty/tx/sendLimitOrder`
  - Cancel → `/v1/thirdParty/tx/cancelLimitOrder`
  - Wallets → `/v1/thirdParty/user/generateWallet`, `/v1/thirdParty/user/getUserByAssetsId`
  - Query orders → `/v1/thirdParty/tx/getSwapOrder`, `/v1/thirdParty/tx/getLimitOrder`
  - Approve → `/v1/thirdParty/tx/approve`
  - Chain wallet quote → `/v1/thirdParty/chainWallet/getAmountOut`
- **agents/trade_agent.py**: Removed manual HMAC signing. Uses `ave.headers.trade_proxy_headers()` for correct signing. Price lookup uses official data endpoint `/tokens/{addr}-{chain}`. Live trades use `/v1/thirdParty/tx/sendSwapOrder`.

### Validation

- 488 Python files compile successfully
- 37/37 tests pass

---

## v1.1.0 — OpenRouter + Telegram Bot (2026-04-15)

Switched LLM to OpenRouter, added Telegram bot controller, created run scripts.

---

### Switch to OpenRouter

- **agents/sage_agent.py**: Replaced Anthropic SDK with direct OpenRouter HTTP calls (OpenAI-compatible `/v1/chat/completions`). Removed `anthropic` dependency entirely.
- **config.py**: Changed default `llm_provider` from `anthropic` to `openrouter`, default model to `anthropic/claude-sonnet-4-20250514` (OpenRouter format). Added `TelegramConfig` dataclass and `openrouter_api_key` field. Removed `anthropic_api_key`.
- **config.yaml**: Updated `agent.llm_provider` and `agent.reasoning_model`. Added `telegram` section.
- **dashboard/app.py**: Updated `SAGEAgent` init to use `settings.openrouter_api_key`.
- **requirements.txt**: Removed `anthropic==0.34.0`, added `python-telegram-bot==21.6`.
- **.env.example**: Replaced `ANTHROPIC_API_KEY` with `OPENROUTER_API_KEY`, added `TELEGRAM_BOT_TOKEN`.

### Telegram Bot Controller

- **scripts/telegram_bot.py**: Full-featured Telegram bot with 18 commands:
  - Status: `/start`, `/help`, `/status`, `/health`, `/config`, `/chains`
  - Memory: `/memory`, `/query`, `/ask`, `/memhealth`
  - Signals: `/signals`, `/decisions`, `/performance`
  - Trading: `/positions`, `/closed`, `/feedback`
  - Control: `/dryrun on|off`, `/model <name>` (admin-only)
  - Auto-registers command menu with Telegram via `set_my_commands`
  - Communicates with dashboard REST API (no direct DB access)
  - Admin restriction support via `telegram.admin_chat_ids` config

### Run Scripts

- **run.sh**: Unified startup script with 4 modes: `dashboard`, `bot`, `both`, `test`.
- **run.md**: Complete usage guide covering setup, env vars, run modes, API endpoints, Telegram commands, Docker, and project structure.
- **scripts/setup.sh**: Updated to use `.venv` directory, updated next-steps text.
- **scripts/__init__.py**: Created for module imports.

---

## v1.0.0 — Build Complete (2026-04-15)

Full build pass: bug fixes, new modules, feedback loop wiring, error recovery, and expanded test suite.

---

### Phase 1 — Critical Bug Fixes

- **agents/trade_agent.py**: Fixed `hmac.new()` → `hmac.HMAC()` (Python has no `hmac.new`).
- **agents/trade_agent.py**: Added `decision_id` field to `closed_positions()` output so outcomes can link back to the original SAGE decision.
- **agents/sage_agent.py**: Added `record_outcome_from_position(pos)` method — accepts a closed position dict, looks up the original `TradeDecision` by `decision_id`, and calls `record_outcome()` to close the learning loop.
- **config.py**: Fixed `load_settings()` to resolve `config.yaml` relative to the file's own directory (`os.path.dirname(os.path.abspath(__file__))`) instead of relying on `os.getcwd()`.
- **dashboard/app.py**: Wrapped the intelligence loop body in `try/except` with error logging and a 2-second pause on failure, preventing a single unhandled exception from killing the entire agent.

### Phase 2 — Skills Module (AVE Cloud API Wrappers)

- **skills/__init__.py**: Created package init exporting all three skill classes.
- **skills/ave_data_rest.py**: `AveDataRestSkill` — async REST wrapper for AVE Cloud data API (search, token details, price, klines, holders, trending, risk, transactions, ping).
- **skills/ave_data_wss.py**: `AveDataWssSkill` — WebSocket streaming wrapper with auto-reconnect, exponential backoff, and subscription management.
- **skills/ave_trade_rest.py**: `AveTradeRestSkill` — proxy wallet trading wrapper with HMAC-SHA256 signing (market/limit orders, cancel, positions, balance, trade history).

### Phase 3 — Feedback Module

- **core/feedback.py**: Created `FeedbackWriter` class.
  - `record()`: Computes PnL percentage, classifies outcome (win/loss/breakeven), builds an `outcome_event` chunk via `build_outcome_chunk()`, and upserts it to the vector store.
  - `stats()`: Returns win rate, total wins/losses, and average PnL — used by dashboard endpoints.

### Phase 4 — Memory Agent

- **agents/memory_agent.py**: Created `MemoryAgent` class.
  - `query()`: Natural-language search over the knowledge base with chain/token/type filters.
  - `get_token_history()`: Retrieve all memory for a specific token within a time window.
  - `get_signal_performance()`: Historical win rate and PnL stats for a signal type.
  - `cleanup_stale()`: Removes non-outcome chunks older than a configurable retention period.
  - `health()`: Full memory health report (chunk stats + outcome stats).

### Phase 5 — Setup & Environment

- **scripts/setup.sh**: Created automated setup script (venv creation, pip install, directory setup, env file template, Docker build option).
- **.env.example**: Created environment variable template documenting all required/optional keys.

### Phase 6 — Claude Plugin Manifest

- **.claude-plugin/plugin.json**: Created OpenClaw-compatible plugin manifest declaring SAGE's capabilities, API endpoints, and required permissions.

### Phase 7 — Wired Outcome Feedback Loop

- **dashboard/app.py**: Integrated `FeedbackWriter` and `MemoryAgent` into the application lifecycle.
  - Added `_feedback` and `_memory` globals, initialized in lifespan.
  - Added `_closed_broadcast` set to prevent duplicate outcome recording on repeated position monitor cycles.
  - Wired `_sage.record_outcome_from_position(pos)` call in the position monitor loop — position closes now feed back into SAGE's memory.
  - Upgraded `/api/sage/ask` endpoint to use `MemoryAgent` for natural-language knowledge base queries.
  - Added new endpoints:
    - `GET /api/feedback/stats` — outcome stats (win rate, totals).
    - `GET /api/memory/health` — memory health report.
    - `GET /api/signals/performance?signal_type=...&chain=...` — signal-type performance history.

### Phase 8 — Error Recovery & Resilience

- **core/collector.py**:
  - Added retry with exponential backoff (3 attempts, 1s → 2s → 4s) to `_get()` REST method.
  - Added crash recovery with auto-restart loop in `CollectorOrchestrator.run()` — fatal errors trigger a 5-second pause then restart.
  - Added 2-second error pause in `_rest_loop()` to prevent tight error loops.
- **dashboard/app.py**:
  - Added graceful shutdown: `await collector.stop()` + `loop_task.cancel()` in lifespan teardown.
  - Added `except` clause to position monitor `try` block (syntax fix).

### Phase 9 — Expanded Test Coverage

- **tests/test_extended.py**: Created 20 new tests across 5 test classes:
  - `TestVectorStore` (8 tests): upsert, idempotency, batch upsert, semantic query, chain filter, chunk type filter, stats, get_recent.
  - `TestRAGEngine` (4 tests): context retrieval, empty store handling, confidence boost neutral/positive.
  - `TestFeedbackWriter` (3 tests): win recording, loss recording, stats tracking with win rate.
  - `TestMemoryAgent` (3 tests): query returns context, empty store query, health report.
  - `TestPipelineIntegration` (2 tests): end-to-end event → chunk → embed → RAG retrieval; signal detection → outcome recording → outcome queryable.
- Used `tempfile.mkdtemp()` per test for ChromaDB isolation (prevents SQLite locking between tests).

### Phase 10 — Full Stack Validation

- Python 3.12.10 venv created at `.venv/`.
- All 14 Python source files compile clean (`py_compile`).
- **37 tests pass, 0 failures** (pytest 9.0.3).

---

### Test Summary

| Suite | Tests | Status |
|-------|-------|--------|
| SignificanceScorer | 4 | ✅ |
| Chunker | 6 | ✅ |
| SignalDetector | 7 | ✅ |
| VectorStore | 8 | ✅ |
| RAGEngine | 4 | ✅ |
| FeedbackWriter | 3 | ✅ |
| MemoryAgent | 3 | ✅ |
| Pipeline Integration | 2 | ✅ |
| **Total** | **37** | **All pass** |

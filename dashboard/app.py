"""
AVE SAGE — Dashboard
FastAPI server exposing REST endpoints and WebSocket live feed.
Serves the intelligence loop state, memory stats, decisions, and positions.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import httpx
import uvicorn
from config import settings
from core.collector import CollectorOrchestrator
from core.chunker import Chunker
from core.embedder import VectorStore
from core.rag_engine import RAGEngine
from core.signal_detector import SignalDetector
from core.feedback import FeedbackWriter
from core.rules_engine import TradingRulesEngine
from core.strategy_ledger import StrategyLedger, SelfTuner
from agents.sage_agent import SAGEAgent
from agents.trade_agent import TradeAgent
from agents.memory_agent import MemoryAgent

logger = logging.getLogger(__name__)

# ─── Global state (injected at startup) ───────────────────────────────────────
_store: Optional[VectorStore] = None
_sage: Optional[SAGEAgent] = None
_trade: Optional[TradeAgent] = None
_feedback: Optional[FeedbackWriter] = None
_memory: Optional[MemoryAgent] = None
_rules: Optional[TradingRulesEngine] = None
_ledger: Optional[StrategyLedger] = None
_tuner: Optional[SelfTuner] = None
_collector = None
_ws_clients: list[WebSocket] = []


async def broadcast(msg: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ─── App Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _sage, _trade, _feedback, _memory, _rules, _ledger, _tuner, _collector

    # Init components
    _store = VectorStore(
        persist_dir=settings.memory.persist_dir,
        collection_name=settings.memory.collection_name,
        embedding_provider=settings.memory.embedding_provider,
        embedding_model=settings.memory.embedding_model,
        openai_api_key=settings.openai_api_key,
    )
    rag = RAGEngine(_store, settings.memory.__dict__)
    _feedback = FeedbackWriter(_store)
    _memory = MemoryAgent(_store, _feedback, settings.memory.__dict__)
    _rules = TradingRulesEngine(settings.agent.__dict__)
    _ledger = StrategyLedger(persist_path="./data/strategy_ledger.json")
    _tuner = SelfTuner(_ledger, settings.agent.__dict__)
    _sage = SAGEAgent(rag, _store, settings.openrouter_api_key, settings.agent.__dict__)
    _trade = TradeAgent(settings.ave.api_key, settings.ave.secret_key, settings.agent.__dict__)

    collector = CollectorOrchestrator(
        api_key=settings.ave.api_key,
        api_plan=settings.ave.api_plan,
        chains=settings.ave.chains,
        cfg=settings.collection.__dict__,
    )
    chunker = Chunker()
    detector = SignalDetector(settings.agent.__dict__)

    # Track closed position IDs to avoid duplicate broadcasts
    _closed_broadcast: set[str] = set()

    # Main intelligence loop
    async def intelligence_loop():
        async with _trade:
            asyncio.create_task(collector.run())
            asyncio.create_task(position_monitor_loop())

            async for raw_evt in collector.events():
                try:
                    # 1. Chunk → store in memory
                    chunk = chunker.process(raw_evt)
                    if chunk:
                        _store.upsert(chunk)
                        await broadcast({"type": "memory_update", "chunk_type": chunk.chunk_type,
                                         "token": chunk.token_symbol, "chain": chunk.chain,
                                         "text": chunk.rag_text[:120]})

                    # 2. Detect signals
                    signals = detector.ingest(raw_evt)
                    for signal in signals:
                        await broadcast({"type": "signal", "signal_type": signal.signal_type,
                                         "token": signal.token_symbol, "chain": signal.chain,
                                         "confidence": signal.base_confidence})

                        # 3. Reason + decide
                        decision = await _sage.process_signal(signal)
                        await broadcast({"type": "decision", "action": decision.action,
                                         "token": decision.signal.token_symbol,
                                         "confidence": decision.final_confidence,
                                         "reasoning": decision.reasoning[:100]})

                        # 4. Apply self-tuned parameters
                        if decision.action in ("buy", "sell"):
                            tuned = _tuner.tune(decision.signal.signal_type, decision.signal.chain)
                            if tuned["source"] == "tuned":
                                decision.amount_usd *= tuned["size_multiplier"]
                                if decision.final_confidence < tuned["confidence_min"]:
                                    decision.action = "watch"
                                    decision.reasoning += f" [Self-tuner: conf below tuned min {tuned['confidence_min']:.2f}]"

                        # 5. Rules engine gate
                        if decision.action in ("buy", "sell"):
                            _rules.set_open_position_count(len(_trade.open_positions()))
                            verdict = _rules.evaluate(decision)
                            if not verdict.allowed:
                                decision.action = "skip"
                                decision.reasoning += f" [BLOCKED by {verdict.rule_name}: {verdict.reason}]"
                                await broadcast({"type": "rule_blocked",
                                                 "rule": verdict.rule_name,
                                                 "reason": verdict.reason,
                                                 "token": decision.signal.token_symbol})

                        # 6. Execute if actionable
                        if decision.action in ("buy", "sell"):
                            position = await _trade.execute(decision)
                            if position:
                                await broadcast({"type": "trade_opened",
                                                 "position_id": position.position_id,
                                                 "token": position.token_symbol,
                                                 "action": position.action,
                                                 "amount_usd": position.amount_usd,
                                                 "entry_price": position.entry_price})
                except Exception as e:
                    logger.error(f"[SAGE] Intelligence loop error: {e}", exc_info=True)
                    await asyncio.sleep(2)  # brief pause before processing next event

    async def position_monitor_loop():
        while True:
            await asyncio.sleep(30)
            if not _trade:
                continue
            try:
                await _trade.update_positions()
                for pos in _trade.closed_positions():
                    if pos["id"] in _closed_broadcast:
                        continue
                    _closed_broadcast.add(pos["id"])
                    # Record outcome back into SAGE memory (learning loop)
                    _sage.record_outcome_from_position(pos)
                    # Update rules engine + strategy ledger
                    pnl_usd = (pos.get("pnl_pct", 0) / 100) * pos.get("amount_usd", 0)
                    _rules.record_trade_result(pnl_usd)
                    if pos.get("signal_type"):
                        pnl_pct = pos.get("pnl_pct", 0) / 100
                        _ledger.record_outcome(pos["signal_type"], pos.get("chain", ""), pnl_pct)
                    await broadcast({"type": "trade_closed",
                                     "position_id": pos["id"],
                                     "pnl_pct": pos["pnl_pct"],
                                     "token": pos["token"]})
            except Exception as e:
                logger.error(f"[SAGE] Position monitor error: {e}")

    _collector = collector  # expose for /api/scan endpoint
    loop_task = asyncio.create_task(intelligence_loop())
    logger.info("[SAGE] Intelligence loop started")
    yield
    # Graceful shutdown
    await collector.stop()
    loop_task.cancel()
    logger.info("[SAGE] Shutdown complete")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="AVE SAGE", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time()), "memory_chunks": _store.count() if _store else 0}

@app.get("/api/memory/stats")
async def memory_stats():
    if not _store:
        return {"error": "not initialized"}
    return _store.stats()

@app.get("/api/memory/recent")
async def recent_memory(chain: str = "solana", hours: int = 24, n: int = 20):
    if not _store:
        return []
    return _store.get_recent(chain=chain, lookback_hours=hours, limit=n)

@app.get("/api/memory/query")
async def query_memory(q: str, chain: Optional[str] = None, n: int = 8):
    if not _store:
        return []
    return _store.query(q, n_results=n, chain_filter=chain)

@app.get("/api/decisions")
async def recent_decisions(n: int = 20):
    if not _sage:
        return []
    return _sage.recent_decisions(n)

@app.get("/api/positions/open")
async def open_positions():
    if not _trade:
        return []
    return _trade.open_positions()

@app.get("/api/positions/closed")
async def closed_positions():
    if not _trade:
        return []
    return _trade.closed_positions()

@app.get("/api/sage/ask")
async def ask_sage(q: str, chain: Optional[str] = None):
    """Conversational chat with SAGE — uses LLM + RAG context."""
    if not _sage:
        return {"answer": "SAGE not initialized"}
    return await _sage.chat(q, chain=chain)

@app.get("/api/feedback/stats")
async def feedback_stats():
    """Trade outcome statistics — win rate, total outcomes."""
    if not _feedback:
        return {"error": "not initialized"}
    return _feedback.stats()

@app.get("/api/memory/health")
async def memory_health():
    """Full knowledge base health report."""
    if not _memory:
        return {"error": "not initialized"}
    return _memory.health()

@app.get("/api/signals/performance")
async def signal_performance(signal_type: str, chain: Optional[str] = None):
    """Historical performance for a specific signal type."""
    if not _memory:
        return {"error": "not initialized"}
    return _memory.get_signal_performance(signal_type, chain=chain)

@app.get("/api/rules/status")
async def rules_status():
    """Current trading rules engine state."""
    if not _rules:
        return {"error": "not initialized"}
    return _rules.status()

@app.get("/api/strategy/ledger")
async def strategy_ledger():
    """All strategy records with win rates and tuned parameters."""
    if not _ledger:
        return {"error": "not initialized"}
    return _ledger.all_records()

@app.get("/api/strategy/tune")
async def strategy_tune():
    """Re-tune all strategies and return results."""
    if not _tuner:
        return {"error": "not initialized"}
    return _tuner.tune_all()


# ─── WebSocket Live Feed ──────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_feed(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


# ─── Dashboard UI ─────────────────────────────────────────────────────────────

@app.get("/api/wallet/balance")
async def wallet_balance():
    """Get proxy wallet SOL balance via AVE API + Solana RPC."""
    import base64, datetime, hashlib, hmac as hmac_mod
    try:
        api_key = settings.ave.api_key
        secret_key = settings.ave.secret_key
        assets_id = settings.agent.assets_id
        if not assets_id:
            return {"error": "No assets_id configured"}

        # HMAC sign for AVE trade proxy API
        sign_path = "/v1/thirdParty/user/getUserByAssetsId"
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        message = timestamp + "GET" + sign_path
        h = hmac_mod.new(secret_key.encode(), message.encode(), hashlib.sha256)
        signature = base64.b64encode(h.digest()).decode()

        url = f"https://bot-api.ave.ai{sign_path}?assetsIds={assets_id}"
        headers = {
            "AVE-ACCESS-KEY": api_key,
            "AVE-ACCESS-TIMESTAMP": timestamp,
            "AVE-ACCESS-SIGN": signature,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers)
            user_data = r.json()

        if user_data.get("status") != 200:
            return {"error": f"AVE API: {user_data.get('msg', 'unknown error')}"}

        wallet_info = user_data.get("data", [{}])[0] if user_data.get("data") else {}
        addresses = {a["chain"]: a["address"] for a in wallet_info.get("addressList", [])}
        sol_address = addresses.get("solana", "")

        # Get SOL balance via Solana RPC
        sol_balance = 0.0
        if sol_address:
            async with httpx.AsyncClient(timeout=10.0) as client:
                rpc_resp = await client.post("https://api.mainnet-beta.solana.com", json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getBalance",
                    "params": [sol_address],
                })
                lamports = rpc_resp.json().get("result", {}).get("value", 0)
                sol_balance = lamports / 1e9

        return {
            "chain": "solana",
            "address": sol_address,
            "sol_balance": round(sol_balance, 6),
            "assets_id": assets_id,
            "wallet_name": wallet_info.get("assetsName", ""),
        }
    except Exception as e:
        logger.error(f"[WALLET] Balance fetch failed: {e}")
        return {"error": str(e)}


@app.get("/api/wallet/holdings")
async def wallet_holdings():
    """Get SPL token holdings from proxy wallet via Solana RPC."""
    try:
        # First get the wallet address
        bal = await wallet_balance()
        sol_address = bal.get("address", "")
        if not sol_address:
            return {"holdings": [], "error": "No wallet address"}

        holdings = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get SPL token accounts
            rpc_resp = await client.post("https://api.mainnet-beta.solana.com", json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    sol_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"},
                ],
            })
            result = rpc_resp.json().get("result", {}).get("value", [])
            for acct in result:
                info = acct.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                amount = info.get("tokenAmount", {})
                ui_amount = float(amount.get("uiAmount", 0) or 0)
                if ui_amount > 0:
                    holdings.append({
                        "mint": info.get("mint", ""),
                        "amount": ui_amount,
                        "decimals": amount.get("decimals", 0),
                    })

        return {"holdings": holdings, "sol_balance": bal.get("sol_balance", 0)}
    except Exception as e:
        logger.error(f"[WALLET] Holdings fetch failed: {e}")
        return {"holdings": [], "error": str(e)}


@app.post("/api/scan")
async def trigger_scan():
    """Manually trigger one REST collection cycle across all chains."""
    if not _collector:
        return {"error": "Collector not initialised"}
    try:
        count = await asyncio.wait_for(_collector.poll_once(), timeout=45)
        return {"status": "ok", "events_queued": count, "chains": _collector.chains}
    except asyncio.TimeoutError:
        return {"status": "partial", "message": "Scan timed out after 45s", "chains": _collector.chains}


@app.post("/api/trade/execute")
async def manual_trade(token: str, chain: str = "solana", action: str = "buy",
                       amount_usd: float = 1.0, symbol: str = ""):
    """Manually trigger a trade — for demo and testing."""
    if not _trade:
        return {"error": "Trade agent not initialized"}
    from agents.sage_agent import TradeDecision
    from core.signal_detector import SignalPacket
    import uuid as _uuid
    signal = SignalPacket(
        signal_type="manual_trade",
        chain=chain,
        token=token,
        token_symbol=symbol or token[:8],
        timestamp=int(time.time()),
        base_confidence=0.95,
        direction="long" if action == "buy" else "short",
        trigger_events=[],
        conditions={"price_usd": "0", "source": "manual"},
    )
    decision = TradeDecision(
        decision_id=_uuid.uuid4().hex[:12],
        signal=signal,
        action=action,
        final_confidence=0.95,
        amount_usd=amount_usd,
        reasoning="Manual trade triggered via API",
        rag_context_summary="",
    )
    try:
        position = await _trade.execute(decision)
        if position:
            return {
                "status": "ok",
                "position_id": position.position_id,
                "tx_hash": position.tx_hash,
                "entry_price": position.entry_price,
                "amount_usd": position.amount_usd,
                "action": position.action,
                "error": position.error,
            }
        return {"status": "skipped", "reason": "Trade returned None (duplicate or price=0)"}
    except Exception as e:
        logger.error(f"[TRADE] Manual trade error: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AVE SAGE — Intelligence Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #080c14;
    --surface: #0d1520;
    --border: #1a2840;
    --accent: #00d4ff;
    --green: #00ff88;
    --red: #ff3355;
    --yellow: #ffcc00;
    --text: #c8d8f0;
    --muted: #4a6080;
    --font-mono: 'JetBrains Mono', monospace;
    --font-ui: 'Space Grotesk', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font-ui); min-height: 100vh; }
  header {
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(13, 21, 32, 0.9);
    backdrop-filter: blur(8px);
    position: sticky; top: 0; z-index: 100;
  }
  .logo { font-family: var(--font-mono); font-weight: 700; font-size: 18px; color: var(--accent); letter-spacing: 2px; }
  .logo span { color: var(--green); }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .status-row { display: flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 12px; color: var(--muted); }
  main { display: grid; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: auto auto; gap: 16px; padding: 24px 32px; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
    position: relative;
    overflow: hidden;
  }
  .card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, var(--accent), transparent); }
  .card-title { font-family: var(--font-mono); font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }
  .stat-big { font-family: var(--font-mono); font-size: 36px; font-weight: 700; color: var(--accent); }
  .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .feed { grid-column: 1 / -1; }
  .feed-list { list-style: none; max-height: 320px; overflow-y: auto; }
  .feed-list::-webkit-scrollbar { width: 4px; }
  .feed-list::-webkit-scrollbar-track { background: var(--bg); }
  .feed-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  .feed-item {
    display: grid;
    grid-template-columns: 80px 120px 1fr;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-family: var(--font-mono);
    font-size: 12px;
    animation: fadeIn 0.3s ease;
  }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
  .tag { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
  .tag-memory { background: rgba(0, 212, 255, 0.15); color: var(--accent); border: 1px solid rgba(0, 212, 255, 0.3); }
  .tag-signal { background: rgba(255, 204, 0, 0.15); color: var(--yellow); border: 1px solid rgba(255, 204, 0, 0.3); }
  .tag-decision { background: rgba(0, 255, 136, 0.15); color: var(--green); border: 1px solid rgba(0, 255, 136, 0.3); }
  .tag-trade { background: rgba(255, 51, 85, 0.15); color: var(--red); border: 1px solid rgba(255, 51, 85, 0.3); }
  .feed-text { color: var(--text); line-height: 1.5; }
  .confidence { color: var(--muted); }
  #chunks-count, #signals-count, #decisions-count { transition: all 0.3s; }
</style>
</head>
<body>
<header>
  <div class="logo">AVE <span>SAGE</span></div>
  <div class="status-row">
    <div class="status-dot"></div>
    <span id="status-text">Connecting...</span>
  </div>
</header>
<main>
  <div class="card">
    <div class="card-title">Memory Chunks</div>
    <div class="stat-big" id="chunks-count">—</div>
    <div class="stat-label">Embeddings in knowledge base</div>
  </div>
  <div class="card">
    <div class="card-title">Signals Detected</div>
    <div class="stat-big" id="signals-count">0</div>
    <div class="stat-label">This session</div>
  </div>
  <div class="card">
    <div class="card-title">Trade Decisions</div>
    <div class="stat-big" id="decisions-count">0</div>
    <div class="stat-label">Actions taken by SAGE</div>
  </div>
  <div class="card feed">
    <div class="card-title">Live Intelligence Feed</div>
    <ul class="feed-list" id="feed"></ul>
  </div>
</main>
<script>
  let signals = 0, decisions = 0;
  const feed = document.getElementById('feed');

  function addFeedItem(type, token, chain, text) {
    const tagClass = 'tag-' + type;
    const li = document.createElement('li');
    li.className = 'feed-item';
    li.innerHTML = `
      <span class="tag ${tagClass}">${type}</span>
      <span class="confidence">${token}/${chain}</span>
      <span class="feed-text">${text}</span>
    `;
    feed.prepend(li);
    if (feed.children.length > 100) feed.lastChild.remove();
  }

  async function loadStats() {
    const r = await fetch('/api/memory/stats');
    const d = await r.json();
    document.getElementById('chunks-count').textContent = d.total_chunks || 0;
  }

  const ws = new WebSocket('ws://' + location.host + '/ws');
  ws.onopen = () => document.getElementById('status-text').textContent = 'LIVE — Intelligence Loop Active';
  ws.onclose = () => document.getElementById('status-text').textContent = 'Disconnected';
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'memory_update') {
      loadStats();
      addFeedItem('memory', msg.token, msg.chain, msg.text);
    } else if (msg.type === 'signal') {
      signals++;
      document.getElementById('signals-count').textContent = signals;
      addFeedItem('signal', msg.token, msg.chain,
        `${msg.signal_type} | confidence: ${(msg.confidence * 100).toFixed(0)}%`);
    } else if (msg.type === 'decision') {
      decisions++;
      document.getElementById('decisions-count').textContent = decisions;
      addFeedItem('decision', msg.token, '-',
        `${msg.action.toUpperCase()} | ${(msg.confidence*100).toFixed(0)}% — ${msg.reasoning}`);
    } else if (msg.type === 'trade_opened') {
      addFeedItem('trade', msg.token, '-',
        `${msg.action.toUpperCase()} $${msg.amount_usd} @ ${msg.entry_price}`);
    } else if (msg.type === 'trade_closed') {
      addFeedItem('trade', msg.token, '-',
        `CLOSED PnL: ${msg.pnl_pct > 0 ? '+' : ''}${msg.pnl_pct}%`);
    }
  };

  loadStats();
  setInterval(loadStats, 10000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=False)

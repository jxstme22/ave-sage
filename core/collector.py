"""
AVE SAGE — Collector
Streams and polls AVE Cloud API for market events across chains.
Uses the official ave-cloud-skill SDK for correct URLs and headers.
Feeds raw data into the chunker pipeline.
"""

import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Callable, AsyncIterator
import websockets
from config import settings

# Add the official SDK to the Python path
_SDK_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ave-cloud-skill", "scripts",
)
if _SDK_SCRIPTS not in sys.path:
    sys.path.insert(0, _SDK_SCRIPTS)

from ave.config import V2_BASE, WSS_BASE
from ave.headers import data_headers
from ave.http_async import async_get

logger = logging.getLogger(__name__)

# ─── Event Model ─────────────────────────────────────────────────────────────

@dataclass
class RawMarketEvent:
    source: str                    # "rest" | "wss"
    event_type: str                # "price" | "swap" | "kline" | "holder" | "trending" | "risk"
    chain: str
    token: str
    token_symbol: str
    timestamp: int
    data: dict
    significance: float = 0.0      # computed after collection


# ─── Significance Scorer ─────────────────────────────────────────────────────

class SignificanceScorer:
    """
    Scores raw events 0.0–1.0. Only events above threshold reach the pipeline.
    Prevents noisy micro-movements from polluting the knowledge base.
    """

    def __init__(self, cfg: dict):
        self.price_min = cfg.get("price_change_min", 0.03)
        self.volume_mult = cfg.get("volume_spike_multiplier", 2.5)
        self.threshold = cfg.get("significance_threshold", 0.6)

    def score(self, event: RawMarketEvent) -> float:
        d = event.data
        score = 0.0

        if event.event_type == "price":
            change = abs(d.get("price_change_1h", 0.0))
            score = min(change / 0.15, 1.0)  # 15% move = full score

        elif event.event_type == "swap":
            usd_value = d.get("amount_usd", 0)
            score = min(usd_value / 20_000, 1.0)  # $20k swap = full score (tuned for small-cap tokens)

        elif event.event_type == "kline":
            vol_mult = d.get("volume_multiplier", 1.0)
            # 2.5x = threshold, 5x = full score
            score = min((vol_mult - 1.0) / 4.0, 1.0)

        elif event.event_type == "holder":
            delta = abs(d.get("holder_delta", 0))
            score = min(delta / 500, 1.0)

        elif event.event_type == "trending":
            rank = d.get("trending_rank", 100)
            score = max(0.0, (100 - rank) / 100)

        elif event.event_type == "risk":
            risk = d.get("risk_score", 0.0)
            # High risk events are always significant
            score = risk if risk > 0.7 else risk * 0.5

        return round(score, 4)

    def is_significant(self, event: RawMarketEvent) -> bool:
        event.significance = self.score(event)
        return event.significance >= self.threshold


# ─── REST Collector ───────────────────────────────────────────────────────────

class AveRestCollector:
    """
    Polls AVE Cloud REST endpoints on a configurable interval.
    Uses official SDK: base URL https://data.ave-api.xyz/v2
    """

    def __init__(self, api_key: str, chains: list[str], scorer: SignificanceScorer):
        self.api_key = api_key
        self.chains = chains
        self.scorer = scorer

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def _get(self, path: str, params: dict = None) -> dict:
        url = f"{V2_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        last_err = None
        for attempt in range(3):
            try:
                resp = await async_get(url, data_headers())
                return resp.json()
            except Exception as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(1.5 ** attempt)
        logger.warning(f"REST request failed after 3 attempts: {path} — {last_err}")
        return {}

    async def get_trending(self, chain: str, limit: int = 20) -> list[RawMarketEvent]:
        data = await self._get("/tokens/trending", {"chain": chain, "page_size": limit})
        events = []
        raw_data = data.get("data", {})
        # API returns {"data": {"tokens": [...], ...}} or {"data": [...]}
        if isinstance(raw_data, dict):
            token_list = raw_data.get("tokens", [])
        elif isinstance(raw_data, list):
            token_list = raw_data
        else:
            token_list = []
        for i, token in enumerate(token_list):
            if isinstance(token, str):
                # "address-chain" string fallback
                addr_part = token.rsplit("-", 1)[0]
                token = {"token": addr_part, "symbol": addr_part[:6].upper()}
            evt = RawMarketEvent(
                source="rest",
                event_type="trending",
                chain=chain,
                token=token.get("token", token.get("address", "")),
                token_symbol=token.get("symbol", "UNKNOWN"),
                timestamp=int(time.time()),
                data={
                    "trending_rank": i + 1,
                    "price_usd": float(token.get("current_price_usd", 0)),
                    "price_change_1h": float(token.get("token_price_change_1h", 0)),
                    "volume_24h": float(token.get("token_tx_volume_usd_24h", 0)),
                    "market_cap": float(token.get("market_cap", 0)),
                    "name": token.get("name", ""),
                    "holders": token.get("holders", 0),
                    "ave_risk_level": token.get("ave_risk_level", -1),
                },
            )
            if self.scorer.is_significant(evt):
                events.append(evt)
        return events

    async def get_price_and_risk(self, chain: str, token_address: str, symbol: str) -> Optional[RawMarketEvent]:
        data = await self._get(f"/tokens/{token_address}-{chain}")
        td = data.get("data", {})
        if not td:
            return None

        risk_data = await self._get(f"/contracts/{token_address}-{chain}")
        rd = risk_data.get("data", {})
        risk_score = float(rd.get("risk_score", rd.get("ave_risk_level", 0)))

        evt = RawMarketEvent(
            source="rest",
            event_type="price",
            chain=chain,
            token=token_address,
            token_symbol=symbol,
            timestamp=int(time.time()),
            data={
                "price_usd": float(td.get("current_price_usd", td.get("price", 0))),
                "price_change_1h": float(td.get("token_price_change_1h", td.get("price_change_1h", 0))),
                "price_change_24h": float(td.get("token_price_change_24h", td.get("price_change_24h", 0))),
                "volume_24h": float(td.get("token_tx_volume_usd_24h", td.get("volume_24h", 0))),
                "liquidity_usd": float(td.get("tvl", td.get("liquidity", 0))),
                "holder_count": td.get("holders", td.get("holder_count", 0)),
                "risk_score": risk_score,
            },
        )
        return evt if self.scorer.is_significant(evt) else None

    async def get_klines(self, chain: str, token_address: str, symbol: str, interval: int = 900) -> list[RawMarketEvent]:
        data = await self._get(f"/klines/token/{token_address}-{chain}", {
            "interval": interval,
            "limit": 48
        })
        klines = data.get("data", [])
        if len(klines) < 2:
            return []

        avg_volume = sum(k.get("volume", 0) for k in klines[:-1]) / max(len(klines) - 1, 1)
        latest = klines[-1]
        current_volume = latest.get("volume", 0)
        volume_multiplier = current_volume / max(avg_volume, 1)

        evt = RawMarketEvent(
            source="rest",
            event_type="kline",
            chain=chain,
            token=token_address,
            token_symbol=symbol,
            timestamp=int(latest.get("timestamp", time.time())),
            data={
                "interval": interval,
                "open": latest.get("open", 0),
                "high": latest.get("high", 0),
                "low": latest.get("low", 0),
                "close": latest.get("close", 0),
                "volume": current_volume,
                "volume_multiplier": round(volume_multiplier, 2),
                "avg_volume_48": round(avg_volume, 2),
                "candle_body_pct": abs(latest.get("close", 0) - latest.get("open", 0)) / max(latest.get("open", 1), 0.0001),
            },
        )
        return [evt] if self.scorer.is_significant(evt) else []

    async def get_large_swaps(self, chain: str, token_address: str, symbol: str, min_usd: float = 5000) -> list[RawMarketEvent]:
        data = await self._get(f"/txs/{token_address}-{chain}", {
            "limit": 50,
        })
        raw_data = data.get("data", {})
        # API returns {"data": {"txs": [...]}} or {"data": [...]}
        if isinstance(raw_data, dict):
            tx_list = raw_data.get("txs", [])
        elif isinstance(raw_data, list):
            tx_list = raw_data
        else:
            tx_list = []
        events = []
        for tx in tx_list:
            usd_val = tx.get("amount_usd", 0)
            if usd_val < min_usd:
                continue
            evt = RawMarketEvent(
                source="rest",
                event_type="swap",
                chain=chain,
                token=token_address,
                token_symbol=symbol,
                timestamp=tx.get("timestamp", int(time.time())),
                data={
                    "tx_hash": tx.get("tx_hash", ""),
                    "swap_type": tx.get("type", "unknown"),  # buy | sell
                    "amount_usd": usd_val,
                    "amount_token": tx.get("amount_token", 0),
                    "price_impact": tx.get("price_impact", 0),
                    "wallet": tx.get("wallet", ""),
                },
            )
            if self.scorer.is_significant(evt):
                events.append(evt)
        return events

    async def poll_chain(self, chain: str, emit_callback: Callable[[RawMarketEvent], None]):
        """Full REST poll cycle for one chain."""
        logger.info(f"[REST] Polling {chain}...")
        trending = await self.get_trending(chain)
        for evt in trending:
            emit_callback(evt)

        for evt in trending[:10]:  # deep-dive top 10 trending
            price_evt = await self.get_price_and_risk(chain, evt.token, evt.token_symbol)
            if price_evt:
                emit_callback(price_evt)

            kline_events = await self.get_klines(chain, evt.token, evt.token_symbol)
            for ke in kline_events:
                emit_callback(ke)

            swap_events = await self.get_large_swaps(chain, evt.token, evt.token_symbol)
            for se in swap_events:
                emit_callback(se)

            await asyncio.sleep(0.3)  # gentle rate limiting


# ─── WSS Collector ────────────────────────────────────────────────────────────

class AveWssCollector:
    """
    Connects to AVE Cloud WebSocket for real-time price and transaction streams.
    Uses official SDK WSS URL: wss://wss.ave-api.xyz
    Requires API_PLAN=pro.
    """

    def __init__(self, api_key: str, scorer: SignificanceScorer):
        self.api_key = api_key
        self.scorer = scorer
        self._active_subs: dict[str, str] = {}
        self._ws = None

    async def subscribe(self, chain: str, token: str, symbol: str):
        self._active_subs[token] = {"chain": chain, "symbol": symbol}
        if self._ws:
            await self._ws.send(json.dumps({
                "op": "subscribe",
                "channel": "price",
                "chain": chain,
                "address": token,
            }))

    async def stream(self, emit_callback: Callable[[RawMarketEvent], None]):
        from ave.config import get_api_key
        key = self.api_key or get_api_key()
        uri = f"{WSS_BASE}?ave_access_key={key}"
        async with websockets.connect(uri, ping_interval=20) as ws:
            self._ws = ws
            logger.info("[WSS] Connected to AVE stream")
            async for raw_msg in ws:
                try:
                    msg = json.loads(raw_msg)
                    evt = self._parse_wss_message(msg)
                    if evt and self.scorer.is_significant(evt):
                        emit_callback(evt)
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.warning(f"[WSS] Parse error: {e}")

    def _parse_wss_message(self, msg: dict) -> Optional[RawMarketEvent]:
        channel = msg.get("channel", "")
        chain = msg.get("chain", "unknown")
        token = msg.get("address", "")
        sub = self._active_subs.get(token, {})
        symbol = sub.get("symbol", "UNKNOWN") if sub else "UNKNOWN"

        if channel == "price":
            return RawMarketEvent(
                source="wss",
                event_type="price",
                chain=chain,
                token=token,
                token_symbol=symbol,
                timestamp=int(time.time()),
                data={
                    "price_usd": msg.get("price", 0),
                    "price_change_1h": msg.get("change_1h", 0),
                    "price_change_24h": msg.get("change_24h", 0),
                    "volume_24h": msg.get("volume_24h", 0),
                },
            )
        elif channel == "tx":
            return RawMarketEvent(
                source="wss",
                event_type="swap",
                chain=chain,
                token=token,
                token_symbol=symbol,
                timestamp=msg.get("timestamp", int(time.time())),
                data={
                    "tx_hash": msg.get("hash", ""),
                    "swap_type": msg.get("type", "unknown"),
                    "amount_usd": msg.get("usd_value", 0),
                    "amount_token": msg.get("token_amount", 0),
                    "price_impact": msg.get("price_impact", 0),
                    "wallet": msg.get("wallet", ""),
                },
            )
        return None


# ─── Unified Collector Orchestrator ──────────────────────────────────────────

class CollectorOrchestrator:
    """
    Runs REST polling + optional WSS streaming in parallel.
    Emits RawMarketEvent objects to a shared asyncio.Queue.
    """

    def __init__(self, api_key: str, api_plan: str, chains: list[str], cfg: dict):
        self.api_key = api_key
        self.api_plan = api_plan
        self.chains = chains
        self.scorer = SignificanceScorer(cfg)
        self.poll_interval = cfg.get("poll_interval_seconds", 60)
        self.queue: asyncio.Queue[RawMarketEvent] = asyncio.Queue(maxsize=1000)
        self._rest = AveRestCollector(api_key, chains, self.scorer)
        self._wss = AveWssCollector(api_key, self.scorer) if api_plan == "pro" else None
        self._running = False

    def _enqueue(self, evt: RawMarketEvent):
        try:
            self.queue.put_nowait(evt)
            logger.debug(f"[COLLECTOR] Queued {evt.event_type} — {evt.token_symbol} ({evt.chain}) sig={evt.significance}")
        except asyncio.QueueFull:
            logger.warning("[COLLECTOR] Queue full — dropping event")

    async def run(self):
        self._running = True
        logger.info(f"[COLLECTOR] Starting — chains={self.chains} plan={self.api_plan}")
        while self._running:
            try:
                tasks = [self._rest_loop()]
                if self._wss:
                    tasks.append(self._wss.stream(self._enqueue))
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.error(f"[COLLECTOR] Fatal error — restarting in 10s: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def _rest_loop(self):
        async with self._rest:
            while self._running:
                for chain in self.chains:
                    try:
                        await self._rest.poll_chain(chain, self._enqueue)
                    except Exception as e:
                        logger.error(f"[REST] Poll error on {chain}: {e}", exc_info=True)
                        await asyncio.sleep(2)  # brief pause before next chain
                logger.info(f"[COLLECTOR] REST cycle complete. Sleeping {self.poll_interval}s...")
                await asyncio.sleep(self.poll_interval)

    async def stop(self):
        self._running = False

    async def poll_once(self) -> int:
        """Run one REST poll cycle across all chains. Returns number of events collected."""
        count = 0
        def counting_enqueue(evt):
            nonlocal count
            self._enqueue(evt)
            count += 1
        async with self._rest:
            for chain in self.chains:
                try:
                    await self._rest.poll_chain(chain, counting_enqueue)
                except Exception as e:
                    logger.error(f"[COLLECTOR] Manual poll error on {chain}: {e}")
        return count

    async def events(self) -> AsyncIterator[RawMarketEvent]:
        while True:
            evt = await self.queue.get()
            yield evt

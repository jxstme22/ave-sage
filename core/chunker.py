"""
AVE SAGE — Chunker
Converts RawMarketEvents into structured MemoryChunks ready for embedding.
Each chunk has a human-readable rag_text field that gets embedded into the vector store.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from core.collector import RawMarketEvent


# ─── Memory Chunk Model ───────────────────────────────────────────────────────

@dataclass
class MemoryChunk:
    id: str                           # deterministic hash-based ID
    chunk_type: str                   # market_event | trade_event | pattern_event | outcome_event
    chain: str
    token: str
    token_symbol: str
    timestamp: int
    rag_text: str                     # human-readable text for embedding
    metadata: dict = field(default_factory=dict)
    linked_trade_id: Optional[str] = None
    linked_outcome_id: Optional[str] = None

    def to_chroma_doc(self) -> dict:
        """Returns (id, document, metadata) tuple for ChromaDB upsert."""
        meta = {
            **self.metadata,
            "chunk_type": self.chunk_type,
            "chain": self.chain,
            "token": self.token,
            "token_symbol": self.token_symbol,
            "timestamp": self.timestamp,
        }
        if self.linked_trade_id:
            meta["linked_trade_id"] = self.linked_trade_id
        if self.linked_outcome_id:
            meta["linked_outcome_id"] = self.linked_outcome_id
        return {
            "id": self.id,
            "document": self.rag_text,
            "metadata": meta,
        }


# ─── ID Generation ────────────────────────────────────────────────────────────

def make_chunk_id(chain: str, token: str, event_type: str, timestamp: int) -> str:
    raw = f"{chain}:{token}:{event_type}:{timestamp}"
    return "chunk_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Text Templates ──────────────────────────────────────────────────────────

def _fmt_usd(val: float) -> str:
    if val >= 1_000_000:
        return f"${val/1_000_000:.2f}M"
    if val >= 1_000:
        return f"${val/1_000:.1f}K"
    return f"${val:.2f}"

def _fmt_pct(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val*100:.2f}%"

def _chain_label(chain: str) -> str:
    return {"solana": "Solana", "bsc": "BSC", "eth": "Ethereum", "base": "Base"}.get(chain.lower(), chain.upper())

def _risk_label(score: float) -> str:
    if score < 0.3:
        return "low"
    if score < 0.6:
        return "medium"
    return "HIGH"


# ─── Chunk Builders ──────────────────────────────────────────────────────────

def _build_price_chunk(evt: RawMarketEvent) -> MemoryChunk:
    d = evt.data
    chain_label = _chain_label(evt.chain)
    risk = d.get("risk_score", 0.0)
    risk_label = _risk_label(risk)

    text = (
        f"{evt.token_symbol} on {chain_label}: price {_fmt_usd(d.get('price_usd', 0))} "
        f"({_fmt_pct(d.get('price_change_1h', 0))} 1h, {_fmt_pct(d.get('price_change_24h', 0))} 24h). "
        f"Volume 24h: {_fmt_usd(d.get('volume_24h', 0))}. "
        f"Liquidity: {_fmt_usd(d.get('liquidity_usd', 0))}. "
        f"Holders: {d.get('holder_count', 0):,}. "
        f"Risk score: {risk:.2f} ({risk_label}). "
        f"Significance: {evt.significance:.2f}."
    )
    return MemoryChunk(
        id=make_chunk_id(evt.chain, evt.token, "price", evt.timestamp),
        chunk_type="market_event",
        chain=evt.chain,
        token=evt.token,
        token_symbol=evt.token_symbol,
        timestamp=evt.timestamp,
        rag_text=text,
        metadata={
            "event_subtype": "price_update",
            "price_usd": d.get("price_usd", 0),
            "price_change_1h": d.get("price_change_1h", 0),
            "price_change_24h": d.get("price_change_24h", 0),
            "volume_24h": d.get("volume_24h", 0),
            "risk_score": risk,
            "significance": evt.significance,
            "source": evt.source,
        },
    )


def _build_swap_chunk(evt: RawMarketEvent) -> MemoryChunk:
    d = evt.data
    swap_type = d.get("swap_type", "unknown").upper()
    chain_label = _chain_label(evt.chain)

    text = (
        f"Large {swap_type} detected for {evt.token_symbol} on {chain_label}: "
        f"{_fmt_usd(d.get('amount_usd', 0))} ({d.get('amount_token', 0):,.2f} tokens). "
        f"Price impact: {d.get('price_impact', 0)*100:.2f}%. "
        f"Wallet: {d.get('wallet', 'unknown')[:8]}... "
        f"Tx: {d.get('tx_hash', 'unknown')[:12]}..."
    )
    return MemoryChunk(
        id=make_chunk_id(evt.chain, evt.token, f"swap_{d.get('tx_hash','')[:8]}", evt.timestamp),
        chunk_type="trade_event",
        chain=evt.chain,
        token=evt.token,
        token_symbol=evt.token_symbol,
        timestamp=evt.timestamp,
        rag_text=text,
        metadata={
            "event_subtype": "large_swap",
            "swap_type": d.get("swap_type", "unknown"),
            "amount_usd": d.get("amount_usd", 0),
            "price_impact": d.get("price_impact", 0),
            "tx_hash": d.get("tx_hash", ""),
            "wallet": d.get("wallet", ""),
            "significance": evt.significance,
            "source": evt.source,
        },
    )


def _build_kline_chunk(evt: RawMarketEvent) -> MemoryChunk:
    d = evt.data
    chain_label = _chain_label(evt.chain)
    vol_mult = d.get("volume_multiplier", 1.0)
    candle_pct = d.get("candle_body_pct", 0)
    direction = "bullish" if d.get("close", 0) >= d.get("open", 0) else "bearish"

    # Classify signal type
    if vol_mult >= 3.0 and direction == "bullish":
        signal = "volume_breakout_bullish"
    elif vol_mult >= 3.0 and direction == "bearish":
        signal = "volume_breakout_bearish"
    elif candle_pct >= 0.05:
        signal = f"strong_{direction}_candle"
    else:
        signal = f"{direction}_candle"

    text = (
        f"{evt.token_symbol} {d.get('interval','?')} candle on {chain_label}: "
        f"{direction.upper()} close at {_fmt_usd(d.get('close', 0))} "
        f"(open {_fmt_usd(d.get('open', 0))}, body {candle_pct*100:.1f}%). "
        f"Volume {_fmt_usd(d.get('volume', 0))} — {vol_mult:.1f}x the 48-candle average. "
        f"Signal classification: {signal}."
    )
    return MemoryChunk(
        id=make_chunk_id(evt.chain, evt.token, f"kline_{d.get('interval','')}", evt.timestamp),
        chunk_type="pattern_event",
        chain=evt.chain,
        token=evt.token,
        token_symbol=evt.token_symbol,
        timestamp=evt.timestamp,
        rag_text=text,
        metadata={
            "event_subtype": "kline",
            "interval": d.get("interval", ""),
            "direction": direction,
            "signal_type": signal,
            "volume_multiplier": vol_mult,
            "candle_body_pct": candle_pct,
            "close": d.get("close", 0),
            "significance": evt.significance,
        },
    )


def _build_trending_chunk(evt: RawMarketEvent) -> MemoryChunk:
    d = evt.data
    chain_label = _chain_label(evt.chain)
    rank = d.get("trending_rank", 0)

    text = (
        f"{evt.token_symbol} is trending #{rank} on {chain_label}. "
        f"Current price: {_fmt_usd(d.get('price_usd', 0))} "
        f"({_fmt_pct(d.get('price_change_1h', 0))} 1h). "
        f"Market cap: {_fmt_usd(d.get('market_cap', 0))}. "
        f"Volume 24h: {_fmt_usd(d.get('volume_24h', 0))}."
    )
    return MemoryChunk(
        id=make_chunk_id(evt.chain, evt.token, f"trending_{rank}", evt.timestamp),
        chunk_type="market_event",
        chain=evt.chain,
        token=evt.token,
        token_symbol=evt.token_symbol,
        timestamp=evt.timestamp,
        rag_text=text,
        metadata={
            "event_subtype": "trending",
            "trending_rank": rank,
            "price_usd": d.get("price_usd", 0),
            "price_change_1h": d.get("price_change_1h", 0),
            "market_cap": d.get("market_cap", 0),
            "significance": evt.significance,
        },
    )


def _build_holder_chunk(evt: RawMarketEvent) -> MemoryChunk:
    d = evt.data
    chain_label = _chain_label(evt.chain)
    delta = d.get("holder_delta", 0)
    direction = "gained" if delta > 0 else "lost"

    text = (
        f"{evt.token_symbol} on {chain_label} {direction} {abs(delta):,} holders. "
        f"Total holders: {d.get('holder_count', 0):,}. "
        f"Holder change indicates {'accumulation' if delta > 0 else 'distribution'} pressure."
    )
    return MemoryChunk(
        id=make_chunk_id(evt.chain, evt.token, "holder", evt.timestamp),
        chunk_type="market_event",
        chain=evt.chain,
        token=evt.token,
        token_symbol=evt.token_symbol,
        timestamp=evt.timestamp,
        rag_text=text,
        metadata={
            "event_subtype": "holder_change",
            "holder_delta": delta,
            "significance": evt.significance,
        },
    )


# ─── Main Chunker ─────────────────────────────────────────────────────────────

class Chunker:
    """
    Converts RawMarketEvent → MemoryChunk.
    Each event type has its own template producing rich, queryable rag_text.
    """

    BUILDERS = {
        "price": _build_price_chunk,
        "swap": _build_swap_chunk,
        "kline": _build_kline_chunk,
        "trending": _build_trending_chunk,
        "holder": _build_holder_chunk,
    }

    def process(self, evt: RawMarketEvent) -> Optional[MemoryChunk]:
        builder = self.BUILDERS.get(evt.event_type)
        if not builder:
            return None
        try:
            chunk = builder(evt)
            return chunk
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[CHUNKER] Failed to chunk {evt.event_type}: {e}")
            return None

    def process_batch(self, events: list[RawMarketEvent]) -> list[MemoryChunk]:
        results = []
        for evt in events:
            chunk = self.process(evt)
            if chunk:
                results.append(chunk)
        return results


# ─── Outcome Chunk Builder (called by feedback.py) ───────────────────────────

def build_outcome_chunk(
    chain: str,
    token: str,
    token_symbol: str,
    trade_id: str,
    signal_type: str,
    action: str,
    entry_price: float,
    exit_price: float,
    pnl_pct: float,
    outcome: str,  # "win" | "loss" | "breakeven"
    rag_context_summary: str,
    timestamp: int,
) -> MemoryChunk:
    """
    Builds an outcome chunk after a trade closes.
    This is the most valuable chunk type — it closes the learning loop.
    """
    chain_label = _chain_label(chain)
    pnl_str = _fmt_pct(pnl_pct)

    text = (
        f"TRADE OUTCOME [{outcome.upper()}]: {token_symbol} on {chain_label}. "
        f"Signal: {signal_type}. Action: {action.upper()}. "
        f"Entry: {_fmt_usd(entry_price)} → Exit: {_fmt_usd(exit_price)}. "
        f"PnL: {pnl_str}. "
        f"RAG context used: {rag_context_summary}"
    )

    return MemoryChunk(
        id=make_chunk_id(chain, token, f"outcome_{trade_id}", timestamp),
        chunk_type="outcome_event",
        chain=chain,
        token=token,
        token_symbol=token_symbol,
        timestamp=timestamp,
        rag_text=text,
        linked_trade_id=trade_id,
        metadata={
            "event_subtype": "trade_outcome",
            "signal_type": signal_type,
            "action": action,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "outcome": outcome,
        },
    )

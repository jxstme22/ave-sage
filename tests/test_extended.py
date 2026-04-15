"""
AVE SAGE — Extended Tests
Tests for: VectorStore (embedder), RAG engine, FeedbackWriter, MemoryAgent,
TradeAgent dry-run, and full pipeline integration.
"""

import os
import shutil
import tempfile
import time
import pytest
from core.collector import RawMarketEvent, SignificanceScorer
from core.chunker import Chunker, MemoryChunk, build_outcome_chunk
from core.embedder import VectorStore
from core.rag_engine import RAGEngine, RAGContext
from core.signal_detector import SignalDetector, SignalPacket
from core.feedback import FeedbackWriter
from agents.memory_agent import MemoryAgent


# ─── Shared Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def vector_store():
    """Fresh ChromaDB store in a unique temp directory per test."""
    tmpdir = tempfile.mkdtemp(prefix="sage_test_")
    store = VectorStore(
        persist_dir=tmpdir,
        collection_name="test_sage",
        embedding_provider="sentence_transformer",
        embedding_model="all-MiniLM-L6-v2",
    )
    yield store
    shutil.rmtree(tmpdir, ignore_errors=True)


def _make_chunk(symbol="SOL", chain="solana", chunk_type="market_event", text=None, ts=None) -> MemoryChunk:
    ts = ts or int(time.time())
    text = text or f"{symbol} on {chain} showing a 5% price increase with 3x volume spike."
    return MemoryChunk(
        id=f"test_{symbol}_{ts}",
        chunk_type=chunk_type,
        chain=chain,
        token="So111111",
        token_symbol=symbol,
        timestamp=ts,
        rag_text=text,
        metadata={"event_subtype": "test", "significance": 0.8},
    )


# ─── VectorStore (Embedder) Tests ────────────────────────────────────────────

class TestVectorStore:
    def test_upsert_and_count(self, vector_store):
        chunk = _make_chunk()
        assert vector_store.upsert(chunk)
        assert vector_store.count() == 1

    def test_upsert_is_idempotent(self, vector_store):
        chunk = _make_chunk()
        vector_store.upsert(chunk)
        vector_store.upsert(chunk)
        assert vector_store.count() == 1

    def test_batch_upsert(self, vector_store):
        chunks = [
            _make_chunk(symbol="SOL", ts=int(time.time()) - 100),
            _make_chunk(symbol="BNB", chain="bsc", ts=int(time.time()) - 50),
            _make_chunk(symbol="ETH", chain="eth", ts=int(time.time())),
        ]
        count = vector_store.upsert_batch(chunks)
        assert count == 3
        assert vector_store.count() == 3

    def test_semantic_query(self, vector_store):
        chunks = [
            _make_chunk(symbol="SOL", text="SOL price surged 10% in 1 hour with massive volume spike"),
            _make_chunk(symbol="BNB", chain="bsc", text="BNB trading flat with no volume activity"),
        ]
        vector_store.upsert_batch(chunks)

        results = vector_store.query("volume spike price increase", n_results=2)
        assert len(results) > 0
        # SOL chunk should be more relevant
        assert results[0]["metadata"]["token_symbol"] == "SOL"

    def test_query_with_chain_filter(self, vector_store):
        chunks = [
            _make_chunk(symbol="SOL", chain="solana", text="SOL big move on Solana"),
            _make_chunk(symbol="BNB", chain="bsc", text="BNB big move on BSC"),
        ]
        vector_store.upsert_batch(chunks)

        results = vector_store.query("big move", n_results=5, chain_filter="bsc")
        assert all(r["metadata"]["chain"] == "bsc" for r in results)

    def test_query_with_chunk_type_filter(self, vector_store):
        c1 = _make_chunk(symbol="SOL", chunk_type="market_event", text="SOL market activity")
        c2 = _make_chunk(symbol="SOL", chunk_type="outcome_event", text="SOL trade outcome win",
                         ts=int(time.time()) + 1)
        vector_store.upsert_batch([c1, c2])

        results = vector_store.query("SOL activity", chunk_type_filter="outcome_event")
        assert all(r["metadata"]["chunk_type"] == "outcome_event" for r in results)

    def test_stats(self, vector_store):
        vector_store.upsert(_make_chunk())
        stats = vector_store.stats()
        assert stats["total_chunks"] == 1

    def test_get_recent(self, vector_store):
        vector_store.upsert(_make_chunk())
        recent = vector_store.get_recent("solana", lookback_hours=1)
        assert len(recent) >= 1


# ─── RAG Engine Tests ────────────────────────────────────────────────────────

class TestRAGEngine:
    def test_retrieve_builds_context(self, vector_store):
        # Seed some market events
        chunks = [
            _make_chunk(text="SOL had a volume breakout at $140, price went up 8% after", ts=int(time.time()) - 3600),
            _make_chunk(text="SOL volume spike at $135, followed by 5% increase", ts=int(time.time()) - 7200),
        ]
        vector_store.upsert_batch(chunks)

        rag = RAGEngine(vector_store, {"max_context_chunks": 5, "similarity_threshold": 0.0, "lookback_hours": 168})
        ctx = rag.retrieve(
            signal_type="volume_breakout_bullish",
            token_symbol="SOL",
            chain="solana",
            current_conditions={"price_change_1h": 0.05, "volume_multiplier": 3.5, "risk_score": 0.1},
        )

        assert isinstance(ctx, RAGContext)
        assert len(ctx.chunks) > 0
        assert "CURRENT MARKET CONDITIONS" in ctx.context_text

    def test_empty_store_returns_no_history_message(self, vector_store):
        rag = RAGEngine(vector_store, {"max_context_chunks": 5, "similarity_threshold": 0.0, "lookback_hours": 168})
        ctx = rag.retrieve(
            signal_type="trending_entry",
            token_symbol="UNKNOWN",
            chain="solana",
            current_conditions={"price_change_1h": 0.02, "volume_multiplier": 1.0, "risk_score": 0.5},
        )
        assert "No prior outcomes" in ctx.context_text

    def test_confidence_boost_neutral_on_no_history(self, vector_store):
        rag = RAGEngine(vector_store, {"max_context_chunks": 5, "similarity_threshold": 0.0, "lookback_hours": 168})
        ctx = rag.retrieve(
            signal_type="volume_breakout_bullish",
            token_symbol="SOL",
            chain="solana",
            current_conditions={"price_change_1h": 0.05, "volume_multiplier": 3.0, "risk_score": 0.1},
        )
        assert ctx.confidence_boost == 0.05  # slight positive boost for fresh opportunity

    def test_confidence_boost_positive_on_wins(self, vector_store):
        # Seed winning outcome events
        for i in range(5):
            chunk = build_outcome_chunk(
                chain="solana", token="So111111", token_symbol="SOL",
                trade_id=f"t{i}", signal_type="volume_breakout_bullish",
                action="buy", entry_price=140.0, exit_price=155.0,
                pnl_pct=0.107, outcome="win",
                rag_context_summary="strong signal",
                timestamp=int(time.time()) - i * 3600,
            )
            vector_store.upsert(chunk)

        rag = RAGEngine(vector_store, {"max_context_chunks": 8, "similarity_threshold": 0.0, "lookback_hours": 168})
        ctx = rag.retrieve(
            signal_type="volume_breakout_bullish",
            token_symbol="SOL",
            chain="solana",
            current_conditions={"price_change_1h": 0.06, "volume_multiplier": 4.0, "risk_score": 0.1},
        )
        assert ctx.confidence_boost > 0


# ─── FeedbackWriter Tests ────────────────────────────────────────────────────

class TestFeedbackWriter:
    def test_record_win(self, vector_store):
        fw = FeedbackWriter(vector_store)
        chunk = fw.record(
            chain="solana", token="So111111", token_symbol="SOL",
            trade_id="t1", signal_type="volume_breakout_bullish",
            action="buy", entry_price=140.0, exit_price=155.0,
        )
        assert chunk.chunk_type == "outcome_event"
        assert "WIN" in chunk.rag_text
        assert vector_store.count() == 1

    def test_record_loss(self, vector_store):
        fw = FeedbackWriter(vector_store)
        chunk = fw.record(
            chain="solana", token="So111111", token_symbol="SOL",
            trade_id="t2", signal_type="trending_entry",
            action="buy", entry_price=140.0, exit_price=130.0,
        )
        assert "LOSS" in chunk.rag_text

    def test_stats_tracking(self, vector_store):
        fw = FeedbackWriter(vector_store)
        fw.record(chain="solana", token="So111111", token_symbol="SOL",
                  trade_id="t1", signal_type="x", action="buy",
                  entry_price=100.0, exit_price=110.0)
        fw.record(chain="solana", token="So111111", token_symbol="SOL",
                  trade_id="t2", signal_type="x", action="buy",
                  entry_price=100.0, exit_price=90.0)
        fw.record(chain="solana", token="So111111", token_symbol="SOL",
                  trade_id="t3", signal_type="x", action="buy",
                  entry_price=100.0, exit_price=115.0)

        stats = fw.stats()
        assert stats["total_outcomes"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["win_rate"] == pytest.approx(0.667, abs=0.01)


# ─── MemoryAgent Tests ───────────────────────────────────────────────────────

class TestMemoryAgent:
    def test_query_returns_context(self, vector_store):
        vector_store.upsert(_make_chunk(text="SOL volume breakout at $140 with 4x spike"))
        fw = FeedbackWriter(vector_store)
        ma = MemoryAgent(vector_store, fw, {"lookback_hours": 168, "max_context_chunks": 8, "similarity_threshold": 0.0})
        result = ma.query("SOL volume breakout")
        assert result["chunks_used"] > 0
        assert "sol" in result["context"].lower()

    def test_query_empty_store(self, vector_store):
        fw = FeedbackWriter(vector_store)
        ma = MemoryAgent(vector_store, fw, {"lookback_hours": 168, "max_context_chunks": 8, "similarity_threshold": 0.0})
        result = ma.query("nonexistent token XYZ")
        assert result["chunks_used"] == 0
        assert "No relevant memories" in result["context"]

    def test_health_report(self, vector_store):
        fw = FeedbackWriter(vector_store)
        ma = MemoryAgent(vector_store, fw, {"lookback_hours": 168, "max_context_chunks": 8, "similarity_threshold": 0.0})
        health = ma.health()
        assert "memory" in health
        assert "outcomes" in health


# ─── Integration: Full Pipeline Test ─────────────────────────────────────────

class TestPipelineIntegration:
    """End-to-end: event → chunk → embed → detect → RAG retrieve"""

    def test_event_to_rag_retrieval(self, vector_store):
        """Complete pipeline: market event → stored in vector DB → queryable via RAG."""
        chunker = Chunker()
        scorer = SignificanceScorer({"price_change_min": 0.03, "volume_spike_multiplier": 2.5, "significance_threshold": 0.3})

        # 1. Create market event
        evt = RawMarketEvent(
            source="rest", event_type="price",
            chain="solana", token="So111111", token_symbol="SOL",
            timestamp=int(time.time()),
            data={"price_usd": 145.0, "price_change_1h": 0.08,
                  "price_change_24h": 0.15, "volume_24h": 1_200_000,
                  "liquidity_usd": 8_000_000, "holder_count": 15000, "risk_score": 0.1},
        )
        scorer.is_significant(evt)

        # 2. Chunk it
        chunk = chunker.process(evt)
        assert chunk is not None

        # 3. Store in vector DB
        assert vector_store.upsert(chunk)
        assert vector_store.count() == 1

        # 4. Query it back via RAG
        rag = RAGEngine(vector_store, {"max_context_chunks": 5, "similarity_threshold": 0.0, "lookback_hours": 168})
        ctx = rag.retrieve(
            signal_type="trend_acceleration",
            token_symbol="SOL",
            chain="solana",
            current_conditions={"price_change_1h": 0.08, "volume_multiplier": 2.0, "risk_score": 0.1},
        )
        assert len(ctx.chunks) > 0
        assert "SOL" in ctx.context_text

    def test_signal_detect_to_outcome_loop(self, vector_store):
        """Signal detection → outcome recording → outcome queryable."""
        chunker = Chunker()
        detector = SignalDetector({
            "trade_confidence_min": 0.60,
            "volume_spike_multiplier": 2.5,
            "signal_window_seconds": 900,
            "risk_warn_threshold": 0.65,
        })

        # 1. Kline event triggers signal
        evt = RawMarketEvent(
            source="rest", event_type="kline",
            chain="solana", token="So111111", token_symbol="SOL",
            timestamp=int(time.time()),
            data={"interval": "15m", "open": 140.0, "high": 152.0,
                  "low": 139.0, "close": 151.0, "volume": 500_000,
                  "volume_multiplier": 4.5, "avg_volume_48": 111_000,
                  "candle_body_pct": 0.078, "direction": "bullish"},
            significance=0.85,
        )

        # 2. Detect signal
        signals = detector.ingest(evt)
        assert len(signals) > 0
        signal = signals[0]
        assert signal.signal_type == "volume_breakout_bullish"

        # 3. Store the event chunk
        chunk = chunker.process(evt)
        vector_store.upsert(chunk)

        # 4. Record outcome (simulated trade)
        fw = FeedbackWriter(vector_store)
        outcome = fw.record(
            chain="solana", token="So111111", token_symbol="SOL",
            trade_id="int_test_001", signal_type=signal.signal_type,
            action="buy", entry_price=151.0, exit_price=163.0,
        )
        assert outcome.chunk_type == "outcome_event"
        assert vector_store.count() == 2  # event + outcome

        # 5. Outcome should be queryable
        results = vector_store.query(
            "volume breakout trade outcome",
            chunk_type_filter="outcome_event",
        )
        assert len(results) > 0
        assert "WIN" in results[0]["document"]

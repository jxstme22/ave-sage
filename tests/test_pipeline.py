"""
AVE SAGE — Tests
Core pipeline validation: chunker, scorer, signal detector, RAG context building.
"""

import time
import pytest
from core.collector import RawMarketEvent, SignificanceScorer
from core.chunker import Chunker, build_outcome_chunk
from core.signal_detector import SignalDetector


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_price_event(chain="solana", symbol="SOL", change_1h=0.05, risk=0.1) -> RawMarketEvent:
    return RawMarketEvent(
        source="rest", event_type="price",
        chain=chain, token="So111111", token_symbol=symbol,
        timestamp=int(time.time()),
        data={"price_usd": 145.0, "price_change_1h": change_1h,
              "price_change_24h": 0.12, "volume_24h": 800_000,
              "liquidity_usd": 5_000_000, "holder_count": 12000, "risk_score": risk},
    )

def make_kline_event(vol_mult=3.5, direction="bullish") -> RawMarketEvent:
    open_p, close_p = (100.0, 107.0) if direction == "bullish" else (100.0, 93.0)
    return RawMarketEvent(
        source="rest", event_type="kline",
        chain="solana", token="So111111", token_symbol="SOL",
        timestamp=int(time.time()),
        data={"interval": "15m", "open": open_p, "high": close_p + 1,
              "low": open_p - 1, "close": close_p, "volume": 500_000,
              "volume_multiplier": vol_mult, "avg_volume_48": 143_000,
              "candle_body_pct": abs(close_p - open_p) / open_p,
              "direction": direction},
        significance=0.8,
    )

def make_swap_event(swap_type="buy", amount_usd=25_000) -> RawMarketEvent:
    return RawMarketEvent(
        source="wss", event_type="swap",
        chain="solana", token="So111111", token_symbol="SOL",
        timestamp=int(time.time()),
        data={"tx_hash": "abc123def456", "swap_type": swap_type,
              "amount_usd": amount_usd, "amount_token": 172.4,
              "price_impact": 0.003, "wallet": "Wallet123abc"},
    )

def make_trending_event(rank=2, risk=0, change_1h=5.0) -> RawMarketEvent:
    return RawMarketEvent(
        source="rest", event_type="trending",
        chain="bsc", token="0xTokenBSC", token_symbol="TOKEN",
        timestamp=int(time.time()),
        data={"trending_rank": rank, "price_usd": 0.42,
              "price_change_1h": change_1h, "volume_24h": 2_000_000,
              "market_cap": 10_000_000, "ave_risk_level": risk},
    )


# ─── Scorer Tests ────────────────────────────────────────────────────────────

class TestSignificanceScorer:
    cfg = {"price_change_min": 0.03, "volume_spike_multiplier": 2.5, "significance_threshold": 0.6}

    def test_strong_price_move_is_significant(self):
        scorer = SignificanceScorer(self.cfg)
        evt = make_price_event(change_1h=0.10)
        evt.significance = scorer.score(evt)
        assert scorer.is_significant(evt)

    def test_small_price_move_not_significant(self):
        scorer = SignificanceScorer(self.cfg)
        evt = make_price_event(change_1h=0.005)
        assert not scorer.is_significant(evt)

    def test_high_risk_always_significant(self):
        scorer = SignificanceScorer(self.cfg)
        evt = make_price_event(risk=0.92)
        evt.event_type = "risk"
        evt.data["risk_score"] = 0.92
        assert scorer.score(evt) > 0.7

    def test_large_swap_significant(self):
        scorer = SignificanceScorer(self.cfg)
        evt = make_swap_event(amount_usd=35_000)
        evt.significance = scorer.score(evt)
        assert evt.significance > 0.6


# ─── Chunker Tests ───────────────────────────────────────────────────────────

class TestChunker:
    def setup_method(self):
        self.chunker = Chunker()

    def test_price_chunk_contains_key_fields(self):
        evt = make_price_event()
        evt.significance = 0.75
        chunk = self.chunker.process(evt)
        assert chunk is not None
        assert "SOL" in chunk.rag_text
        assert "Solana" in chunk.rag_text
        assert chunk.chunk_type == "market_event"

    def test_kline_chunk_classifies_signal(self):
        evt = make_kline_event(vol_mult=4.0, direction="bullish")
        chunk = self.chunker.process(evt)
        assert chunk is not None
        assert "volume_breakout_bullish" in chunk.rag_text
        assert chunk.chunk_type == "pattern_event"

    def test_swap_chunk_includes_usd_value(self):
        evt = make_swap_event(amount_usd=30_000)
        evt.significance = 0.65
        chunk = self.chunker.process(evt)
        assert chunk is not None
        assert "30" in chunk.rag_text  # $30K
        assert chunk.chunk_type == "trade_event"

    def test_chunk_id_is_deterministic(self):
        evt = make_price_event()
        evt.significance = 0.7
        c1 = self.chunker.process(evt)
        c2 = self.chunker.process(evt)
        assert c1.id == c2.id

    def test_outcome_chunk_closes_loop(self):
        chunk = build_outcome_chunk(
            chain="solana", token="So111111", token_symbol="SOL",
            trade_id="test_001", signal_type="volume_breakout_bullish",
            action="buy", entry_price=140.0, exit_price=152.0,
            pnl_pct=0.0857, outcome="win",
            rag_context_summary="3 previous wins on similar signal",
            timestamp=int(time.time()),
        )
        assert chunk.chunk_type == "outcome_event"
        assert "WIN" in chunk.rag_text
        assert chunk.linked_trade_id == "test_001"

    def test_batch_process(self):
        events = [make_price_event(), make_kline_event(), make_swap_event()]
        for e in events:
            e.significance = 0.75
        chunks = self.chunker.process_batch(events)
        assert len(chunks) == 3


# ─── Signal Detector Tests ───────────────────────────────────────────────────

class TestSignalDetector:
    cfg = {
        "trade_confidence_min": 0.60,
        "volume_spike_multiplier": 2.5,
        "signal_window_seconds": 900,
        "risk_warn_threshold": 0.65,
    }

    def setup_method(self):
        self.detector = SignalDetector(self.cfg)

    def test_volume_breakout_triggers_signal(self):
        evt = make_kline_event(vol_mult=4.0, direction="bullish")
        signals = self.detector.ingest(evt)
        assert any(s.signal_type == "volume_breakout_bullish" for s in signals)

    def test_low_volume_no_signal(self):
        evt = make_kline_event(vol_mult=1.2, direction="bullish")
        signals = self.detector.ingest(evt)
        assert not any(s.signal_type.startswith("volume_breakout") for s in signals)

    def test_risk_flag_triggers_exit_signal(self):
        evt = make_price_event(risk=0.85)
        signals = self.detector.ingest(evt)
        assert any(s.signal_type == "risk_flag_raised" for s in signals)

    def test_trending_entry_triggers_on_top5_low_risk(self):
        evt = make_trending_event(rank=3, risk=0, change_1h=5.0)
        evt.significance = 0.7
        signals = self.detector.ingest(evt)
        assert any(s.signal_type == "trending_entry" for s in signals)

    def test_trending_no_signal_if_high_risk(self):
        evt = make_trending_event(rank=2, risk=5, change_1h=5.0)
        evt.significance = 0.7
        signals = self.detector.ingest(evt)
        assert not any(s.signal_type == "trending_entry" for s in signals)

    def test_whale_accumulation_needs_multiple_swaps(self):
        # Single swap — no signal
        evt1 = make_swap_event("buy", 30_000)
        evt1.significance = 0.7
        signals = self.detector.ingest(evt1)
        assert not any(s.signal_type == "whale_accumulation" for s in signals)

        # Second swap — should trigger
        evt2 = make_swap_event("buy", 25_000)
        evt2.significance = 0.7
        signals2 = self.detector.ingest(evt2)
        assert any(s.signal_type == "whale_accumulation" for s in signals2)

    def test_trend_acceleration_detected(self):
        evt = make_price_event(change_1h=6.0)
        evt.data["price_change_24h"] = 10.0  # 1h is 60% of 24h = acceleration
        evt.significance = 0.7
        signals = self.detector.ingest(evt)
        assert any(s.signal_type == "trend_acceleration" for s in signals)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

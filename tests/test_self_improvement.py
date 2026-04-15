"""
AVE SAGE — Tests for self-improvement modules
Tests: TradingRulesEngine, StrategyLedger, SelfTuner
"""

import json
import os
import time
import tempfile
from types import SimpleNamespace

import pytest

from core.rules_engine import TradingRulesEngine, RulesConfig, RuleVerdict
from core.strategy_ledger import StrategyLedger, SelfTuner


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_decision(chain="solana", token="ABC123", risk=0.1, liquidity=50_000,
                  amount_usd=10.0, action="buy"):
    """Minimal duck-typed decision object for rules engine."""
    return SimpleNamespace(
        action=action,
        amount_usd=amount_usd,
        signal=SimpleNamespace(
            chain=chain,
            token=token,
            token_symbol="TEST",
            signal_type="momentum_surge",
            conditions={"risk_score": risk, "liquidity_usd": liquidity},
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Trading Rules Engine
# ═══════════════════════════════════════════════════════════════════════════════


class TestRulesEngineBasics:

    def test_all_pass(self):
        engine = TradingRulesEngine()
        d = make_decision()
        v = engine.evaluate(d)
        assert v.allowed is True

    def test_chain_whitelist_block(self):
        engine = TradingRulesEngine()
        d = make_decision(chain="polygon")
        v = engine.evaluate(d)
        assert v.allowed is False
        assert v.rule_name == "chain_whitelist"

    def test_chain_whitelist_pass(self):
        for chain in ["solana", "bsc", "eth", "base"]:
            engine = TradingRulesEngine()
            v = engine.evaluate(make_decision(chain=chain))
            assert v.allowed is True

    def test_token_blacklist_block(self):
        engine = TradingRulesEngine({"token_blacklist": ["SCAM_TOKEN"]})
        d = make_decision(token="SCAM_TOKEN")
        v = engine.evaluate(d)
        assert v.allowed is False
        assert v.rule_name == "token_blacklist"

    def test_risk_score_block(self):
        engine = TradingRulesEngine()
        d = make_decision(risk=0.9)
        v = engine.evaluate(d)
        assert v.allowed is False
        assert v.rule_name == "max_risk_score"

    def test_low_liquidity_block(self):
        engine = TradingRulesEngine()
        d = make_decision(liquidity=5_000)
        v = engine.evaluate(d)
        assert v.allowed is False
        assert v.rule_name == "min_liquidity"


class TestRulesEngineStateful:

    def test_daily_loss_block(self):
        engine = TradingRulesEngine({"max_daily_loss_usd": 50.0})
        engine.record_trade_result(-60.0)  # exceeds limit
        v = engine.evaluate(make_decision())
        assert v.allowed is False
        assert v.rule_name == "max_daily_loss"

    def test_daily_loss_accumulates(self):
        engine = TradingRulesEngine({"max_daily_loss_usd": 50.0, "cooldown_after_loss_seconds": 0})
        engine.record_trade_result(-20.0)
        assert engine.evaluate(make_decision()).allowed is True
        engine.record_trade_result(-35.0)
        assert engine.evaluate(make_decision()).allowed is False

    def test_drawdown_block(self):
        engine = TradingRulesEngine({"max_drawdown_pct": 0.10})
        engine.set_capital(1000.0, 850.0)  # 15% drawdown
        v = engine.evaluate(make_decision())
        assert v.allowed is False
        assert v.rule_name == "max_drawdown"

    def test_drawdown_pass_no_capital(self):
        engine = TradingRulesEngine()
        # No capital set → drawdown check passes
        v = engine.evaluate(make_decision())
        assert v.allowed is True

    def test_concurrent_positions_block(self):
        engine = TradingRulesEngine({"max_concurrent_positions": 3})
        engine.set_open_position_count(3)
        v = engine.evaluate(make_decision())
        assert v.allowed is False
        assert v.rule_name == "max_concurrent_positions"

    def test_cooldown_block(self):
        engine = TradingRulesEngine({"cooldown_after_loss_seconds": 600})
        engine.record_trade_result(-10.0)  # triggers cooldown
        v = engine.evaluate(make_decision())
        assert v.allowed is False
        assert v.rule_name == "cooldown_after_loss"

    def test_cooldown_pass_after_win(self):
        engine = TradingRulesEngine({"cooldown_after_loss_seconds": 600})
        engine.record_trade_result(10.0)  # win, no cooldown
        v = engine.evaluate(make_decision())
        assert v.allowed is True

    def test_position_vs_liquidity_block(self):
        engine = TradingRulesEngine({"max_position_pct_of_liquidity": 0.01})
        # liquidity=50_000, 1% = 500, amount=600 → blocked
        d = make_decision(liquidity=50_000, amount_usd=600.0)
        v = engine.evaluate(d)
        assert v.allowed is False
        assert v.rule_name == "position_vs_liquidity"

    def test_position_vs_liquidity_pass(self):
        engine = TradingRulesEngine({"max_position_pct_of_liquidity": 0.01})
        d = make_decision(liquidity=50_000, amount_usd=400.0)
        v = engine.evaluate(d)
        assert v.allowed is True

    def test_status(self):
        engine = TradingRulesEngine()
        engine.record_trade_result(-25.0)
        engine.set_open_position_count(2)
        s = engine.status()
        assert s["daily_pnl_usd"] == -25.0
        assert s["open_positions"] == 2
        assert "halted" in s


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy Ledger
# ═══════════════════════════════════════════════════════════════════════════════


class TestStrategyLedger:

    def test_record_and_win_rate(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger = StrategyLedger(persist_path=path)
            ledger.record_outcome("momentum_surge", "solana", 0.05)  # win
            ledger.record_outcome("momentum_surge", "solana", -0.03) # loss
            ledger.record_outcome("momentum_surge", "solana", 0.02)  # win

            wr = ledger.win_rate("momentum_surge", "solana")
            assert abs(wr - 2/3) < 0.01
        finally:
            os.unlink(path)

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger1 = StrategyLedger(persist_path=path)
            ledger1.record_outcome("whale_move", "bsc", 0.10)
            ledger1.record_outcome("whale_move", "bsc", -0.02)

            # Re-load from disk
            ledger2 = StrategyLedger(persist_path=path)
            wr = ledger2.win_rate("whale_move", "bsc")
            assert abs(wr - 0.5) < 0.01
            records = ledger2.all_records()
            assert len(records) == 1
            assert records[0]["total_trades"] == 2
        finally:
            os.unlink(path)

    def test_missing_key_returns_none(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger = StrategyLedger(persist_path=path)
            assert ledger.win_rate("nonexistent", "eth") is None
        finally:
            os.unlink(path)

    def test_all_records_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger = StrategyLedger(persist_path=path)
            assert ledger.all_records() == []
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# Self-Tuner
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelfTuner:

    def _build_tuner(self, wins: int, losses: int, avg_win_pct=0.05, avg_loss_pct=-0.03):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        ledger = StrategyLedger(persist_path=path)
        for _ in range(wins):
            ledger.record_outcome("test_signal", "solana", avg_win_pct)
        for _ in range(losses):
            ledger.record_outcome("test_signal", "solana", avg_loss_pct)
        tuner = SelfTuner(ledger)
        return tuner, path

    def test_defaults_below_min_samples(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger = StrategyLedger(persist_path=path)
            ledger.record_outcome("foo", "solana", 0.05)
            tuner = SelfTuner(ledger)
            result = tuner.tune("foo", "solana")
            assert result["source"] == "default"
        finally:
            os.unlink(path)

    def test_high_win_rate_increases_size(self):
        # 8 wins, 2 losses → 80% win rate → size up
        tuner, path = self._build_tuner(8, 2)
        try:
            result = tuner.tune("test_signal", "solana")
            assert result["source"] == "tuned"
            assert result["size_multiplier"] > 1.0
        finally:
            os.unlink(path)

    def test_low_win_rate_decreases_size(self):
        # 2 wins, 8 losses → 20% win rate → size down
        tuner, path = self._build_tuner(2, 8)
        try:
            result = tuner.tune("test_signal", "solana")
            assert result["source"] == "tuned"
            assert result["size_multiplier"] < 1.0
        finally:
            os.unlink(path)

    def test_low_win_rate_tightens_confidence(self):
        tuner, path = self._build_tuner(2, 8)
        try:
            result = tuner.tune("test_signal", "solana")
            # Default confidence_min is typically 0.6; should increase
            assert result["confidence_min"] > 0.6
        finally:
            os.unlink(path)

    def test_tune_all(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ledger = StrategyLedger(persist_path=path)
            for _ in range(6):
                ledger.record_outcome("sig_a", "solana", 0.05)
            for _ in range(6):
                ledger.record_outcome("sig_b", "bsc", -0.02)
            tuner = SelfTuner(ledger)
            results = tuner.tune_all()
            assert len(results) == 2
            types = {r["signal_type"] for r in results}
            assert "sig_a" in types
            assert "sig_b" in types
        finally:
            os.unlink(path)

    def test_size_multiplier_capped(self):
        # Very high win rate
        tuner, path = self._build_tuner(20, 0)
        try:
            result = tuner.tune("test_signal", "solana")
            assert result["size_multiplier"] <= 1.5
        finally:
            os.unlink(path)

    def test_size_multiplier_floored(self):
        # Very low win rate
        tuner, path = self._build_tuner(0, 20)
        try:
            result = tuner.tune("test_signal", "solana")
            assert result["size_multiplier"] >= 0.3
        finally:
            os.unlink(path)

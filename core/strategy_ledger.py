"""
AVE SAGE — Strategy Ledger & Self-Tuner
Tracks per-signal-type performance and adapts trading parameters.
This is the core self-improvement mechanism:
  1. Ledger records every trade outcome by signal type + chain
  2. Self-tuner adjusts TP/SL, confidence thresholds, and sizing
  3. Agent reads tuned params before each decision
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StrategyRecord:
    """One entry per signal_type × chain combination."""
    signal_type: str
    chain: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    total_pnl_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    best_pnl_pct: float = 0.0
    worst_pnl_pct: float = 0.0
    # Tuned parameters (self-improvement outputs)
    tuned_tp_pct: float = 0.08
    tuned_sl_pct: float = 0.04
    tuned_confidence_min: float = 0.70
    tuned_size_multiplier: float = 1.0
    last_updated: int = 0


class StrategyLedger:
    """
    Persistent ledger of strategy performance by signal type and chain.
    Loaded from / saved to a JSON file.
    """

    def __init__(self, persist_path: str = "./data/strategy_ledger.json"):
        self._path = persist_path
        self._records: dict[str, StrategyRecord] = {}
        self._load()

    @staticmethod
    def _key(signal_type: str, chain: str) -> str:
        return f"{signal_type}:{chain}"

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                raw = json.load(f)
            for key, val in raw.items():
                self._records[key] = StrategyRecord(**val)
            logger.info(f"[LEDGER] Loaded {len(self._records)} strategy records")
        except Exception as e:
            logger.warning(f"[LEDGER] Failed to load: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        data = {}
        for key, rec in self._records.items():
            data[key] = {
                "signal_type": rec.signal_type,
                "chain": rec.chain,
                "total_trades": rec.total_trades,
                "wins": rec.wins,
                "losses": rec.losses,
                "breakeven": rec.breakeven,
                "total_pnl_pct": round(rec.total_pnl_pct, 6),
                "avg_win_pct": round(rec.avg_win_pct, 6),
                "avg_loss_pct": round(rec.avg_loss_pct, 6),
                "best_pnl_pct": round(rec.best_pnl_pct, 6),
                "worst_pnl_pct": round(rec.worst_pnl_pct, 6),
                "tuned_tp_pct": round(rec.tuned_tp_pct, 4),
                "tuned_sl_pct": round(rec.tuned_sl_pct, 4),
                "tuned_confidence_min": round(rec.tuned_confidence_min, 4),
                "tuned_size_multiplier": round(rec.tuned_size_multiplier, 4),
                "last_updated": rec.last_updated,
            }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, signal_type: str, chain: str) -> StrategyRecord:
        key = self._key(signal_type, chain)
        if key not in self._records:
            self._records[key] = StrategyRecord(signal_type=signal_type, chain=chain)
        return self._records[key]

    def record_outcome(self, signal_type: str, chain: str, pnl_pct: float):
        """Record a trade outcome and auto-save."""
        rec = self.get(signal_type, chain)
        rec.total_trades += 1
        rec.total_pnl_pct += pnl_pct

        if pnl_pct > 0.01:
            rec.wins += 1
            rec.avg_win_pct = ((rec.avg_win_pct * (rec.wins - 1)) + pnl_pct) / rec.wins
        elif pnl_pct < -0.01:
            rec.losses += 1
            rec.avg_loss_pct = ((rec.avg_loss_pct * (rec.losses - 1)) + pnl_pct) / rec.losses
        else:
            rec.breakeven += 1

        rec.best_pnl_pct = max(rec.best_pnl_pct, pnl_pct)
        rec.worst_pnl_pct = min(rec.worst_pnl_pct, pnl_pct)
        rec.last_updated = int(time.time())

        self._save()

    def win_rate(self, signal_type: str, chain: str) -> Optional[float]:
        rec = self.get(signal_type, chain)
        if rec.total_trades == 0:
            return None
        return rec.wins / rec.total_trades

    def all_records(self) -> list[dict]:
        return [
            {
                "signal_type": r.signal_type,
                "chain": r.chain,
                "total_trades": r.total_trades,
                "win_rate": round(r.wins / r.total_trades, 3) if r.total_trades > 0 else None,
                "total_pnl_pct": round(r.total_pnl_pct * 100, 2),
                "avg_win_pct": round(r.avg_win_pct * 100, 2),
                "avg_loss_pct": round(r.avg_loss_pct * 100, 2),
                "tuned_tp_pct": round(r.tuned_tp_pct * 100, 2),
                "tuned_sl_pct": round(r.tuned_sl_pct * 100, 2),
                "tuned_confidence_min": r.tuned_confidence_min,
                "tuned_size_multiplier": r.tuned_size_multiplier,
            }
            for r in self._records.values()
        ]


class SelfTuner:
    """
    Reads the strategy ledger and adjusts trading parameters.
    Recomputes after every N trades (tuning_interval).
    
    Adaptation rules:
    - High win rate (>60%) + enough samples → increase size, relax confidence
    - Low win rate (<40%) + enough samples → decrease size, tighten confidence
    - Avg win >> avg loss → widen TP, keep SL
    - Avg loss >> avg win → tighten SL
    """

    MIN_SAMPLES = 5  # need at least this many trades before tuning

    def __init__(self, ledger: StrategyLedger, defaults: dict = None):
        self.ledger = ledger
        defaults = defaults or {}
        self.default_tp = defaults.get("take_profit_pct", 0.08)
        self.default_sl = defaults.get("stop_loss_pct", 0.04)
        self.default_confidence = defaults.get("trade_confidence_min", 0.70)

    def tune(self, signal_type: str, chain: str) -> dict:
        """
        Returns tuned parameters for a signal_type/chain pair.
        Falls back to defaults if insufficient data.
        """
        rec = self.ledger.get(signal_type, chain)

        if rec.total_trades < self.MIN_SAMPLES:
            return {
                "tp_pct": self.default_tp,
                "sl_pct": self.default_sl,
                "confidence_min": self.default_confidence,
                "size_multiplier": 1.0,
                "source": "default",
            }

        win_rate = rec.wins / rec.total_trades

        # ── TP/SL Adjustment ─────────────────────────────────
        tp = self.default_tp
        sl = self.default_sl

        if rec.avg_win_pct > 0 and abs(rec.avg_loss_pct) > 0:
            # If average win is large relative to loss, we can widen TP
            rr_ratio = rec.avg_win_pct / abs(rec.avg_loss_pct)
            if rr_ratio > 2.0:
                tp = min(self.default_tp * 1.3, 0.20)   # widen up to 20%
            elif rr_ratio < 0.8:
                sl = max(self.default_sl * 0.75, 0.02)  # tighten SL to 2% min

        # If we're often hitting SL (low win rate), tighten SL
        if win_rate < 0.35:
            sl = max(self.default_sl * 0.7, 0.02)
        # If rarely hitting SL (high win rate), we can relax SL slightly
        elif win_rate > 0.65:
            sl = min(self.default_sl * 1.2, 0.08)

        # ── Confidence Adjustment ─────────────────────────────
        confidence = self.default_confidence
        if win_rate > 0.60:
            confidence = max(self.default_confidence - 0.05, 0.55)
        elif win_rate < 0.40:
            confidence = min(self.default_confidence + 0.10, 0.90)

        # ── Size Adjustment ───────────────────────────────────
        size_mult = 1.0
        if win_rate > 0.60 and rec.total_pnl_pct > 0:
            size_mult = min(1.5, 1.0 + (win_rate - 0.5))
        elif win_rate < 0.40:
            size_mult = max(0.3, 1.0 - (0.5 - win_rate) * 2)

        # Store back into ledger
        rec.tuned_tp_pct = round(tp, 4)
        rec.tuned_sl_pct = round(sl, 4)
        rec.tuned_confidence_min = round(confidence, 4)
        rec.tuned_size_multiplier = round(size_mult, 4)

        return {
            "tp_pct": tp,
            "sl_pct": sl,
            "confidence_min": confidence,
            "size_multiplier": size_mult,
            "source": "tuned",
            "win_rate": round(win_rate, 3),
            "sample_count": rec.total_trades,
        }

    def tune_all(self) -> list[dict]:
        """Re-tune all tracked strategies and return results."""
        results = []
        for key, rec in self.ledger._records.items():
            result = self.tune(rec.signal_type, rec.chain)
            result["signal_type"] = rec.signal_type
            result["chain"] = rec.chain
            results.append(result)
        self.ledger._save()
        return results

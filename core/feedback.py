"""
AVE SAGE — Feedback
Trade outcome writer — closes the learning loop.
When a position closes, this module writes the result back into the
vector store so future RAG queries benefit from historical outcomes.
"""

import logging
import time
from typing import Optional
from core.chunker import build_outcome_chunk, MemoryChunk
from core.embedder import VectorStore

logger = logging.getLogger(__name__)


class FeedbackWriter:
    """
    Records trade outcomes into the knowledge base.
    Called when a position is closed (TP/SL hit or manual close).
    Each outcome becomes a searchable chunk that enriches future signal evaluation.
    """

    def __init__(self, store: VectorStore):
        self.store = store
        self._outcome_count = 0
        self._win_count = 0
        self._loss_count = 0

    def record(
        self,
        chain: str,
        token: str,
        token_symbol: str,
        trade_id: str,
        signal_type: str,
        action: str,
        entry_price: float,
        exit_price: float,
        rag_context_summary: str = "",
        timestamp: Optional[int] = None,
    ) -> MemoryChunk:
        """
        Record a trade outcome into the knowledge base.
        Returns the stored MemoryChunk.
        """
        ts = timestamp or int(time.time())

        # Compute PnL
        pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
        if action == "sell":
            pnl_pct = -pnl_pct

        # Classify outcome
        if pnl_pct > 0.01:
            outcome = "win"
            self._win_count += 1
        elif pnl_pct < -0.01:
            outcome = "loss"
            self._loss_count += 1
        else:
            outcome = "breakeven"

        self._outcome_count += 1

        chunk = build_outcome_chunk(
            chain=chain,
            token=token,
            token_symbol=token_symbol,
            trade_id=trade_id,
            signal_type=signal_type,
            action=action,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            outcome=outcome,
            rag_context_summary=rag_context_summary[:200],
            timestamp=ts,
        )

        self.store.upsert(chunk)
        logger.info(
            f"[FEEDBACK] Outcome #{self._outcome_count}: {outcome.upper()} "
            f"PnL={pnl_pct*100:+.2f}% — {token_symbol} ({chain})"
        )
        return chunk

    def stats(self) -> dict:
        """Summary statistics for the dashboard."""
        total = self._outcome_count
        return {
            "total_outcomes": total,
            "wins": self._win_count,
            "losses": self._loss_count,
            "breakeven": total - self._win_count - self._loss_count,
            "win_rate": round(self._win_count / total, 3) if total > 0 else None,
        }

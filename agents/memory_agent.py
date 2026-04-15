"""
AVE SAGE — Memory Agent
Manages the knowledge base lifecycle: cleanup, compaction, stats, and query interface.
Provides high-level memory operations used by the dashboard and OpenClaw integration.
"""

import logging
import time
from typing import Optional
from core.embedder import VectorStore
from core.feedback import FeedbackWriter

logger = logging.getLogger(__name__)


class MemoryAgent:
    """
    Manages SAGE's knowledge base.
    - Query interface for natural-language questions
    - Cleanup of stale/expired chunks
    - Memory statistics and health reporting
    """

    def __init__(self, store: VectorStore, feedback: FeedbackWriter, cfg: dict):
        self.store = store
        self.feedback = feedback
        self.lookback_hours = cfg.get("lookback_hours", 168)  # 7 days
        self.max_context_chunks = cfg.get("max_context_chunks", 8)
        self.similarity_threshold = cfg.get("similarity_threshold", 0.60)

    def query(
        self,
        question: str,
        chain: Optional[str] = None,
        token: Optional[str] = None,
        chunk_type: Optional[str] = None,
        n_results: int = 8,
    ) -> dict:
        """
        Natural language query against the knowledge base.
        Returns formatted context and raw chunks.
        """
        chunks = self.store.query(
            query_text=question,
            n_results=n_results,
            chain_filter=chain,
            token_filter=token,
            chunk_type_filter=chunk_type,
            similarity_threshold=self.similarity_threshold,
        )

        context = "\n".join(f"- {c['document']}" for c in chunks) if chunks else "No relevant memories found."

        return {
            "query": question,
            "context": context,
            "chunks_used": len(chunks),
            "chunks": chunks,
        }

    def get_token_history(self, chain: str, token_symbol: str, hours: int = 168) -> list[dict]:
        """Retrieve all memory about a specific token within a time window."""
        return self.store.query(
            query_text=f"{token_symbol} market activity signals outcomes on {chain}",
            n_results=20,
            chain_filter=chain,
            min_timestamp=int(time.time()) - hours * 3600,
        )

    def get_signal_performance(self, signal_type: str, chain: Optional[str] = None) -> dict:
        """Get historical performance stats for a signal type."""
        outcomes = self.store.query(
            query_text=f"trade outcome result for signal {signal_type}",
            n_results=20,
            chain_filter=chain,
            chunk_type_filter="outcome_event",
        )

        if not outcomes:
            return {"signal_type": signal_type, "sample_size": 0, "win_rate": None, "avg_pnl_pct": None}

        wins = 0
        pnls = []
        for o in outcomes:
            meta = o.get("metadata", {})
            if meta.get("outcome") == "win":
                wins += 1
            pnl = meta.get("pnl_pct", 0)
            pnls.append(pnl)

        n = len(outcomes)
        return {
            "signal_type": signal_type,
            "chain": chain or "all",
            "sample_size": n,
            "win_rate": round(wins / n, 3) if n > 0 else None,
            "avg_pnl_pct": round(sum(pnls) / n, 4) if pnls else None,
            "best_pnl": round(max(pnls), 4) if pnls else None,
            "worst_pnl": round(min(pnls), 4) if pnls else None,
        }

    def cleanup_stale(self, max_age_hours: int = 720) -> int:
        """
        Remove chunks older than max_age_hours (default 30 days).
        Outcome events are preserved indefinitely — they're the learning history.
        Returns count of removed chunks.
        """
        cutoff = int(time.time()) - max_age_hours * 3600
        try:
            # Get old non-outcome chunks
            stale = self.store._collection.get(
                where={"$and": [
                    {"timestamp": {"$lt": cutoff}},
                    {"chunk_type": {"$ne": "outcome_event"}},
                ]},
                limit=500,
                include=["metadatas"],
            )
            ids = stale.get("ids", [])
            if ids:
                self.store._collection.delete(ids=ids)
                logger.info(f"[MEMORY] Cleaned up {len(ids)} stale chunks (>{max_age_hours}h old)")
            return len(ids)
        except Exception as e:
            logger.error(f"[MEMORY] Cleanup failed: {e}")
            return 0

    def health(self) -> dict:
        """Full health report for the knowledge base."""
        store_stats = self.store.stats()
        feedback_stats = self.feedback.stats()
        return {
            "memory": store_stats,
            "outcomes": feedback_stats,
            "lookback_hours": self.lookback_hours,
        }

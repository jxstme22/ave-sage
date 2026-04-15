"""
AVE SAGE — RAG Engine
Queries the vector store to build rich context for agent reasoning.
The core of SAGE's memory advantage: "what do I know about situations like this?"
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional
from core.embedder import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    query: str
    chunks: list[dict]
    context_text: str
    outcome_stats: dict        # win_rate, avg_pnl, sample_size
    confidence_boost: float    # 0.0–0.3 added to signal confidence based on history


class RAGEngine:
    """
    Builds contextual memory packages for the SAGE agent.
    Before any trade decision, the agent calls retrieve() to get:
    1. Semantically similar past market events
    2. Historical outcomes for similar signals
    3. Statistical summary of past performance
    """

    def __init__(self, store: VectorStore, cfg: dict):
        self.store = store
        self.max_chunks = cfg.get("max_context_chunks", 8)
        self.similarity_threshold = cfg.get("similarity_threshold", 0.60)
        self.lookback_hours = cfg.get("lookback_hours", 168)  # 7 days default

    def retrieve(
        self,
        signal_type: str,
        token_symbol: str,
        chain: str,
        current_conditions: dict,
        n_results: Optional[int] = None,
    ) -> RAGContext:
        """
        Main retrieval method. Called before agent makes a trade decision.

        current_conditions example:
        {
            "price_change_1h": 0.043,
            "volume_multiplier": 3.2,
            "risk_score": 0.12,
            "trending_rank": 4,
        }
        """
        n = n_results or self.max_chunks
        query_text = self._build_query(signal_type, token_symbol, chain, current_conditions)

        # 1. Semantic search: similar market situations
        similar_events = self.store.query(
            query_text=query_text,
            n_results=n,
            chain_filter=chain,
            similarity_threshold=self.similarity_threshold,
            min_timestamp=int(time.time()) - self.lookback_hours * 3600,
        )

        # 2. Outcome history: what happened after similar signals
        outcomes = self.store.query_outcomes_for_signal(signal_type, chain, n=5)

        # 3. Build stats from outcomes
        outcome_stats = self._compute_outcome_stats(outcomes)

        # 4. Build confidence boost from history
        confidence_boost = self._compute_confidence_boost(outcome_stats)

        # 5. Format context text for LLM prompt
        context_text = self._format_context(similar_events, outcomes, outcome_stats, current_conditions)

        return RAGContext(
            query=query_text,
            chunks=similar_events + outcomes,
            context_text=context_text,
            outcome_stats=outcome_stats,
            confidence_boost=confidence_boost,
        )

    def retrieve_for_dashboard(self, chain: str, token_symbol: str) -> list[dict]:
        """Lighter retrieval for dashboard display — no stat computation."""
        return self.store.query(
            query_text=f"{token_symbol} market activity {chain}",
            n_results=10,
            chain_filter=chain,
        )

    def _build_query(self, signal: str, symbol: str, chain: str, conditions: dict) -> str:
        """
        Constructs a natural language query optimized for semantic retrieval.
        The more descriptive the query, the better the RAG results.
        """
        price_change = conditions.get("price_change_1h", 0)
        vol_mult = conditions.get("volume_multiplier", 1.0)
        risk = conditions.get("risk_score", 0.0)
        rank = conditions.get("trending_rank")

        parts = [
            f"{symbol} on {chain} showing {signal} signal.",
            f"Price changed {price_change*100:+.1f}% in the last hour.",
            f"Volume is {vol_mult:.1f}x the average.",
            f"Risk score: {risk:.2f}.",
        ]
        if rank:
            parts.append(f"Currently trending #{rank}.")

        parts.append("Similar historical market events and outcomes.")
        return " ".join(parts)

    def _compute_outcome_stats(self, outcomes: list[dict]) -> dict:
        """Compute win rate and avg pnl from outcome chunks."""
        if not outcomes:
            return {"sample_size": 0, "win_rate": None, "avg_pnl_pct": None}

        wins = 0
        pnls = []

        for o in outcomes:
            meta = o.get("metadata", {})
            outcome = meta.get("outcome", "")
            pnl = meta.get("pnl_pct", 0)
            if outcome == "win":
                wins += 1
            pnls.append(pnl)

        n = len(outcomes)
        return {
            "sample_size": n,
            "win_rate": round(wins / n, 3) if n > 0 else None,
            "avg_pnl_pct": round(sum(pnls) / n, 4) if pnls else None,
            "best_pnl": max(pnls) if pnls else None,
            "worst_pnl": min(pnls) if pnls else None,
        }

    def _compute_confidence_boost(self, stats: dict) -> float:
        """
        Adjusts base signal confidence based on historical performance.
        Strong win rate + sufficient sample = meaningful boost.
        No history = slight positive boost (fresh opportunity, not penalized).
        Consistent losses = negative boost (warning).
        """
        n = stats.get("sample_size", 0)
        if n == 0:
            return 0.05  # slight boost: fresh opportunity, no negative history
        if n < 3:
            return 0.03  # minor boost: too few samples to judge negatively

        win_rate = stats.get("win_rate", 0.5)
        avg_pnl = stats.get("avg_pnl_pct", 0)

        boost = 0.0
        if win_rate >= 0.7:
            boost += 0.15
        elif win_rate >= 0.55:
            boost += 0.05
        elif win_rate < 0.4:
            boost -= 0.15

        if avg_pnl and avg_pnl > 0.05:
            boost += 0.10
        elif avg_pnl and avg_pnl < -0.05:
            boost -= 0.10

        # Scale boost down if sample is small
        if n < 5:
            boost *= 0.5

        return round(max(-0.25, min(0.25, boost)), 3)

    def _format_context(
        self,
        similar_events: list[dict],
        outcomes: list[dict],
        stats: dict,
        conditions: dict,
    ) -> str:
        sections = []

        # Current conditions summary
        sections.append(
            "=== CURRENT MARKET CONDITIONS ===\n"
            + "\n".join(f"  {k}: {v}" for k, v in conditions.items())
        )

        # Historical similar events
        if similar_events:
            sections.append("=== SIMILAR HISTORICAL EVENTS ===")
            for i, evt in enumerate(similar_events[:5], 1):
                sim = evt.get("similarity", 0)
                sections.append(f"  [{i}] (sim={sim:.2f}) {evt['document']}")

        # Historical outcomes
        if outcomes:
            sections.append("=== HISTORICAL OUTCOMES FOR THIS SIGNAL ===")
            for o in outcomes[:3]:
                sections.append(f"  • {o['document']}")

        # Statistics
        if stats["sample_size"] > 0:
            wr = f"{stats['win_rate']*100:.0f}%" if stats["win_rate"] is not None else "N/A"
            apnl = f"{stats['avg_pnl_pct']*100:+.1f}%" if stats["avg_pnl_pct"] is not None else "N/A"
            sections.append(
                f"=== SIGNAL PERFORMANCE HISTORY ===\n"
                f"  Samples: {stats['sample_size']} | Win Rate: {wr} | Avg PnL: {apnl}"
            )
        else:
            sections.append("=== SIGNAL PERFORMANCE HISTORY ===\n  No prior outcomes for this signal type — treat as a fresh opportunity. Use signal metrics to decide.")

        return "\n\n".join(sections)

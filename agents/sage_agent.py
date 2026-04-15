"""
AVE SAGE — Main Reasoning Agent
The brain of SAGE. Receives SignalPackets + RAGContext,
calls an LLM for structured trade decisions, and dispatches to TradeAgent.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
import httpx
from core.rag_engine import RAGEngine, RAGContext
from core.signal_detector import SignalPacket
from core.chunker import build_outcome_chunk
from core.embedder import VectorStore

logger = logging.getLogger(__name__)


# ─── Trade Decision Model ─────────────────────────────────────────────────────

@dataclass
class TradeDecision:
    decision_id: str
    signal: SignalPacket
    action: str                  # "buy" | "sell" | "skip" | "watch"
    final_confidence: float      # base_confidence + rag_boost
    amount_usd: float
    reasoning: str               # LLM's chain of thought
    rag_context_summary: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    executed: bool = False
    execution_result: Optional[dict] = None


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are AVE SAGE, an on-chain market intelligence agent.
You analyze crypto market signals enriched with historical memory and make structured trade decisions.

Your decision process:
1. Evaluate the signal type and base confidence
2. Study the RAG context — what happened in similar situations before?
3. Check the risk score — never trade high-risk tokens
4. Output a structured JSON decision

Your response MUST be valid JSON with this exact schema:
{
  "action": "buy" | "sell" | "skip" | "watch",
  "confidence_adjustment": float between -0.2 and 0.2,
  "amount_usd_multiplier": float between 0.25 and 1.0,
  "reasoning": "concise explanation of the decision (2-3 sentences)",
  "key_factors": ["factor1", "factor2", "factor3"],
  "risk_flags": ["any concerns, or empty list"],
  "rag_summary": "one sentence summarizing what historical data showed"
}

Rules:
- NEVER trade tokens with risk_score > 0.65
- SKIP if historical win rate on this signal < 40% with 5+ samples
- WATCH if conditions are interesting but confidence < threshold
- If NO prior outcomes exist for this signal type, treat it as a FRESH OPPORTUNITY — do NOT penalize for missing history. Use the signal's own metrics (confidence, risk, trending) to decide.
- When sample size < 5, weight current signal metrics MORE than sparse historical data
- Reduce amount_usd_multiplier when risk_flags are present
- Start with small positions (0.25-0.5 multiplier) when history is limited
- Be concise. No preamble. Only valid JSON.
"""


# ─── SAGE Agent ───────────────────────────────────────────────────────────────

class SAGEAgent:
    """
    Main reasoning loop. For each signal:
    1. Fetch RAG context from VectorStore
    2. Build LLM prompt
    3. Parse structured JSON decision
    4. Apply confidence + position sizing
    5. Return TradeDecision
    """

    def __init__(
        self,
        rag_engine: RAGEngine,
        vector_store: VectorStore,
        openrouter_api_key: str,
        cfg: dict,
    ):
        self.rag = rag_engine
        self.store = vector_store
        self.api_key = openrouter_api_key
        self.model = cfg.get("reasoning_model", "anthropic/claude-sonnet-4-20250514")
        self.min_confidence = cfg.get("trade_confidence_min", 0.70)
        self.max_position_usd = cfg.get("max_position_usd", 50.0)
        self.dry_run = cfg.get("dry_run", True)
        self._decision_log: list[TradeDecision] = []

    async def process_signal(self, signal: SignalPacket) -> TradeDecision:
        """Full reasoning pipeline for one signal."""
        logger.info(f"[SAGE] Processing signal: {signal.signal_type} — {signal.token_symbol} ({signal.chain})")

        # 1. Retrieve RAG context
        rag_ctx = self.rag.retrieve(
            signal_type=signal.signal_type,
            token_symbol=signal.token_symbol,
            chain=signal.chain,
            current_conditions=signal.conditions,
        )

        # 2. Build final confidence
        final_confidence = min(
            signal.base_confidence + rag_ctx.confidence_boost,
            0.97
        )

        # 3. Hard safety check: never reason about risky tokens
        risk_score = signal.conditions.get("risk_score", 0.0)
        if risk_score > 0.65:
            return self._force_skip(signal, final_confidence, rag_ctx, reason="Risk score too high")

        # 4. Build LLM prompt
        prompt = self._build_prompt(signal, final_confidence, rag_ctx)

        # 5. Call LLM
        try:
            await asyncio.sleep(0.5)  # rate limit protection
            llm_response = await self._call_llm(prompt)
        except Exception as e:
            logger.warning(f"[SAGE] LLM call failed: {e}")
            llm_response = ""

        # 6. Parse decision
        decision = self._parse_llm_response(signal, final_confidence, rag_ctx, llm_response)

        # 7. Apply final sizing
        decision = self._apply_sizing(decision)

        self._decision_log.append(decision)
        logger.info(
            f"[SAGE] Decision: {decision.action.upper()} {signal.token_symbol} "
            f"conf={decision.final_confidence:.2f} amt=${decision.amount_usd:.2f}"
        )
        return decision

    def _build_prompt(self, signal: SignalPacket, confidence: float, rag: RAGContext) -> str:
        return f"""SIGNAL RECEIVED
===============
Type: {signal.signal_type}
Token: {signal.token_symbol} ({signal.chain})
Base Confidence: {signal.base_confidence:.2f}
RAG Confidence Boost: {rag.confidence_boost:+.2f}
Final Confidence: {confidence:.2f}
Direction: {signal.direction}
Notes: {signal.notes}

{rag.context_text}

TASK: Based on this signal and historical memory, decide whether to act.
Output only valid JSON per the schema in your system prompt."""

    async def _call_llm(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/ave-sage",
                    "X-Title": "AVE SAGE",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                logger.warning(f"[SAGE] LLM API error: {data['error']}")
                return ""
            content = data["choices"][0]["message"]["content"]
            if not content:
                logger.warning(f"[SAGE] LLM returned empty content. finish_reason: {data['choices'][0].get('finish_reason')}")
            return (content or "").strip()

    def _parse_llm_response(
        self,
        signal: SignalPacket,
        confidence: float,
        rag: RAGContext,
        raw: str,
    ) -> TradeDecision:
        try:
            # Strip any accidental markdown fences
            clean = raw.replace("```json", "").replace("```", "").strip()
            # Try parsing directly first
            try:
                parsed = json.loads(clean)
            except json.JSONDecodeError:
                # Extract first JSON object from mixed text
                import re
                match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', clean)
                if match:
                    parsed = json.loads(match.group())
                else:
                    raise

            adjusted_confidence = confidence + parsed.get("confidence_adjustment", 0.0)
            adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

            return TradeDecision(
                decision_id=str(uuid.uuid4())[:12],
                signal=signal,
                action=parsed.get("action", "skip"),
                final_confidence=round(adjusted_confidence, 3),
                amount_usd=self.max_position_usd * parsed.get("amount_usd_multiplier", 0.5),
                reasoning=parsed.get("reasoning", "No reasoning provided"),
                rag_context_summary=parsed.get("rag_summary", rag.context_text[:100]),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[SAGE] LLM response parse failed: {e} — defaulting to skip")
            return self._force_skip(signal, confidence, rag, reason=f"LLM parse error: {e}")

    def _force_skip(self, signal: SignalPacket, confidence: float, rag: Optional[RAGContext], reason: str) -> TradeDecision:
        return TradeDecision(
            decision_id=str(uuid.uuid4())[:12],
            signal=signal,
            action="skip",
            final_confidence=confidence,
            amount_usd=0.0,
            reasoning=reason,
            rag_context_summary=rag.context_text[:80] if rag else "",
        )

    def _apply_sizing(self, decision: TradeDecision) -> TradeDecision:
        """Apply final position sizing rules."""
        # Below confidence threshold → force skip
        if decision.action in ("buy", "sell") and decision.final_confidence < self.min_confidence:
            decision.action = "watch"
            decision.amount_usd = 0.0
            decision.reasoning += f" [Confidence {decision.final_confidence:.2f} below threshold {self.min_confidence}]"

        # Cap position size
        decision.amount_usd = min(decision.amount_usd, self.max_position_usd)

        return decision

    def record_outcome(
        self,
        decision: TradeDecision,
        entry_price: float,
        exit_price: float,
    ):
        """
        Called when a trade closes. Writes outcome back to vector store.
        This is the learning loop — SAGE gets smarter from its own history.
        """
        if not decision.executed:
            return

        pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
        if decision.action == "sell":
            pnl_pct = -pnl_pct  # inverted for short direction

        outcome = "win" if pnl_pct > 0.01 else ("loss" if pnl_pct < -0.01 else "breakeven")

        chunk = build_outcome_chunk(
            chain=decision.signal.chain,
            token=decision.signal.token,
            token_symbol=decision.signal.token_symbol,
            trade_id=decision.decision_id,
            signal_type=decision.signal.signal_type,
            action=decision.action,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            outcome=outcome,
            rag_context_summary=decision.rag_context_summary[:200],
            timestamp=int(time.time()),
        )
        self.store.upsert(chunk)
        logger.info(f"[SAGE] Outcome recorded: {outcome.upper()} PnL={pnl_pct*100:+.2f}% — {decision.signal.token_symbol}")

    def record_outcome_from_position(self, pos: dict):
        """
        Called from the position monitor loop when a position closes.
        Looks up the original TradeDecision by decision_id and records the outcome.
        """
        decision_id = pos.get("decision_id", "")
        decision = next((d for d in self._decision_log if d.decision_id == decision_id), None)
        if decision and decision.executed:
            self.record_outcome(decision, pos.get("entry", 0), pos.get("exit", 0))

    async def chat(self, question: str, chain: Optional[str] = None) -> dict:
        """
        Conversational chat — user asks a question, SAGE answers using
        KB context + LLM reasoning.  Returns {answer, context_used, chunks_used}.
        """
        # 1. Semantic search — low threshold so conversational queries still match
        chunks = self.store.query(
            query_text=question,
            n_results=8,
            chain_filter=chain,
            similarity_threshold=0.05,
        )

        # 1b. Fallback: if semantic search returns nothing, use most recent chunks
        if not chunks:
            chunks = self.store.recent_chunks(n=8)

        # 2. Also fetch recent decisions for context
        recent = self.recent_decisions(5)
        decisions_text = ""
        if recent:
            lines = []
            for d in recent[:5]:
                lines.append(f"  [{d['action'].upper()}] {d['token']} ({d['chain']}) conf={d['confidence']:.2f} — {d['reasoning'][:150]}")
            decisions_text = "\n=== MY RECENT DECISIONS ===\n" + "\n".join(lines)

        # 3. KB stats for grounding
        kb_count = self.store.count()
        kb_stats = f"[KB: {kb_count} total memory chunks stored]"

        # 4. Build context
        if chunks:
            context = "\n".join(f"- [{c['metadata'].get('chunk_type','?')}] {c['document']}" for c in chunks)
        else:
            context = "(No chunks in knowledge base yet)"

        prompt = f"""USER QUESTION: {question}

{kb_stats}

=== RELEVANT KNOWLEDGE BASE CHUNKS ===
{context}
{decisions_text}

Answer the user's question using the context above. You have {kb_count} memory chunks — reference actual data.
Be concise, direct, and specific. Do NOT say the knowledge base is empty (it has {kb_count} chunks).
Respond in plain text. Be conversational but data-driven."""

        chat_system = (
            "You are AVE SAGE, an on-chain market intelligence agent. "
            "You help users understand market conditions, their portfolio, trading strategies, "
            "and signals you've detected. You have access to a knowledge base of market events, "
            "trade outcomes, and strategies. Be direct and data-driven."
        )

        # 4. Call LLM
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/ave-sage",
                        "X-Title": "AVE SAGE",
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 4096,
                        "messages": [
                            {"role": "system", "content": chat_system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    return {"answer": f"LLM error: {data['error']}", "chunks_used": len(chunks)}
                answer = (data["choices"][0]["message"]["content"] or "").strip()
                if not answer:
                    answer = "I received your question but couldn't generate a response. Please try again."
        except Exception as e:
            logger.error(f"[SAGE] Chat LLM call failed: {e}")
            # Fallback: return KB context directly
            if chunks:
                answer = f"I couldn't reach my reasoning engine, but here's what I found in my knowledge base:\n\n{context}"
            else:
                answer = f"I couldn't reach my reasoning engine and found no relevant data. Error: {e}"

        return {
            "answer": answer,
            "chunks_used": len(chunks),
            "context_used": context[:500] if chunks else "",
        }

    def recent_decisions(self, n: int = 20) -> list[dict]:
        return [
            {
                "id": d.decision_id,
                "token": d.signal.token_symbol,
                "chain": d.signal.chain,
                "signal": d.signal.signal_type,
                "action": d.action,
                "confidence": d.final_confidence,
                "amount_usd": d.amount_usd,
                "reasoning": d.reasoning,
                "executed": d.executed,
                "timestamp": d.timestamp,
            }
            for d in reversed(self._decision_log[-n:])
        ]

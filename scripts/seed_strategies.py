"""
AVE SAGE — Knowledge Base Seeder
Seeds the vector store with Solana-focused safe trading strategies,
risk management rules, and token evaluation criteria.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from core.chunker import MemoryChunk
from core.embedder import VectorStore
from config import settings

STRATEGIES = [
    # ── Volume Breakout Strategy ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Volume Breakout (Solana). When a Solana token's 15-min volume "
            "exceeds 3x its 48-hour average AND price is above VWAP, this is a bullish "
            "volume breakout. Entry: market buy with 0.5-1% of portfolio. "
            "Take profit: +8% from entry. Stop loss: -4% from entry. "
            "Confidence threshold: 0.75. Only enter if token has >$50k 24h liquidity "
            "and risk score below 0.6. Exit immediately if volume spike reverses "
            "within 5 minutes (likely fake breakout)."
        ),
    },
    # ── Trending Entry Strategy ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Trending Entry (Solana). When a token enters the AVE trending "
            "list top-10 for the first time with low risk score (<0.5), this signals "
            "early organic momentum. Entry: small position ($1-2). "
            "Take profit: +12% (trending tokens often have explosive moves). "
            "Stop loss: -5%. Only valid if the token has been trading for >24 hours "
            "(avoid brand-new rugs). Check holder count: need >500 unique holders."
        ),
    },
    # ── Whale Accumulation Strategy ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Whale Accumulation (Solana). When 3+ buy swaps of >$5000 "
            "occur within 15 minutes from different wallets, this indicates smart money "
            "accumulation. Entry: market buy after 3rd whale buy confirms pattern. "
            "Take profit: +10%. Stop loss: -4%. "
            "CRITICAL: Verify these are different wallets (not wash trading). "
            "Skip if token risk score >0.5 or if single wallet holds >15% of supply."
        ),
    },
    # ── Trend Acceleration Strategy ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Trend Acceleration (Solana). When price increases 3%+ in the last "
            "hour while volume is also increasing (volume multiplier >2x), the trend is "
            "accelerating. This is a momentum continuation signal. "
            "Entry: market buy with tight stop. Take profit: +8%. Stop loss: -3%. "
            "Best when combined with positive holder growth. "
            "Avoid if token already pumped >20% in 24h (likely too late)."
        ),
    },
    # ── Risk Exit Strategy ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Risk Exit (All Chains). When a token's risk score rises above 0.7 "
            "OR holder count drops >10% in 1 hour OR dev wallet makes a large sell, "
            "immediately close any open position at market price. Do not wait for stop loss. "
            "This is a safety-first exit to protect capital. "
            "Risk flags: honeypot detection, liquidity removal, large insider sells, "
            "sudden social media silence after hype."
        ),
    },
    # ── Position Sizing Rules ──
    {
        "type": "pattern_event",
        "symbol": "RULES",
        "text": (
            "RULES: Position Sizing. Never risk more than $2 per trade on Solana micro-caps. "
            "Max 3 concurrent positions. Daily loss limit: $5 (stop trading for the day). "
            "Drawdown limit: 15% of total capital. After 2 consecutive losses, reduce "
            "position size by 50% for the next 3 trades. After 3 consecutive wins, "
            "increase position size by 25% (max 2x original)."
        ),
    },
    # ── Token Evaluation Checklist ──
    {
        "type": "pattern_event",
        "symbol": "RULES",
        "text": (
            "RULES: Token Evaluation Checklist (Solana). Before buying ANY token, verify: "
            "1) Risk score <0.6 (low risk), 2) 24h volume >$50,000, 3) Holder count >500, "
            "4) Token age >24 hours, 5) No honeypot flag, 6) Liquidity >$20,000, "
            "7) Dev wallet holds <10% of supply, 8) Not a known scam or copycat. "
            "If ANY check fails, SKIP the trade regardless of other signals."
        ),
    },
    # ── Market Regime Awareness ──
    {
        "type": "pattern_event",
        "symbol": "STRATEGY",
        "text": (
            "STRATEGY: Market Regime Awareness. In a bear market (SOL down >5% in 24h), "
            "reduce all position sizes by 50% and increase confidence threshold to 0.85. "
            "In extreme fear (SOL down >10% in 24h), stop opening new positions entirely. "
            "In a bull market (SOL up >3% in 24h), standard sizing applies. "
            "Check SOL price trend before every trade decision."
        ),
    },
    # ── Outcome: Successful Volume Breakout ──
    {
        "type": "outcome_event",
        "symbol": "BONK",
        "text": (
            "OUTCOME: BUY BONK on Solana — volume breakout signal at $0.00001823. "
            "Volume was 4.2x average, price above VWAP. Take profit hit at +8.5% "
            "within 2 hours. PnL: +$0.17 on $2.00 position. Signal type: "
            "volume_breakout_bullish. Confidence was 0.82. "
            "LESSON: Volume breakouts on established meme tokens (>10k holders) "
            "are reliable when combined with positive market sentiment."
        ),
    },
    # ── Outcome: Failed Trending Entry ──
    {
        "type": "outcome_event",
        "symbol": "NEWTOKEN",
        "text": (
            "OUTCOME: BUY NEWTOKEN on Solana — trending entry signal. Token entered "
            "trending top-5 but was only 6 hours old. Stop loss hit at -4.8%. "
            "PnL: -$0.10 on $2.00 position. Signal type: trending_entry. Confidence was 0.71. "
            "LESSON: Tokens under 24 hours old are too risky even if trending. "
            "The trending list can be gamed by bot activity on new launches. "
            "Always enforce the 24-hour minimum age rule."
        ),
    },
    # ── Outcome: Whale Accumulation Win ──
    {
        "type": "outcome_event",
        "symbol": "RAY",
        "text": (
            "OUTCOME: BUY RAY on Solana — whale accumulation detected. 4 distinct wallets "
            "bought $5k-$12k within 10 minutes. Entry at $1.82. Price rose to $2.05 (+12.6%). "
            "Take profit hit. PnL: +$0.25 on $2.00 position. Signal: whale_accumulation. "
            "LESSON: Whale accumulation on tokens with established liquidity (>$500k) "
            "is one of the most reliable signals. Key: verify wallet diversity."
        ),
    },
    # ── Outcome: Risk Exit Saved Capital ──
    {
        "type": "outcome_event",
        "symbol": "SCAMCOIN",
        "text": (
            "OUTCOME: EMERGENCY EXIT SCAMCOIN on Solana — risk score spiked from 0.3 to 0.85 "
            "while holding a position. Immediately sold at market. Price crashed 70% within "
            "30 minutes after exit. PnL: -$0.05 (minor loss vs potential -$1.40). "
            "LESSON: Risk exit signals save capital. Never ignore rising risk scores. "
            "A small loss is always better than a catastrophic one."
        ),
    },
]


def seed():
    store = VectorStore(
        persist_dir=settings.memory.persist_dir,
        collection_name=settings.memory.collection_name,
        embedding_provider=settings.memory.embedding_provider,
        embedding_model=settings.memory.embedding_model,
    )

    ts = int(time.time())
    seeded = 0
    for i, s in enumerate(STRATEGIES):
        chunk = MemoryChunk(
            id=f"seed_strategy_{i:03d}",
            chunk_type=s["type"],
            chain="solana",
            token="strategy",
            token_symbol=s["symbol"],
            timestamp=ts - (i * 3600),  # space them out
            rag_text=s["text"],
            metadata={"source": "seed", "category": "strategy"},
        )
        if store.upsert(chunk):
            seeded += 1
            print(f"  [OK] {s['symbol']}: {s['text'][:60]}...")

    print(f"\nSeeded {seeded}/{len(STRATEGIES)} strategy chunks into KB.")
    print(f"Total chunks in store: {store.count()}")


if __name__ == "__main__":
    seed()

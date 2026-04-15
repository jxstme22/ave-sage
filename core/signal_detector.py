"""
AVE SAGE — Signal Detector
Analyzes accumulated market events to identify actionable patterns.
Produces SignalPacket objects consumed by the SAGE agent.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from core.collector import RawMarketEvent

logger = logging.getLogger(__name__)


@dataclass
class SignalPacket:
    signal_type: str               # see SIGNAL_TYPES below
    chain: str
    token: str
    token_symbol: str
    timestamp: int
    base_confidence: float         # 0.0–1.0 before RAG boost
    direction: str                 # "long" | "short" | "exit" | "watch"
    trigger_events: list[str]      # IDs of events that triggered this signal
    conditions: dict = field(default_factory=dict)
    notes: str = ""


# ─── Signal Type Registry ─────────────────────────────────────────────────────

SIGNAL_TYPES = {
    "volume_breakout_bullish":   "High volume bullish candle, above 3x average",
    "volume_breakout_bearish":   "High volume bearish candle, above 3x average",
    "whale_accumulation":        "Multiple large buys from same/similar wallets",
    "whale_distribution":        "Multiple large sells, potential exit",
    "trend_acceleration":        "Price change accelerating across timeframes",
    "risk_flag_raised":          "Risk score crossed warning threshold",
    "trending_entry":            "Token appeared in top 5 trending with low risk",
    "reversal_signal":           "Price reversal after extended move",
    "holder_surge":              "Rapid holder count increase",
    "consolidation_breakout":    "Low volatility followed by volume expansion",
}


# ─── Event Window ─────────────────────────────────────────────────────────────

class EventWindow:
    """
    Sliding window of recent events per token.
    Detects patterns across multiple events on the same token.
    """

    def __init__(self, window_seconds: int = 900):  # 15 min default
        self.window = window_seconds
        self._events: dict[str, list[RawMarketEvent]] = {}  # token -> events

    def add(self, evt: RawMarketEvent):
        key = f"{evt.chain}:{evt.token}"
        if key not in self._events:
            self._events[key] = []
        self._events[key].append(evt)
        self._evict(key)

    def get(self, chain: str, token: str) -> list[RawMarketEvent]:
        key = f"{chain}:{token}"
        self._evict(key)
        return self._events.get(key, [])

    def _evict(self, key: str):
        cutoff = int(time.time()) - self.window
        self._events[key] = [e for e in self._events.get(key, []) if e.timestamp >= cutoff]


# ─── Signal Detector ──────────────────────────────────────────────────────────

class SignalDetector:
    """
    Runs detection rules over an EventWindow.
    Each detect_* method returns a SignalPacket or None.
    """

    def __init__(self, cfg: dict):
        # Signal detector uses a lower confidence gate so SAGE sees more candidates.
        # SAGE + rules engine apply the final trade_confidence_min filter.
        self.min_confidence = 0.35
        self.vol_mult_threshold = cfg.get("volume_spike_multiplier", 2.0)
        self.window = EventWindow(window_seconds=cfg.get("signal_window_seconds", 900))
        self.risk_warn_threshold = cfg.get("risk_warn_threshold", 0.65)

    def ingest(self, evt: RawMarketEvent) -> list[SignalPacket]:
        """Process a new event and return any signals it triggers."""
        self.window.add(evt)
        recent = self.window.get(evt.chain, evt.token)
        signals = []

        # Run all detectors
        for detector_fn in [
            self._detect_volume_breakout,
            self._detect_whale_activity,
            self._detect_risk_flag,
            self._detect_trending_entry,
            self._detect_trend_acceleration,
            self._detect_holder_surge,
        ]:
            try:
                signal = detector_fn(evt, recent)
                if signal and signal.base_confidence >= self.min_confidence:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"[DETECTOR] {detector_fn.__name__} error: {e}")

        return signals

    def _detect_volume_breakout(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        if evt.event_type != "kline":
            return None
        vol_mult = evt.data.get("volume_multiplier", 1.0)
        if vol_mult < self.vol_mult_threshold:
            return None

        direction = evt.data.get("direction", "bullish")
        signal_type = f"volume_breakout_{direction}"
        candle_body = evt.data.get("candle_body_pct", 0)

        # Confidence: based on volume multiple + candle body size
        confidence = min(0.5 + (vol_mult - self.vol_mult_threshold) * 0.1 + candle_body * 2, 0.95)

        return SignalPacket(
            signal_type=signal_type,
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=round(confidence, 3),
            direction="long" if direction == "bullish" else "short",
            trigger_events=[evt.data.get("interval", "?")],
            conditions={
                "volume_multiplier": vol_mult,
                "candle_body_pct": candle_body,
                "interval": evt.data.get("interval"),
            },
            notes=f"Volume {vol_mult:.1f}x average on {evt.data.get('interval','?')} candle",
        )

    def _detect_whale_activity(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        if evt.event_type != "swap":
            return None

        recent_swaps = [e for e in recent if e.event_type == "swap"]
        swap_type = evt.data.get("swap_type", "unknown")

        # Count large swaps of same type in window
        same_direction = [s for s in recent_swaps if s.data.get("swap_type") == swap_type]
        total_usd = sum(s.data.get("amount_usd", 0) for s in same_direction)

        if len(same_direction) < 2 or total_usd < 20_000:
            return None

        signal_type = "whale_accumulation" if swap_type == "buy" else "whale_distribution"
        confidence = min(0.55 + (len(same_direction) * 0.05) + (total_usd / 200_000) * 0.2, 0.90)

        return SignalPacket(
            signal_type=signal_type,
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=round(confidence, 3),
            direction="long" if swap_type == "buy" else "short",
            trigger_events=[s.data.get("tx_hash", "")[:12] for s in same_direction],
            conditions={"swap_count": len(same_direction), "total_usd": total_usd},
            notes=f"{len(same_direction)} large {swap_type}s totaling ${total_usd:,.0f}",
        )

    def _detect_risk_flag(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        risk_score = evt.data.get("risk_score", 0.0)
        if risk_score < self.risk_warn_threshold:
            return None

        return SignalPacket(
            signal_type="risk_flag_raised",
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=risk_score,
            direction="exit",
            trigger_events=["risk_check"],
            conditions={"risk_score": risk_score},
            notes=f"Risk score {risk_score:.2f} — potential honeypot or rug",
        )

    def _detect_trending_entry(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        if evt.event_type != "trending":
            return None
        rank = evt.data.get("trending_rank", 100)
        risk = evt.data.get("ave_risk_level", evt.data.get("risk_score", -1))
        # price_change_1h from API is in percent (e.g. 5.3 = 5.3%)
        price_change = evt.data.get("price_change_1h", 0)

        # Relaxed: top 15 trending, risk < 4 (ave_risk_level scale), any positive momentum
        if rank > 15 or (risk >= 0 and risk > 4) or price_change < 0.5:
            return None

        confidence = round(0.40 + max(0, (10 - rank)) * 0.025 + min(abs(price_change) / 50, 0.20), 3)

        return SignalPacket(
            signal_type="trending_entry",
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=min(confidence, 0.85),
            direction="long",
            trigger_events=["trending_feed"],
            conditions={
                "trending_rank": rank,
                "risk_score": risk,
                "price_change_1h": price_change,
                "price_usd": evt.data.get("price_usd", 0.0),
            },
            notes=f"Trending #{rank} with low risk ({risk:.2f}) and positive momentum",
        )

    def _detect_trend_acceleration(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        if evt.event_type != "price":
            return None

        change_1h = evt.data.get("price_change_1h", 0)
        change_24h = evt.data.get("price_change_24h", 0)

        # Acceleration: 1h move is a large fraction of 24h move, all positive
        # Values are in percent (e.g. 5.3 = 5.3%)
        # Relaxed: 1.5% 1h move is enough to warrant attention
        if change_1h < 1.5 or change_24h <= 0:
            return None

        accel_ratio = change_1h / change_24h if change_24h > 0 else 0
        if accel_ratio < 0.15:
            return None

        confidence = round(min(0.40 + accel_ratio * 0.4, 0.88), 3)

        return SignalPacket(
            signal_type="trend_acceleration",
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=confidence,
            direction="long",
            trigger_events=["price_feed"],
            conditions={"price_change_1h": change_1h, "price_change_24h": change_24h, "accel_ratio": accel_ratio},
            notes=f"1h move ({change_1h*100:+.1f}%) is {accel_ratio*100:.0f}% of 24h total move",
        )

    def _detect_holder_surge(self, evt: RawMarketEvent, recent: list) -> Optional[SignalPacket]:
        if evt.event_type != "holder":
            return None
        delta = evt.data.get("holder_delta", 0)
        if delta < 200:
            return None

        confidence = min(0.55 + delta / 2000, 0.80)
        return SignalPacket(
            signal_type="holder_surge",
            chain=evt.chain,
            token=evt.token,
            token_symbol=evt.token_symbol,
            timestamp=evt.timestamp,
            base_confidence=round(confidence, 3),
            direction="long",
            trigger_events=["holder_feed"],
            conditions={"holder_delta": delta},
            notes=f"+{delta:,} new holders detected",
        )

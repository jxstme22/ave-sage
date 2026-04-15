"""
AVE SAGE — Trading Rules Engine
Guardrails and risk management rules applied before trade execution.
Prevents reckless trades, enforces daily limits, blacklists, cooldowns.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RulesConfig:
    max_daily_loss_usd: float = 100.0
    max_concurrent_positions: int = 5
    cooldown_after_loss_seconds: int = 300       # 5 min pause after a loss
    max_drawdown_pct: float = 0.15               # 15% total drawdown → halt
    min_liquidity_usd: float = 10_000
    max_risk_score: float = 0.65
    token_blacklist: list = field(default_factory=list)
    chain_whitelist: list = field(default_factory=lambda: ["solana", "bsc", "eth", "base"])
    max_position_pct_of_liquidity: float = 0.01  # never more than 1% of pool liq


@dataclass
class RuleVerdict:
    allowed: bool
    rule_name: str = ""
    reason: str = ""


class TradingRulesEngine:
    """
    Pre-trade gate. Every trade decision must pass ALL rules before execution.
    Tracks cumulative daily P&L, open position count, and cooldown state.
    """

    def __init__(self, cfg: dict = None):
        c = cfg or {}
        self.config = RulesConfig(
            max_daily_loss_usd=c.get("max_daily_loss_usd", 100.0),
            max_concurrent_positions=c.get("max_concurrent_positions", 5),
            cooldown_after_loss_seconds=c.get("cooldown_after_loss_seconds", 300),
            max_drawdown_pct=c.get("max_drawdown_pct", 0.15),
            min_liquidity_usd=c.get("min_liquidity_usd", 10_000),
            max_risk_score=c.get("max_risk_score", 0.65),
            token_blacklist=c.get("token_blacklist", []),
            chain_whitelist=c.get("chain_whitelist", ["solana", "bsc", "eth", "base"]),
            max_position_pct_of_liquidity=c.get("max_position_pct_of_liquidity", 0.01),
        )

        # Running state
        self._daily_pnl_usd: float = 0.0
        self._day_start: int = self._today_start()
        self._last_loss_time: int = 0
        self._initial_capital: float = 0.0
        self._current_capital: float = 0.0
        self._open_position_count: int = 0

    @staticmethod
    def _today_start() -> int:
        t = time.time()
        return int(t - (t % 86400))

    def _reset_daily_if_needed(self):
        today = self._today_start()
        if today != self._day_start:
            self._daily_pnl_usd = 0.0
            self._day_start = today

    def set_capital(self, initial: float, current: float):
        self._initial_capital = initial
        self._current_capital = current

    def set_open_position_count(self, count: int):
        self._open_position_count = count

    def record_trade_result(self, pnl_usd: float):
        """Update state after a trade closes."""
        self._reset_daily_if_needed()
        self._daily_pnl_usd += pnl_usd
        self._current_capital += pnl_usd
        if pnl_usd < 0:
            self._last_loss_time = int(time.time())

    def evaluate(self, decision) -> RuleVerdict:
        """
        Run all rules against a trade decision. Returns first failing rule,
        or an allowed verdict if all pass.
        decision: must have .signal.chain, .signal.token, .signal.conditions, .amount_usd
        """
        self._reset_daily_if_needed()
        checks = [
            self._check_chain_whitelist,
            self._check_token_blacklist,
            self._check_risk_score,
            self._check_liquidity,
            self._check_daily_loss,
            self._check_drawdown,
            self._check_concurrent_positions,
            self._check_cooldown,
            self._check_position_vs_liquidity,
        ]
        for check in checks:
            result = check(decision)
            if not result.allowed:
                logger.warning(f"[RULES] BLOCKED: {result.rule_name} — {result.reason}")
                return result
        return RuleVerdict(allowed=True)

    def _check_chain_whitelist(self, d) -> RuleVerdict:
        chain = d.signal.chain
        if chain not in self.config.chain_whitelist:
            return RuleVerdict(False, "chain_whitelist", f"Chain '{chain}' not whitelisted")
        return RuleVerdict(True)

    def _check_token_blacklist(self, d) -> RuleVerdict:
        token = d.signal.token
        if token in self.config.token_blacklist:
            return RuleVerdict(False, "token_blacklist", f"Token {token} is blacklisted")
        return RuleVerdict(True)

    def _check_risk_score(self, d) -> RuleVerdict:
        risk = d.signal.conditions.get("risk_score", 0.0)
        if risk > self.config.max_risk_score:
            return RuleVerdict(False, "max_risk_score",
                               f"Risk {risk:.2f} > limit {self.config.max_risk_score}")
        return RuleVerdict(True)

    def _check_liquidity(self, d) -> RuleVerdict:
        liq = d.signal.conditions.get("liquidity_usd", float("inf"))
        if liq < self.config.min_liquidity_usd:
            return RuleVerdict(False, "min_liquidity",
                               f"Liquidity ${liq:,.0f} < min ${self.config.min_liquidity_usd:,.0f}")
        return RuleVerdict(True)

    def _check_daily_loss(self, d) -> RuleVerdict:
        if self._daily_pnl_usd < -self.config.max_daily_loss_usd:
            return RuleVerdict(False, "max_daily_loss",
                               f"Daily loss ${abs(self._daily_pnl_usd):.2f} exceeds limit ${self.config.max_daily_loss_usd:.2f}")
        return RuleVerdict(True)

    def _check_drawdown(self, d) -> RuleVerdict:
        if self._initial_capital <= 0:
            return RuleVerdict(True)
        drawdown = (self._initial_capital - self._current_capital) / self._initial_capital
        if drawdown > self.config.max_drawdown_pct:
            return RuleVerdict(False, "max_drawdown",
                               f"Drawdown {drawdown*100:.1f}% > limit {self.config.max_drawdown_pct*100:.0f}%")
        return RuleVerdict(True)

    def _check_concurrent_positions(self, d) -> RuleVerdict:
        if self._open_position_count >= self.config.max_concurrent_positions:
            return RuleVerdict(False, "max_concurrent_positions",
                               f"{self._open_position_count} open >= limit {self.config.max_concurrent_positions}")
        return RuleVerdict(True)

    def _check_cooldown(self, d) -> RuleVerdict:
        if self._last_loss_time <= 0:
            return RuleVerdict(True)
        elapsed = int(time.time()) - self._last_loss_time
        if elapsed < self.config.cooldown_after_loss_seconds:
            remaining = self.config.cooldown_after_loss_seconds - elapsed
            return RuleVerdict(False, "cooldown_after_loss",
                               f"Cooling down — {remaining}s remaining after last loss")
        return RuleVerdict(True)

    def _check_position_vs_liquidity(self, d) -> RuleVerdict:
        liq = d.signal.conditions.get("liquidity_usd", 0)
        if liq <= 0:
            return RuleVerdict(True)
        max_amt = liq * self.config.max_position_pct_of_liquidity
        if d.amount_usd > max_amt:
            return RuleVerdict(False, "position_vs_liquidity",
                               f"Position ${d.amount_usd:.2f} > {self.config.max_position_pct_of_liquidity*100:.1f}% of pool liq ${liq:,.0f}")
        return RuleVerdict(True)

    def status(self) -> dict:
        self._reset_daily_if_needed()
        drawdown = 0.0
        if self._initial_capital > 0:
            drawdown = (self._initial_capital - self._current_capital) / self._initial_capital
        cooldown_remaining = max(0, self.config.cooldown_after_loss_seconds - (int(time.time()) - self._last_loss_time)) if self._last_loss_time > 0 else 0
        return {
            "daily_pnl_usd": round(self._daily_pnl_usd, 2),
            "drawdown_pct": round(drawdown * 100, 2),
            "open_positions": self._open_position_count,
            "cooldown_remaining_s": cooldown_remaining,
            "halted": self._daily_pnl_usd < -self.config.max_daily_loss_usd or drawdown > self.config.max_drawdown_pct,
        }

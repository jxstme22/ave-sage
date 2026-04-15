"""
AVE SAGE — Trade Agent
Executes trade decisions via AVE Cloud proxy wallet API.
Uses the official ave-cloud-skill SDK for correct URLs, HMAC signing, and endpoints.
"""

import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Optional
from agents.sage_agent import TradeDecision

# Add the official SDK to the Python path
_SDK_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ave-cloud-skill", "scripts",
)
if _SDK_SCRIPTS not in sys.path:
    sys.path.insert(0, _SDK_SCRIPTS)

from ave.config import V2_BASE, TRADE_BASE
from ave.headers import data_headers, trade_proxy_headers
from ave.http_async import async_get, async_post

logger = logging.getLogger(__name__)


# ─── Position Model ───────────────────────────────────────────────────────────

@dataclass
class Position:
    position_id: str
    decision_id: str
    chain: str
    token: str
    token_symbol: str
    action: str
    amount_usd: float
    entry_price: float
    signal_type: str = ""
    current_price: float = 0.0
    exit_price: float = 0.0
    tp_price: float = 0.0
    sl_price: float = 0.0
    status: str = "open"           # open | closed | cancelled
    pnl_pct: float = 0.0
    open_time: int = field(default_factory=lambda: int(time.time()))
    close_time: Optional[int] = None
    tx_hash: str = ""
    error: str = ""


# ─── Trade Agent ──────────────────────────────────────────────────────────────

class TradeAgent:
    """
    Wraps AVE Cloud's proxy wallet trading API.
    Uses official SDK for correct base URL (bot-api.ave.ai) and HMAC signing.
    """

    def __init__(self, api_key: str, secret_key: str, cfg: dict):
        self.api_key = api_key
        self.secret_key = secret_key
        self.dry_run = cfg.get("dry_run", True)
        self.tp_pct = cfg.get("take_profit_pct", 0.08)
        self.sl_pct = cfg.get("stop_loss_pct", 0.04)
        self.assets_id = cfg.get("assets_id", "")
        self._positions: dict[str, Position] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def _trade_post(self, path: str, body: dict) -> dict:
        """POST to trade API with official HMAC proxy signing."""
        url = f"{TRADE_BASE}{path}"
        try:
            headers = trade_proxy_headers("POST", path, body)
            resp = await async_post(url, body, headers)
            return resp.json()
        except Exception as e:
            logger.error(f"[TRADE] POST {path} failed: {e}")
            return {"error": str(e)}

    async def _trade_get(self, path: str, params: dict = None) -> dict:
        """GET from trade API with official HMAC proxy signing."""
        url = f"{TRADE_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            headers = trade_proxy_headers("GET", path)
            resp = await async_get(url, headers)
            return resp.json()
        except Exception as e:
            logger.error(f"[TRADE] GET {path} failed: {e}")
            return {"error": str(e)}

    async def execute(self, decision: TradeDecision) -> Position:
        """
        Main entry point. Converts a TradeDecision into a live position.
        Returns a Position object (real or simulated in dry_run mode).
        """
        if decision.action not in ("buy", "sell"):
            logger.info(f"[TRADE] Skipping non-actionable decision: {decision.action}")
            return None

        # Prevent duplicate open positions for the same token+chain
        if decision.action == "buy":
            for pos in self._positions.values():
                if (pos.token == decision.signal.token
                        and pos.chain == decision.signal.chain
                        and pos.status == "open"):
                    logger.info(
                        f"[TRADE] Skipping duplicate BUY {decision.signal.token_symbol} "
                        f"— position {pos.position_id} already open"
                    )
                    return None

        if self.dry_run:
            return await self._simulate_trade(decision)
        else:
            return await self._execute_live_trade(decision)

    async def _simulate_trade(self, decision: TradeDecision) -> Position:
        """Dry-run mode: simulate position without hitting AVE trade API."""
        logger.info(f"[TRADE][DRY-RUN] Simulating {decision.action.upper()} "
                    f"{decision.signal.token_symbol} ${decision.amount_usd:.2f}")

        # Get current price via REST data API; fall back to signal price if 0
        signal_price = float(decision.signal.conditions.get("price_usd", 0.0) or 0.0)
        price = await self._get_current_price(decision.signal.chain, decision.signal.token)
        if price == 0.0 and signal_price > 0:
            price = signal_price

        pos = Position(
            position_id=f"sim_{uuid.uuid4().hex[:8]}",
            decision_id=decision.decision_id,
            chain=decision.signal.chain,
            token=decision.signal.token,
            token_symbol=decision.signal.token_symbol,
            action=decision.action,
            amount_usd=decision.amount_usd,
            entry_price=price,
            signal_type=decision.signal.signal_type,
            current_price=price,
            tp_price=price * (1 + self.tp_pct) if decision.action == "buy" else price * (1 - self.tp_pct),
            sl_price=price * (1 - self.sl_pct) if decision.action == "buy" else price * (1 + self.sl_pct),
            status="open",
            tx_hash=f"sim_{uuid.uuid4().hex[:16]}",
        )

        self._positions[pos.position_id] = pos
        decision.executed = True
        decision.execution_result = {"position_id": pos.position_id, "dry_run": True}
        logger.info(f"[TRADE][DRY-RUN] Position opened: {pos.position_id} entry={price:.6f}")
        return pos

    async def _execute_live_trade(self, decision: TradeDecision) -> Position:
        """Live mode: execute via AVE proxy wallet using official SDK endpoints."""
        logger.info(f"[TRADE][LIVE] Executing {decision.action.upper()} "
                    f"{decision.signal.token_symbol} ${decision.amount_usd:.2f}")

        # Get token price for position tracking
        signal_price = float(decision.signal.conditions.get("price_usd", 0.0) or 0.0)
        price = await self._get_current_price(decision.signal.chain, decision.signal.token)
        if price == 0.0 and signal_price > 0:
            logger.info(f"[TRADE] Using signal-embedded price {signal_price:.8f} for {decision.signal.token_symbol}")
            price = signal_price
        tp = price * (1 + self.tp_pct) if decision.action == "buy" else price * (1 - self.tp_pct)
        sl = price * (1 - self.sl_pct) if decision.action == "buy" else price * (1 + self.sl_pct)

        chain = decision.signal.chain

        # Convert USD amount to native token lamports/wei
        if chain == "solana":
            sol_price = await self._get_native_price("solana")
            if sol_price <= 0:
                logger.warning("[TRADE] Cannot get SOL price for conversion. Skipping.")
                return None
            native_amount = decision.amount_usd / sol_price
            in_amount_raw = str(int(native_amount * 1e9))  # lamports
            gas = "1000000"   # 0.001 SOL MEV minimum
            native_token = "sol"
        else:
            # EVM chains (bsc, eth, base) — use native coin placeholder
            native_price = await self._get_native_price(chain)
            if native_price <= 0:
                logger.warning(f"[TRADE] Cannot get native price for {chain}. Skipping.")
                return None
            native_amount = decision.amount_usd / native_price
            in_amount_raw = str(int(native_amount * 1e18))  # wei
            gas = ""
            native_token = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

        if decision.action == "buy":
            in_token = native_token
            out_token = decision.signal.token
        else:
            in_token = decision.signal.token
            out_token = native_token
            # For sells, inAmount is token amount — use full position balance
            # For now, use the raw amount as-is (assumes small position)

        body = {
            "chain": chain,
            "assetsId": self.assets_id,
            "inTokenAddress": in_token,
            "outTokenAddress": out_token,
            "inAmount": in_amount_raw,
            "swapType": decision.action,
            "slippage": "1000",   # 10% slippage for meme coins
            "useMev": True,
        }
        if gas:
            body["gas"] = gas

        logger.info(f"[TRADE][LIVE] Swap payload: chain={chain} "
                     f"in={in_token[:8]}… out={out_token[:8]}… "
                     f"amount={in_amount_raw} type={decision.action}")

        result = await self._trade_post("/v1/thirdParty/tx/sendSwapOrder", body)

        # Check for API-level error
        if "error" in result or result.get("status") not in (0, 200):
            error_msg = result.get("error", result.get("msg", "Unknown error"))
            logger.error(f"[TRADE][LIVE] Swap failed: {error_msg}")
            pos = Position(
                position_id=f"err_{uuid.uuid4().hex[:8]}",
                decision_id=decision.decision_id,
                chain=chain,
                token=decision.signal.token,
                token_symbol=decision.signal.token_symbol,
                action=decision.action,
                amount_usd=decision.amount_usd,
                entry_price=price,
                status="cancelled",
                error=error_msg,
            )
            self._positions[pos.position_id] = pos
            return pos

        # Order submitted — extract order ID
        order_id = result.get("data", {}).get("id", "")
        logger.info(f"[TRADE][LIVE] Order submitted: {order_id}")

        # Poll for execution status (up to 15 seconds)
        tx_hash = ""
        fill_price = price
        for _ in range(5):
            await asyncio.sleep(3)
            poll = await self._trade_get(
                "/v1/thirdParty/tx/getSwapOrder",
                {"chain": chain, "ids": order_id},
            )
            orders = poll.get("data", [])
            if orders and isinstance(orders, list):
                order = orders[0]
                status = order.get("status", "")
                tx_hash = order.get("txHash", "")
                if order.get("txPriceUsd"):
                    fill_price = float(order["txPriceUsd"])
                if status == "confirmed":
                    logger.info(f"[TRADE][LIVE] ✅ Confirmed tx={tx_hash}")
                    break
                elif status in ("failed", "rejected"):
                    logger.error(f"[TRADE][LIVE] ❌ Order {status}: {order.get('errorMessage','')}")
                    break
                else:
                    logger.info(f"[TRADE][LIVE] Polling... status={status}")

        pos = Position(
            position_id=order_id or uuid.uuid4().hex[:8],
            decision_id=decision.decision_id,
            chain=chain,
            token=decision.signal.token,
            token_symbol=decision.signal.token_symbol,
            action=decision.action,
            amount_usd=decision.amount_usd,
            entry_price=fill_price if fill_price > 0 else price,
            current_price=fill_price if fill_price > 0 else price,
            tp_price=tp,
            sl_price=sl,
            status="open",
            tx_hash=tx_hash,
        )
        decision.executed = True
        decision.execution_result = {
            "order_id": order_id,
            "tx_hash": tx_hash,
            "fill_price": fill_price,
        }

        self._positions[pos.position_id] = pos
        return pos

    async def _get_native_price(self, chain: str) -> float:
        """Get native token (SOL/ETH/BNB) price in USD."""
        native_tokens = {
            "solana": "So11111111111111111111111111111111111111112",
            "eth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "base": "0x4200000000000000000000000000000000000006",
        }
        token = native_tokens.get(chain)
        if not token:
            return 0.0
        try:
            url = f"{V2_BASE}/tokens/{token}-{chain}"
            resp = await async_get(url, data_headers())
            data = resp.json()
            td = data.get("data", {}) or {}
            # Price can be at data.token.current_price_usd or data.current_price_usd
            token_info = td.get("token", {}) or {}
            price = float(token_info.get("current_price_usd", 0) or 0)
            if price == 0.0:
                price = float(td.get("current_price_usd", 0) or 0)
            if price == 0.0:
                # Try from first pair
                pairs = td.get("pairs", [])
                if pairs:
                    p = pairs[0]
                    price = float(p.get("token1_price_usd", p.get("token0_price_usd", 0)) or 0)
            logger.info(f"[TRADE] Native price {chain}: ${price:.2f}")
            return price
        except Exception as e:
            logger.error(f"[TRADE] _get_native_price failed for {chain}: {e}")
            return 0.0

    async def _get_current_price(self, chain: str, token: str) -> float:
        """Get current price using official SDK data endpoint."""
        try:
            url = f"{V2_BASE}/tokens/{token}-{chain}"
            resp = await async_get(url, data_headers())
            data = resp.json()
            td = data.get("data", {}) or {}
            # Check multiple paths: data.current_price_usd, data.token.current_price_usd, data.pairs[0]
            price = float(td.get("current_price_usd", 0) or 0)
            if price == 0.0:
                token_info = td.get("token", {}) or {}
                price = float(token_info.get("current_price_usd", 0) or 0)
            if price == 0.0:
                pairs = td.get("pairs", [])
                if pairs:
                    p = pairs[0]
                    target = p.get("target_token", "")
                    if target.lower() == token.lower():
                        price = float(p.get("token1_price_usd", 0) or 0)
                    if price == 0.0:
                        price = float(p.get("token0_price_usd", 0) or 0)
            if price == 0.0:
                logger.warning(
                    f"[TRADE] Price=0 for {token[:12]}…-{chain}. "
                    f"data_keys={list(td.keys())[:8] if td else 'EMPTY'}"
                )
            return price
        except Exception as e:
            logger.error(f"[TRADE] _get_current_price failed for {token}-{chain}: {e}")
            return 0.0

    async def _get_batch_prices(self, positions: list) -> dict[str, float]:
        """Batch-fetch current prices via /tokens/price for open positions."""
        try:
            token_ids = [f"{p.token}-{p.chain}" for p in positions]
            url = f"{V2_BASE}/tokens/price"
            resp = await async_post(url, {"token_ids": token_ids}, data_headers())
            items = resp.json().get("data", []) or []
            result = {}
            for item in items:
                tid = item.get("token", "")
                chain = item.get("chain", "")
                key = f"{tid}:{chain}"
                price = float(item.get("current_price_usd", item.get("price", 0.0)) or 0.0)
                if price > 0:
                    result[key] = price
            return result
        except Exception as e:
            logger.warning(f"[TRADE] _get_batch_prices failed: {e}")
            return {}

    async def update_positions(self):
        """Polling loop to update open position prices and check TP/SL."""
        open_pos = [p for p in self._positions.values() if p.status == "open"]
        if not open_pos:
            return

        # Batch fetch prices for all open positions
        prices = await self._get_batch_prices(open_pos)

        for pos in open_pos:
            price_key = f"{pos.token}:{pos.chain}"
            price = prices.get(price_key, 0.0)
            if price <= 0:
                # Fallback to single-token endpoint
                price = await self._get_current_price(pos.chain, pos.token)
            if price <= 0:
                continue
            pos.current_price = price
            if pos.entry_price > 0:
                pos.pnl_pct = (price - pos.entry_price) / pos.entry_price
                if pos.action == "sell":
                    pos.pnl_pct = -pos.pnl_pct

            # Check TP/SL
            hit_tp = (pos.action == "buy" and price >= pos.tp_price) or \
                     (pos.action == "sell" and price <= pos.tp_price)
            hit_sl = (pos.action == "buy" and price <= pos.sl_price) or \
                     (pos.action == "sell" and price >= pos.sl_price)

            if hit_tp or hit_sl:
                pos.exit_price = price
                pos.close_time = int(time.time())
                pos.status = "closed"
                reason = "TP" if hit_tp else "SL"
                logger.info(f"[TRADE] Position {pos.position_id} closed [{reason}] "
                            f"PnL={pos.pnl_pct*100:+.2f}%")

    def open_positions(self) -> list[dict]:
        return [
            {
                "id": p.position_id,
                "token": p.token_symbol,
                "chain": p.chain,
                "action": p.action,
                "entry": p.entry_price,
                "current": p.current_price,
                "pnl_pct": round(p.pnl_pct * 100, 2),
                "amount_usd": p.amount_usd,
                "tp": p.tp_price,
                "sl": p.sl_price,
                "status": p.status,
            }
            for p in self._positions.values()
        ]

    def closed_positions(self) -> list[dict]:
        return [
            {
                "id": p.position_id,
                "decision_id": p.decision_id,
                "token": p.token_symbol,
                "chain": p.chain,
                "action": p.action,
                "signal_type": p.signal_type,
                "entry": p.entry_price,
                "exit": p.exit_price,
                "pnl_pct": round(p.pnl_pct * 100, 2),
                "amount_usd": p.amount_usd,
                "status": p.status,
                "close_time": p.close_time,
            }
            for p in self._positions.values()
            if p.status == "closed"
        ]

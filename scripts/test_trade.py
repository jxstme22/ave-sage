"""Quick diagnostic to verify AVE trade API connectivity."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ave-cloud-skill', 'scripts'))

from ave.config import V2_BASE, TRADE_BASE
from ave.headers import data_headers, trade_proxy_headers
from ave.http_async import async_get, async_post

ASSETS_ID = os.environ.get("PROXY_ASSETS_ID", "")
if not ASSETS_ID:
    sys.exit("ERROR: PROXY_ASSETS_ID env var not set. Add it to your .env file.")

# Popular liquid Solana tokens for demo trading
TOKENS = {
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF":  "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "PEPE": "3gWxcrL1KiZp9P6zVgNsiNnF8N3zYw2Vic4usW4ipump",
}


async def get_sol_balance() -> int:
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        rpc_resp = await client.post("https://api.mainnet-beta.solana.com", json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [os.environ.get("PROXY_WALLET_ADDRESS", "")],
        })
        return rpc_resp.json().get("result", {}).get("value", 0)


async def swap(token_addr: str, symbol: str, swap_lamports: int = 3000000) -> dict:
    """Execute a buy swap and return result."""
    body = {
        "chain": "solana",
        "assetsId": ASSETS_ID,
        "inTokenAddress": "sol",
        "outTokenAddress": token_addr,
        "inAmount": str(swap_lamports),
        "swapType": "buy",
        "slippage": "1000",  # 10%
        "useMev": True,
        "gas": "1000000",    # 0.001 SOL
    }
    path = "/v1/thirdParty/tx/sendSwapOrder"
    result = await async_post(
        f"{TRADE_BASE}{path}",
        body,
        trade_proxy_headers("POST", path, body),
    )
    resp = result.json()
    if resp.get("status") in (0, 200) and resp.get("data", {}).get("id"):
        order_id = resp["data"]["id"]
        # Poll for confirmation
        await asyncio.sleep(4)
        poll_path = "/v1/thirdParty/tx/getSwapOrder"
        poll_url = f"{TRADE_BASE}{poll_path}?chain=solana&ids={order_id}"
        poll_r = await async_get(poll_url, trade_proxy_headers("GET", poll_path))
        poll_data = poll_r.json()
        orders = poll_data.get("data", [])
        if orders:
            o = orders[0]
            return {
                "symbol": symbol,
                "order_id": order_id,
                "status": o.get("status"),
                "tx_hash": o.get("txHash", ""),
                "in_lamports": swap_lamports,
                "out_amount": o.get("outAmount", ""),
                "price_usd": o.get("txPriceUsd", ""),
            }
    return {"symbol": symbol, "error": resp.get("msg", str(resp))}


async def main():
    print("=" * 60)
    print("AVE SAGE — Aggressive Trade Test")
    print("=" * 60)

    balance_before = await get_sol_balance()
    print(f"\nBalance BEFORE: {balance_before/1e9:.9f} SOL ({balance_before} lamports)\n")

    # Execute 2 trades: BONK + WIF for demo
    trades = [
        ("BONK", TOKENS["BONK"], 3000000),  # 0.003 SOL each
        ("WIF",  TOKENS["WIF"],  3000000),
    ]

    results = []
    for symbol, addr, lamports in trades:
        print(f"[TRADE] Sending BUY {symbol} ({lamports} lamports)...")
        result = await swap(addr, symbol, lamports)
        results.append(result)
        if result.get("tx_hash"):
            print(f"  ✅ {symbol}: confirmed | tx={result['tx_hash'][:32]}...")
            print(f"     out={result['out_amount']} tokens | price_usd={result['price_usd']}")
        else:
            print(f"  ❌ {symbol}: {result.get('error', 'unknown')}")
        await asyncio.sleep(2)

    balance_after = await get_sol_balance()
    print(f"\nBalance AFTER:  {balance_after/1e9:.9f} SOL ({balance_after} lamports)")
    print(f"Total deducted: {(balance_before - balance_after)/1e9:.9f} SOL")

    print("\n" + "=" * 60)
    print("CONFIRMED TRADES:")
    for r in results:
        if r.get("tx_hash"):
            print(f"  {r['symbol']}: https://solscan.io/tx/{r['tx_hash']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

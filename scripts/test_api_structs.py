"""Debug: check txs and klines API response structure."""
import asyncio
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SDK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ave-cloud-skill", "scripts")
sys.path.insert(0, _SDK)

from ave.config import V2_BASE
from ave.headers import data_headers
from ave.http_async import async_get

async def main():
    token = "EkJuyYyD3to61CHVPJn6wHb7xANxvqApnVJ4o2SdBAGS"
    chain = "solana"
    
    # Klines
    print("=== KLINES ===")
    url = f"{V2_BASE}/klines/token/{token}-{chain}?interval=900&limit=3"
    resp = await async_get(url, data_headers())
    body = resp.json()
    raw = body.get("data", {})
    print(f"data type: {type(raw)}")
    if isinstance(raw, dict):
        print(f"data keys: {raw.keys()}")
        # klines might be nested
        klines = raw.get("klines", raw.get("data", []))
        print(f"klines: {json.dumps(klines[:2], indent=2, default=str)}")
    elif isinstance(raw, list):
        print(f"data length: {len(raw)}")
        print(json.dumps(raw[:2], indent=2, default=str))

    # Transactions
    print("\n=== TRANSACTIONS ===")
    url = f"{V2_BASE}/txs/{token}-{chain}?limit=3"
    resp = await async_get(url, data_headers())
    body = resp.json()
    raw = body.get("data", {})
    print(f"data type: {type(raw)}")
    if isinstance(raw, dict):
        print(f"data keys: {raw.keys()}")
        txs = raw.get("txs", raw.get("transactions", []))
        print(f"txs: {json.dumps(txs[:2], indent=2, default=str)}")
    elif isinstance(raw, list):
        print(f"data length: {len(raw)}")
        print(json.dumps(raw[:2], indent=2, default=str))

    # Contract/risk
    print("\n=== CONTRACT/RISK ===")
    url = f"{V2_BASE}/contracts/{token}-{chain}"
    resp = await async_get(url, data_headers())
    body = resp.json()
    raw = body.get("data", {})
    print(f"data type: {type(raw)}")
    if isinstance(raw, dict):
        print(json.dumps(raw, indent=2, default=str)[:500])

asyncio.run(main())

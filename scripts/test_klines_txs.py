import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ave-cloud-skill", "scripts"))

from ave.config import V2_BASE
from ave.headers import data_headers
from ave.http_async import async_get

async def main():
    url = f"{V2_BASE}/tokens/trending?chain=bsc&page_size=1"
    resp = await async_get(url, data_headers())
    body = resp.json()
    tokens = body.get("data", {}).get("tokens", [])
    if tokens:
        t = tokens[0]
        addr = t.get("token", "")
        sym = t.get("symbol", "?")
        print(f"BSC token: {sym} ({addr})")
        url2 = f"{V2_BASE}/klines/token/{addr}-bsc?interval=900&limit=3"
        resp2 = await async_get(url2, data_headers())
        body2 = resp2.json()
        kd = body2.get("data", [])
        print(f"Klines data type: {type(kd)}, len: {len(kd) if isinstance(kd,list) else 'dict'}")
        if isinstance(kd, list) and kd:
            print(json.dumps(kd[0], indent=2, default=str))
        elif isinstance(kd, dict):
            print(f"Keys: {kd.keys()}")

        # Also check txs for this token
        url3 = f"{V2_BASE}/txs/{addr}-bsc?limit=3"
        resp3 = await async_get(url3, data_headers())
        body3 = resp3.json()
        td = body3.get("data", {})
        print(f"\nTxs data type: {type(td)}")
        if isinstance(td, dict):
            txs = td.get("txs", [])
            print(f"txs count: {len(txs)}")
            if txs:
                print(json.dumps(txs[0], indent=2, default=str))
    else:
        print("No BSC trending tokens")

asyncio.run(main())

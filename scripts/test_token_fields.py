"""Debug: parse the raw token data to see field names."""
import asyncio
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SDK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ave-cloud-skill", "scripts")
sys.path.insert(0, _SDK)

from ave.config import V2_BASE
from ave.headers import data_headers
from ave.http_async import async_get

async def main():
    url = f"{V2_BASE}/tokens/trending?chain=solana&page_size=3"
    resp = await async_get(url, data_headers())
    body = resp.json()
    raw = body.get("data", {})
    print(f"Type of data: {type(raw)}")
    print(f"Keys: {raw.keys() if isinstance(raw, dict) else 'N/A'}")
    
    tokens = raw.get("tokens", []) if isinstance(raw, dict) else raw
    print(f"\nTokens type: {type(tokens)}, count: {len(tokens)}")
    
    if tokens:
        first = tokens[0]
        print(f"\nFirst token keys: {first.keys()}")
        print(json.dumps(first, indent=2, default=str))

asyncio.run(main())

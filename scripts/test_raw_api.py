"""Debug: raw AVE API responses."""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add SDK
_SDK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ave-cloud-skill", "scripts")
sys.path.insert(0, _SDK)

from ave.config import V2_BASE
from ave.headers import data_headers
from ave.http_async import async_get
import json

async def main():
    print(f"V2_BASE = {V2_BASE}")
    headers = data_headers()
    print(f"Headers = {headers}")
    
    for chain in ["solana", "bsc"]:
        print(f"\n--- GET /tokens/trending?chain={chain} ---")
        try:
            url = f"{V2_BASE}/tokens/trending?chain={chain}&page_size=10"
            resp = await async_get(url, headers)
            print(f"Raw response type: {type(resp)}")
            if isinstance(resp, dict):
                print(f"Keys: {resp.keys()}")
                data = resp.get("data", resp)
                print(f"data type: {type(data)}, len: {len(data) if isinstance(data, list) else 'N/A'}")
                print(json.dumps(resp, indent=2, default=str)[:1000])
            else:
                print(f"Response: {str(resp)[:500]}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(main())

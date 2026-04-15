"""Quick check of SAGE endpoints."""
import httpx, json, sys

base = 'http://localhost:8000'

try:
    r = httpx.post(f'{base}/api/scan', timeout=30)
    print("SCAN:", json.dumps(r.json()))
except Exception as e:
    print(f"SCAN ERROR: {e}")

try:
    r = httpx.get(f'{base}/api/decisions?n=10', timeout=10)
    decs = r.json()
    print(f"\nDECISIONS ({len(decs)}):")
    for d in decs[:5]:
        print(f"  {d.get('token')} | {d.get('action')} | conf={d.get('confidence',0):.3f}")
except Exception as e:
    print(f"DECISIONS ERROR: {e}")

try:
    r = httpx.get(f'{base}/api/positions/open', timeout=10)
    print(f"\nOPEN POSITIONS: {len(r.json())}")
    r2 = httpx.get(f'{base}/api/positions/closed', timeout=10)
    print(f"CLOSED POSITIONS: {len(r2.json())}")
except Exception as e:
    print(f"POSITIONS ERROR: {e}")

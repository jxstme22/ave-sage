"""Test the scan endpoint + check if events flow through the pipeline."""
import httpx
import json
import time

BASE = "http://127.0.0.1:8000"

print("=== PRE-SCAN STATE ===")
with httpx.Client(timeout=10.0) as c:
    r = c.get(f"{BASE}/api/memory/stats")
    print(f"Memory chunks: {r.json()}")
    r = c.get(f"{BASE}/api/decisions?n=5")
    print(f"Decisions: {r.json()}")
    r = c.get(f"{BASE}/api/rules/status")
    print(f"Rules: {r.json()}")

print("\n=== TRIGGERING SCAN ===")
with httpx.Client(timeout=300.0) as c:
    start = time.time()
    r = c.post(f"{BASE}/api/scan", json={})
    elapsed = time.time() - start
    print(f"Scan response ({elapsed:.1f}s): {r.status_code}")
    print(json.dumps(r.json(), indent=2))

print("\n=== POST-SCAN STATE (waiting 10s for pipeline) ===")
time.sleep(10)
with httpx.Client(timeout=10.0) as c:
    r = c.get(f"{BASE}/api/memory/stats")
    print(f"Memory chunks: {r.json()}")
    r = c.get(f"{BASE}/api/decisions?n=5")
    decisions = r.json()
    print(f"Decisions count: {len(decisions)}")
    for d in decisions[:5]:
        print(f"  {d.get('action','?').upper()} {d.get('token','?')} conf={d.get('confidence',0):.2f} — {d.get('reasoning','')[:80]}")
    r = c.get(f"{BASE}/api/positions/open")
    print(f"Open positions: {r.json()}")

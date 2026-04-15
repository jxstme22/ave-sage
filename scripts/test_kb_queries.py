"""Verify KB queries return seeded strategies."""
import httpx
import json

BASE = "http://127.0.0.1:8000"

tests = [
    ("Memory stats", "GET", "/api/memory/stats", None),
    ("Query: volume breakout", "GET", "/api/memory/query?q=volume+breakout+solana&n=3", None),
    ("Query: risk management", "GET", "/api/memory/query?q=risk+management+stop+loss&n=3", None),
    ("Query: whale accumulation", "GET", "/api/memory/query?q=whale+buy+accumulation&n=3", None),
    ("Ask: best strategy", "GET", "/api/sage/ask?q=What+is+the+best+strategy+for+Solana+tokens", None),
    ("KB health", "GET", "/api/memory/health", None),
]

with httpx.Client(timeout=60.0) as c:
    for name, method, path, body in tests:
        try:
            r = c.get(f"{BASE}{path}") if method == "GET" else c.post(f"{BASE}{path}", json=body or {})
            print(f"--- {name} ({r.status_code}) ---")
            data = r.json()
            print(json.dumps(data, indent=2)[:500])
            print()
        except Exception as e:
            print(f"--- {name} FAILED ---")
            print(f"  {e}")
            print()

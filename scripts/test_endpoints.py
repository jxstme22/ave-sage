"""Quick smoke test of all SAGE API endpoints."""
import httpx
import json
import sys
import time

BASE = "http://127.0.0.1:8000"

endpoints = [
    ("GET", "/health"),
    ("GET", "/api/memory/stats"),
    ("GET", "/api/memory/recent?chain=solana&hours=24"),
    ("GET", "/api/memory/query?q=solana+volume&n=3"),
    ("GET", "/api/memory/health"),
    ("GET", "/api/decisions?n=5"),
    ("GET", "/api/positions/open"),
    ("GET", "/api/positions/closed"),
    ("GET", "/api/feedback/stats"),
    ("GET", "/api/rules/status"),
    ("GET", "/api/strategy/ledger"),
    ("GET", "/api/strategy/tune"),
    ("GET", "/api/sage/ask?q=What+is+SAGE"),
    ("POST", "/api/scan"),
]

passed = 0
failed = 0

with httpx.Client(timeout=60.0) as c:
    for method, path in endpoints:
        try:
            if method == "GET":
                r = c.get(f"{BASE}{path}")
            else:
                r = c.post(f"{BASE}{path}", json={})
            status = r.status_code
            body = r.text[:300]
            icon = "PASS" if status < 400 else "FAIL"
            if status < 400:
                passed += 1
            else:
                failed += 1
            print(f"[{icon}] {method} {path}")
            print(f"  Status: {status}")
            print(f"  Body: {body}")
            print()
        except Exception as e:
            failed += 1
            print(f"[FAIL] {method} {path}")
            print(f"  Error: {e}")
            print()

print(f"{'='*60}")
print(f"Results: {passed} passed, {failed} failed out of {len(endpoints)}")

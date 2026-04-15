"""Final validation: check all endpoints and system state."""
import httpx

BASE = "http://127.0.0.1:8000"

endpoints = [
    ("GET", "/api/health"),
    ("GET", "/api/status"),
    ("GET", "/api/decisions?n=10"),
    ("GET", "/api/positions/open"),
    ("GET", "/api/positions/closed"),
    ("GET", "/api/memory/stats"),
    ("GET", "/api/memory/health"),
    ("GET", "/api/memory/recent?n=5"),
    ("GET", "/api/feedback/stats"),
    ("GET", "/api/memory/query?q=risk+management&n=3"),
]

print("=== Endpoint Health ===")
for method, path in endpoints:
    r = httpx.get(f"{BASE}{path}")
    print(f"  {r.status_code} {method} {path}")

r = httpx.get(f"{BASE}/api/decisions?n=20")
decisions = r.json()
print(f"\n=== Decisions ({len(decisions)} total) ===")
actions = {}
for d in decisions:
    a = d.get("action", "?")
    actions[a] = actions.get(a, 0) + 1
    reasoning = d.get("reasoning", "")[:100]
    print(f"  {a.upper():6s} {d.get('token','?'):10s} conf={d.get('confidence',0):.2f}  {reasoning}")
print(f"  Action breakdown: {actions}")

r = httpx.get(f"{BASE}/api/memory/stats")
print(f"\n=== Knowledge Base ===")
print(f"  {r.json()}")

r = httpx.get(f"{BASE}/api/positions/open")
print(f"\n=== Open Positions: {len(r.json())} ===")
for p in r.json():
    print(f"  {p}")

r = httpx.get(f"{BASE}/api/positions/closed")
print(f"\n=== Closed Positions: {len(r.json())} ===")
for p in r.json():
    print(f"  {p}")

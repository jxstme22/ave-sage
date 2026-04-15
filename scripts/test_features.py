"""Test all 4 new features."""
import httpx
import json

BASE = "http://localhost:8000"

# Test 1: Sage Chat
print("=== Test 1: Sage Chat ===")
try:
    r = httpx.get(f"{BASE}/api/sage/ask", params={"q": "What tokens are trending right now?"}, timeout=30)
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Has answer: {'answer' in data}")
    print(f"Chunks used: {data.get('chunks_used', 'N/A')}")
    answer = data.get("answer", "N/A")
    print(f"Answer preview: {answer[:400]}")
except Exception as e:
    print(f"ERROR: {e}")
print()

# Test 2: Wallet Balance
print("=== Test 2: Wallet Balance ===")
try:
    r2 = httpx.get(f"{BASE}/api/wallet/balance", timeout=15)
    data2 = r2.json()
    print(f"Status: {r2.status_code}")
    print(json.dumps(data2, indent=2))
except Exception as e:
    print(f"ERROR: {e}")
print()

# Test 3: Memory Recent (significance)
print("=== Test 3: Memory Recent (significance) ===")
try:
    r3 = httpx.get(f"{BASE}/api/memory/recent", params={"n": "3"}, timeout=10)
    data3 = r3.json()
    for item in data3[:3]:
        sig = item.get("significance", "MISSING")
        meta_sig = item.get("metadata", {}).get("significance", "MISSING")
        print(f"  chunk significance={sig}  metadata.significance={meta_sig}")
except Exception as e:
    print(f"ERROR: {e}")
print()

# Test 4: Recent Decisions
print("=== Test 4: Recent Decisions ===")
try:
    r4 = httpx.get(f"{BASE}/api/decisions", params={"n": "10"}, timeout=10)
    data4 = r4.json()
    for d in data4[:5]:
        print(f"  {d['action'].upper()} {d['token']} conf={d['confidence']:.2f}: {d['reasoning'][:120]}")
except Exception as e:
    print(f"ERROR: {e}")

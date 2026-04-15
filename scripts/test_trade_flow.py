"""Test trade flow: simulate a buy decision going through the pipeline."""
import httpx
import json

BASE = "http://127.0.0.1:8000"

# Seed positive outcome into KB so SAGE has positive history to reference
print("=== Seeding positive history ===")
r = httpx.post(f"{BASE}/api/memory/upsert", json={
    "chunk_type": "outcome_event",
    "chain": "solana",
    "token_symbol": "BONK",
    "rag_text": "BONK trending_entry signal resulted in +12% gain. Bought at $0.00001, sold at TP for $0.0000112. Volume was 3x average. Win.",
    "metadata": {"source": "seed", "category": "outcome", "result": "win", "pnl_pct": 12}
})
print(f"Seed 1: {r.status_code}")

r = httpx.post(f"{BASE}/api/memory/upsert", json={
    "chunk_type": "outcome_event",
    "chain": "solana", 
    "token_symbol": "WIF",
    "rag_text": "WIF trending_entry signal with rank #2 resulted in +8% gain within 4 hours. Strong momentum confirmed. Win.",
    "metadata": {"source": "seed", "category": "outcome", "result": "win", "pnl_pct": 8}
})
print(f"Seed 2: {r.status_code}")

r = httpx.post(f"{BASE}/api/memory/upsert", json={
    "chunk_type": "outcome_event",
    "chain": "solana",
    "token_symbol": "POPCAT", 
    "rag_text": "POPCAT trending_entry signal rank #1 resulted in +15% gain. Low risk token with strong community. Win.",
    "metadata": {"source": "seed", "category": "outcome", "result": "win", "pnl_pct": 15}
})
print(f"Seed 3: {r.status_code}")

# Check current state
print("\n=== Current State ===")
r = httpx.get(f"{BASE}/api/memory/stats")
print(f"Memory: {r.json()}")

r = httpx.get(f"{BASE}/api/decisions?n=5")
print(f"\nLatest decisions: {len(r.json())}")
for d in r.json()[:5]:
    print(f"  {d.get('action','?').upper():6s} {d.get('token','?'):10s} conf={d.get('confidence',0):.2f} {d.get('reasoning','')[:80]}")

r = httpx.get(f"{BASE}/api/positions/open")
print(f"\nOpen positions: {r.json()}")

r = httpx.get(f"{BASE}/api/positions/closed")
print(f"Closed positions: {r.json()}")

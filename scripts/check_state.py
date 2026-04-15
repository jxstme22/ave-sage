"""Check current decisions and stats."""
import httpx
r = httpx.get('http://127.0.0.1:8000/api/decisions?n=20')
decisions = r.json()
print(f'Total decisions: {len(decisions)}')
for d in decisions[:10]:
    print(f'  {d.get("action","?").upper():6s} {d.get("token","?"):10s} conf={d.get("confidence",0):.2f} {d.get("reasoning","")[:80]}')

r2 = httpx.get('http://127.0.0.1:8000/api/memory/stats')
print(f'\nMemory: {r2.json()}')

r3 = httpx.get('http://127.0.0.1:8000/api/positions/open')
print(f'Open positions: {r3.json()}')

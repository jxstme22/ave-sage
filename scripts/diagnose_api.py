"""Diagnose AVE API price fields and trade agent issues."""
import sys
sys.path.insert(0, 'ave-cloud-skill/scripts')

import json
import httpx
from ave.config import V2_BASE, TRADE_BASE
from ave.headers import data_headers, trade_proxy_headers

print("=== Trending tokens / price fields ===")
r = httpx.get(f'{V2_BASE}/tokens/trending', params={'chain': 'solana', 'page_size': 3}, headers=data_headers(), timeout=10)
d = r.json()
raw = d.get('data', {})
tokens = raw.get('tokens', []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

if tokens:
    t = tokens[0]
    addr = t.get('token', t.get('address', ''))
    print(f"Token: {t.get('symbol', '?')} - {addr}")
    print("All fields:")
    for k, v in t.items():
        print(f"  {k}: {v}")

    print(f"\n=== Single token endpoint: /tokens/{addr}-solana ===")
    r2 = httpx.get(f'{V2_BASE}/tokens/{addr}-solana', headers=data_headers(), timeout=10)
    d2 = r2.json()
    td = d2.get('data', {})
    if td:
        print("Price-related fields:")
        for k, v in td.items():
            if 'price' in k.lower():
                print(f"  {k}: {v}")
    else:
        print("EMPTY data, status:", d2.get('status'), d2.get('msg'))
else:
    print("No tokens returned")

print("\n=== AVE Trade API - check wallet ===")
import hashlib, hmac, base64, datetime
from config import settings
api_key = settings.ave.api_key
secret_key = settings.ave.secret_key
path = "/v1/thirdParty/user/getUserByAssetsId"
ts = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
msg = ts + "GET" + path
h = hmac.new(secret_key.encode(), msg.encode(), hashlib.sha256)
sig = base64.b64encode(h.digest()).decode()
headers = {
    "AVE-ACCESS-KEY": api_key,
    "AVE-ACCESS-TIMESTAMP": ts,
    "AVE-ACCESS-SIGN": sig,
    "Content-Type": "application/json",
}
r3 = httpx.get(f"{TRADE_BASE}{path}?assetsIds={settings.agent.assets_id}", headers=headers, timeout=10)
d3 = r3.json()
print(f"Status: {d3.get('status')}, msg: {d3.get('msg', 'ok')}")
data3 = d3.get('data', [])
if data3:
    walletinfo = data3[0]
    print("Wallet info keys:", list(walletinfo.keys()))
    print("Wallet name:", walletinfo.get('assetsName'))
    addrs = {a['chain']: a['address'] for a in walletinfo.get('addressList', [])}
    print("Addresses:", addrs)

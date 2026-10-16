"""
Test Alpaca API with correct date format and check results.
"""
import requests
import json
from datetime import datetime, timedelta

API_KEY = "PKK6KU4V22JYLQJHI27GRRHRTG"
API_SECRET = "5f8yafADd55H1oX4dNxa122QRcz3SQG6Q7UwNUSUqot"

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
    "Accept": "application/json"
}

BASE_URL = "https://data.alpaca.markets/v2/stocks"

END_DATE = datetime(2026, 10, 17)
START_DATE = END_DATE - timedelta(days=365)

# Test 1: Latest bars with IEX feed - check what we get
print("Test 1: Latest bars with IEX feed, limit=100")
params = {
    "symbols": "NVDA",
    "timeframe": "1Day",
    "adjustment": "all",
    "limit": 100,
    "feed": "iex"
}
resp = requests.get(f"{BASE_URL}/bars", headers=HEADERS, params=params)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    bars = data.get('bars', {}).get('NVDA', [])
    print(f"  Got {len(bars)} bars")
    if bars:
        print(f"  First bar: {bars[0]}")
        print(f"  Last bar: {bars[-1]}")
else:
    print(f"  Error: {resp.text[:300]}")

print()

# Test 2: Latest bars with SIP feed
print("Test 2: Latest bars with SIP feed, limit=100")
params = {
    "symbols": "NVDA",
    "timeframe": "1Day",
    "adjustment": "all",
    "limit": 100,
    "feed": "sip"
}
resp = requests.get(f"{BASE_URL}/bars", headers=HEADERS, params=params)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    bars = data.get('bars', {}).get('NVDA', [])
    print(f"  Got {len(bars)} bars")
    if bars:
        print(f"  First bar: {bars[0]}")
        print(f"  Last bar: {bars[-1]}")
else:
    print(f"  Error: {resp.text[:300]}")

print()

# Test 3: Date-only format (YYYY-MM-DD)
print("Test 3: Date-only format with IEX feed")
params = {
    "symbols": "NVDA",
    "start": "2025-10-17",
    "end": "2026-10-17",
    "timeframe": "1Day",
    "adjustment": "all",
    "limit": 5000,
    "feed": "iex"
}
resp = requests.get(f"{BASE_URL}/bars", headers=HEADERS, params=params)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    bars = data.get('bars', {}).get('NVDA', [])
    print(f"  Got {len(bars)} bars")
    if bars:
        print(f"  First bar date: {bars[0].get('t')}")
        print(f"  Last bar date: {bars[-1].get('t')}")
else:
    print(f"  Error: {resp.text[:300]}")

print()

# Test 4: Date-only format with SIP feed
print("Test 4: Date-only format with SIP feed")
params = {
    "symbols": "NVDA",
    "start": "2025-10-17",
    "end": "2026-10-17",
    "timeframe": "1Day",
    "adjustment": "all",
    "limit": 5000,
    "feed": "sip"
}
resp = requests.get(f"{BASE_URL}/bars", headers=HEADERS, params=params)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    bars = data.get('bars', {}).get('NVDA', [])
    print(f"  Got {len(bars)} bars")
    if bars:
        print(f"  First bar date: {bars[0].get('t')}")
        print(f"  Last bar date: {bars[-1].get('t')}")
else:
    print(f"  Error: {resp.text[:300]}")

print()

# Test 5: Check account info
print("Test 5: Account info")
resp = requests.get("https://api.alpaca.markets/v2/account", headers=HEADERS)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"  Account status: {data.get('status')}")
    print(f"  Crypto: {data.get('crypto')}")
    print(f"  Currency: {data.get('currency')}")
else:
    print(f"  Error: {resp.text[:300]}")

print()

# Test 6: Check data subscription
print("Test 6: Data subscription info")
resp = requests.get("https://api.alpaca.markets/v2/account/configurations", headers=HEADERS)
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"  Config: {resp.json()}")
else:
    print(f"  Error: {resp.text[:300]}")

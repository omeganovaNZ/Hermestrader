"""
Fetch historical price data from Alpaca using direct REST API calls.
Try different approaches to work around subscription limitations.
"""
import requests
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

API_KEY = "PKK6KU4V22JYLQJHI27GRRHRTG"
API_SECRET = "5f8yafADd55H1oX4dNxa122QRcz3SQG6Q7UwNUSUqot"

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
    "Accept": "application/json"
}

TICKERS = [
    "NVDA", "TSLA", "MU", "AMD", "GOOGL", "AAPL", "MSFT", "AMZN", "META",
    "LLY", "JPM", "XOM", "CRWD", "PLTR", "RKLB", "GEV", "BE", "IREN",
    "QBTS", "RGTI"
]

BASE_URL = "https://data.alpaca.markets/v2/stocks"

def fetch_bars_rest(ticker, start, end, limit=10000):
    """Fetch bars using direct REST API."""
    params = {
        "symbols": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timeframe": "1Day",
        "adjustment": "all",
        "limit": limit,
        "feed": "sip"  # Try SIP feed
    }
    
    url = f"{BASE_URL}/bars"
    resp = requests.get(url, headers=HEADERS, params=params)
    print(f"  {ticker}: Status {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:200]}")
        return None
    return resp.json()

def fetch_bars_iex(ticker, start, end, limit=10000):
    """Try IEX feed instead of SIP."""
    params = {
        "symbols": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timeframe": "1Day",
        "adjustment": "all",
        "limit": limit,
        "feed": "iex"
    }
    
    url = f"{BASE_URL}/bars"
    resp = requests.get(url, headers=HEADERS, params=params)
    print(f"  {ticker} (IEX): Status {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:200]}")
        return None
    return resp.json()

def fetch_latest_bars(ticker, limit=500):
    """Fetch latest bars without specifying date range."""
    params = {
        "symbols": ticker,
        "timeframe": "1Day",
        "adjustment": "all",
        "limit": limit,
        "feed": "iex",
        "sort": "desc"
    }
    
    url = f"{BASE_URL}/bars"
    resp = requests.get(url, headers=HEADERS, params=params)
    print(f"  {ticker} (latest IEX): Status {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:200]}")
        return None
    return resp.json()

def fetch_with_feed_sip(ticker, start, end, limit=10000):
    """Try SIP feed."""
    params = {
        "symbols": ticker,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timeframe": "1Day",
        "adjustment": "all",
        "limit": limit,
        "feed": "sip"
    }
    
    url = f"{BASE_URL}/bars"
    resp = requests.get(url, headers=HEADERS, params=params)
    print(f"  {ticker} (SIP): Status {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text[:200]}")
        return None
    return resp.json()

# Test with NVDA first
print("Testing different API approaches with NVDA...")
print()

END_DATE = datetime(2026, 10, 17)
START_DATE = END_DATE - timedelta(days=365)

# Approach 1: SIP feed with date range
print("Approach 1: SIP feed with date range")
result = fetch_with_feed_sip("NVDA", START_DATE, END_DATE)
print()

# Approach 2: IEX feed with date range
print("Approach 2: IEX feed with date range")
result = fetch_bars_iex("NVDA", START_DATE, END_DATE)
print()

# Approach 3: Latest bars without date range
print("Approach 3: Latest bars without date range")
result = fetch_latest_bars("NVDA", limit=500)
print()

# Approach 4: Try with shorter date range (last 30 days)
print("Approach 4: Shorter date range (last 30 days)")
short_start = END_DATE - timedelta(days=30)
result = fetch_bars_iex("NVDA", short_start, END_DATE)
print()

# Approach 5: Try with even shorter range (last 7 days)
print("Approach 5: Even shorter date range (last 7 days)")
short_start = END_DATE - timedelta(days=7)
result = fetch_bars_iex("NVDA", short_start, END_DATE)
print()

# Approach 6: Try with just a limit parameter (no dates)
print("Approach 6: Just limit parameter, no dates")
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
    print(f"  Success! Got {len(data.get('bars', {}).get('NVDA', []))} bars")
else:
    print(f"  Error: {resp.text[:200]}")

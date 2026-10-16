"""Verify data quality and validate suspicious results."""
import requests
import pandas as pd
from datetime import datetime

# Credentials are read from alpaca_config.txt -- never hardcode secrets here.
def _load_alpaca_creds():
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alpaca_config.txt")
    creds = {}
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("API_KEY="):
                creds["API_KEY"] = line.split("=", 1)[1]
            elif line.startswith("API_SECRET="):
                creds["API_SECRET"] = line.split("=", 1)[1]
    if not creds.get("API_KEY") or not creds.get("API_SECRET"):
        raise ValueError("Could not read API credentials from alpaca_config.txt")
    return creds["API_KEY"], creds["API_SECRET"]


API_KEY, API_SECRET = _load_alpaca_creds()
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
    "Accept": "application/json"
}

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

def fetch_bars_iex(ticker, start="2025-10-01", end="2026-10-17"):
    """Fetch daily bars."""
    all_bars = []
    page_token = None
    while True:
        params = {
            "symbols": ticker,
            "start": start,
            "end": end,
            "timeframe": "1Day",
            "adjustment": "all",
            "limit": 5000,
            "feed": "iex"
        }
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(BASE_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            break
        data = resp.json()
        bars = data.get("bars", {}).get(ticker, [])
        all_bars.extend(bars)
        page_token = data.get("next_page_token")
        if not page_token:
            break
    if not all_bars:
        return None
    df = pd.DataFrame(all_bars)
    df['timestamp'] = pd.to_datetime(df['t'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    return df

# Check stocks with extreme moves for split detection
print("=== Checking for stock splits (extreme price jumps) ===\n")

extreme_tickers = ["CRWD", "MU", "BE", "LLY", "XOM", "NVDA", "AMD", "AAPL", "GOOGL"]

for ticker in extreme_tickers:
    df = fetch_bars_iex(ticker)
    if df is None:
        print(f"{ticker}: No data")
        continue
    
    df['prev_close'] = df['close'].shift(1)
    df['pct_change'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
    
    # Find days with > 20% moves (potential splits)
    big_moves = df[df['pct_change'].abs() > 20].copy()
    
    print(f"{ticker}:")
    if not big_moves.empty:
        for _, row in big_moves.iterrows():
            print(f"  {row['timestamp'].date()}: {row['pct_change']:.2f}% move (close: {row['close']:.2f})")
    else:
        print(f"  No single-day moves > 20%")
    
    # Show first and last few prices
    print(f"  First bar: {df.iloc[0]['timestamp'].date()} close={df.iloc[0]['close']:.2f}")
    print(f"  Last bar: {df.iloc[-1]['timestamp'].date()} close={df.iloc[-1]['close']:.2f}")
    
    # Check for any gaps > 30% that might indicate splits
    splits_detected = []
    for i in range(1, len(df)):
        prev_c = df.iloc[i-1]['close']
        curr_c = df.iloc[i]['close']
        if prev_c > 0:
            ratio = curr_c / prev_c
            if ratio > 1.5 or ratio < 0.67:  # 50%+ gap
                splits_detected.append({
                    'date': df.iloc[i]['timestamp'].date(),
                    'prev_close': prev_c,
                    'curr_close': curr_c,
                    'ratio': ratio
                })
    
    if splits_detected:
        print(f"  *** POTENTIAL SPLITS DETECTED ***")
        for s in splits_detected:
            print(f"    {s['date']}: {s['prev_close']:.2f} -> {s['curr_close']:.2f} (ratio: {s['ratio']:.2f})")
    print()

# Also verify IEX feed data against known prices
print("\n=== Data verification ===")
print("Checking if IEX data matches expected prices...")

# Check a few known reference points
checks = [
    ("NVDA", "2025-10-15", 179.44),  # Starting price from our results
    ("AAPL", "2025-10-15", 248.49),
    ("MSFT", "2025-10-15", 509.32),
]

for ticker, date, expected in checks:
    df = fetch_bars_iex(ticker, start=date, end=date)
    if df is not None and len(df) > 0:
        actual = df.iloc[0]['close']
        match = "OK" if abs(actual - expected) < 0.01 else f"MISMATCH (got {actual})"
        print(f"  {ticker} on {date}: expected {expected}, got {actual} - {match}")
    else:
        print(f"  {ticker} on {date}: No data")

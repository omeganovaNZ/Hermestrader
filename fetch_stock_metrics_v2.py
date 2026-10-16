"""
Fetch historical price data from Alpaca (IEX feed) and calculate technical indicators.
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

BASE_URL = "https://data.alpaca.markets/v2/stocks/bars"

# Date range: last 1 year
END_DATE = "2026-10-17"
START_DATE = "2025-10-01"  # Start earlier to ensure we capture Oct 15, 2025

# Target dates for price comparison
TARGET_START = "2025-10-15"
TARGET_END = "2026-10-15"

def fetch_bars_iex(ticker):
    """Fetch daily bars using IEX feed with pagination."""
    all_bars = []
    page_token = None
    
    while True:
        params = {
            "symbols": ticker,
            "start": START_DATE,
            "end": END_DATE,
            "timeframe": "1Day",
            "adjustment": "all",
            "limit": 5000,
            "feed": "iex"
        }
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(BASE_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"  Error: {resp.text[:200]}")
            break
        
        data = resp.json()
        bars = data.get("bars", {}).get(ticker, [])
        all_bars.extend(bars)
        
        page_token = data.get("next_page_token")
        if not page_token:
            break
    
    if not all_bars:
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(all_bars)
    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['t'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Rename columns for clarity
    df = df.rename(columns={
        'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'
    })
    
    return df

def calculate_rsi(prices, period=14):
    """Calculate RSI using Wilder's method."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_adx(df, period=14):
    """Calculate ADX using Wilder's method."""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    if len(close) < period * 2:
        return None
    
    # True Range
    tr = np.zeros(len(close))
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    
    # +DM and -DM
    plus_dm = np.zeros(len(close))
    minus_dm = np.zeros(len(close))
    for i in range(1, len(close)):
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0
    
    # Smoothed TR, +DM, -DM
    atr = np.zeros(len(close))
    smoothed_plus = np.zeros(len(close))
    smoothed_minus = np.zeros(len(close))
    
    atr[period-1] = np.mean(tr[:period])
    smoothed_plus[period-1] = np.mean(plus_dm[:period])
    smoothed_minus[period-1] = np.mean(minus_dm[:period])
    
    for i in range(period, len(close)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        smoothed_plus[i] = (smoothed_plus[i-1] * (period - 1) + plus_dm[i]) / period
        smoothed_minus[i] = (smoothed_minus[i-1] * (period - 1) + minus_dm[i]) / period
    
    # +DI and -DI
    plus_di = np.zeros(len(close))
    minus_di = np.zeros(len(close))
    for i in range(period, len(close)):
        if atr[i] > 0:
            plus_di[i] = 100 * smoothed_plus[i] / atr[i]
            minus_di[i] = 100 * smoothed_minus[i] / atr[i]
    
    # DX and ADX
    dx = np.zeros(len(close))
    for i in range(period, len(close)):
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum
    
    adx_values = np.zeros(len(close))
    adx_start = period * 2 - 1
    if adx_start < len(close):
        adx_values[adx_start] = np.mean(dx[period:adx_start+1])
        for i in range(adx_start + 1, len(close)):
            adx_values[i] = (adx_values[i-1] * (period - 1) + dx[i]) / period
    
    return adx_values[-1] if adx_values[-1] > 0 else None

def calculate_max_drawdown(prices):
    """Calculate maximum drawdown."""
    peak = prices[0]
    max_dd = 0
    for price in prices:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd

def calculate_sharpe(returns, risk_free_rate=0.04):
    """Calculate annualized Sharpe ratio."""
    if len(returns) < 2:
        return None
    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf
    std = np.std(excess_returns, ddof=1)
    if std == 0:
        return 0.0
    sharpe = np.mean(excess_returns) / std * np.sqrt(252)
    return sharpe

def get_closest_price(df, target_date):
    """Get the closing price on or closest to target_date."""
    target_ts = pd.Timestamp(target_date, tz='UTC')
    df['diff'] = (df['timestamp'] - target_ts).abs()
    closest_idx = df['diff'].idxmin()
    return df.loc[closest_idx, 'close'], df.loc[closest_idx, 'timestamp']

def calculate_bollinger_position(df, period=20, num_std=2):
    """Calculate position within Bollinger Bands (0=lower, 1=upper, 0.5=middle)."""
    if len(df) < period:
        return None
    recent = df.tail(period)
    sma = recent['close'].mean()
    std = recent['close'].std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    current = df.iloc[-1]['close']
    if upper == lower:
        return 0.5
    position = (current - lower) / (upper - lower)
    return position

def process_ticker(ticker):
    """Process a single ticker and return metrics."""
    print(f"Fetching {ticker}...", end=" ", flush=True)
    df = fetch_bars_iex(ticker)
    if df is None or df.empty:
        return {"ticker": ticker, "error": "No data available"}
    
    # Ensure we have enough data
    if len(df) < 20:
        return {"ticker": ticker, "error": f"Insufficient data ({len(df)} bars)"}
    
    # 1. Price on Oct 15, 2025 (or closest)
    price_start, date_start = get_closest_price(df, TARGET_START)
    
    # 2. Price on Oct 15, 2026 (or closest)
    price_end, date_end = get_closest_price(df, TARGET_END)
    
    # 3. Percentage gain
    pct_gain = (price_end - price_start) / price_start * 100
    
    # 4. Current ADX
    adx = calculate_adx(df)
    
    # 5. Current RSI
    rsi = calculate_rsi(df['close'].values)
    
    # 6. Distance from 50-day and 200-day moving averages
    current_price = df.iloc[-1]['close']
    ma50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else None
    ma200 = df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else None
    
    dist_ma50 = ((current_price - ma50) / ma50 * 100) if ma50 and not np.isnan(ma50) else None
    dist_ma200 = ((current_price - ma200) / ma200 * 100) if ma200 and not np.isnan(ma200) else None
    
    # 7. Bollinger Band position
    bb_position = calculate_bollinger_position(df)
    
    # 8. Maximum drawdown
    max_dd = calculate_max_drawdown(df['close'].values)
    
    # 9. Sharpe ratio
    returns = df['close'].pct_change().dropna().values
    sharpe = calculate_sharpe(returns)
    
    print(f"OK ({len(df)} bars)")
    
    return {
        "ticker": ticker,
        "price_oct15_2025": round(price_start, 2),
        "date_start": str(date_start.date()),
        "price_oct15_2026": round(price_end, 2),
        "date_end": str(date_end.date()),
        "pct_gain": round(pct_gain, 2),
        "current_price": round(current_price, 2),
        "adx": round(adx, 2) if adx else None,
        "rsi": round(rsi, 2) if rsi else None,
        "dist_ma50_pct": round(dist_ma50, 2) if dist_ma50 is not None else None,
        "dist_ma200_pct": round(dist_ma200, 2) if dist_ma200 is not None else None,
        "bb_position": round(bb_position, 4) if bb_position is not None else None,
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "num_bars": len(df)
    }

# Process all tickers
results = []
for ticker in TICKERS:
    try:
        result = process_ticker(ticker)
        results.append(result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        results.append({"ticker": ticker, "error": str(e)})

# Save results to JSON
with open("stock_metrics.json", "w") as f:
    json.dump(results, f, indent=2)

# Print summary table
print("\n" + "="*130)
print(f"{'Ticker':<8} {'Price 10/15/25':>14} {'Price 10/15/26':>14} {'Gain%':>8} {'ADX':>6} {'RSI':>6} {'vs MA50%':>9} {'vs MA200%':>10} {'BB Pos':>7} {'MaxDD%':>8} {'Sharpe':>7}")
print("="*130)

for r in results:
    if "error" in r:
        print(f"{r['ticker']:<8} ERROR: {r['error']}")
    else:
        adx_str = f"{r['adx']:.1f}" if r['adx'] else "N/A"
        rsi_str = f"{r['rsi']:.1f}" if r['rsi'] else "N/A"
        ma50_str = f"{r['dist_ma50_pct']:.2f}" if r['dist_ma50_pct'] is not None else "N/A"
        ma200_str = f"{r['dist_ma200_pct']:.2f}" if r['dist_ma200_pct'] is not None else "N/A"
        bb_str = f"{r['bb_position']:.4f}" if r['bb_position'] is not None else "N/A"
        sharpe_str = f"{r['sharpe']:.3f}" if r['sharpe'] is not None else "N/A"
        
        print(f"{r['ticker']:<8} {r['price_oct15_2025']:>14.2f} {r['price_oct15_2026']:>14.2f} {r['pct_gain']:>8.2f} {adx_str:>6} {rsi_str:>6} {ma50_str:>9} {ma200_str:>10} {bb_str:>7} {r['max_drawdown']:>8.2f} {sharpe_str:>7}")

print("="*130)
print(f"\nResults saved to stock_metrics.json")

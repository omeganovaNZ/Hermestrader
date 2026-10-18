"""
Pattern-Match Watchlist Generator

Compares current Alpaca holdings' technical profiles from exactly 2 years ago
against today's market to find stocks with similar setups.

Output: data/pattern_match_results.json
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os

# Ensure data/ directory exists
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Current Alpaca holdings
CURRENT_HOLDINGS = {
    "MRVL": "Marvell Technology",
    "RKLB": "Rocket Lab",
    "MU": "Micron",
    "DDOG": "Datadog",
    "LLY": "Eli Lilly",
    "BE": "Bloom Energy",
    "AMD": "AMD",
    "PK": "Park Hotels",
}

# Broader universe to screen today
CURRENT_UNIVERSE = [
    # Mega-cap tech
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    # Semiconductors
    "AVGO", "TSM", "ASML", "LRCX", "AMAT", "KLAC", "SNPS", "CDNS", "MXL", "ALAB",
    # AI / Cloud
    "CRWD", "PANW", "OKTA", "SNOW", "MDB", "NET", "PLTR", "AI", "SMCI", "DDOG",
    # Biotech / Healthcare
    "LLY", "MRNA", "VRTX", "IOVA", "KOD", "TXG", "REGN", "BIIB", "INCY", "EXAS",
    # Energy / Power
    "XOM", "CVX", "NEE", "GEV", "CAT", "BE", "ENPH", "FSLR", "LNG",
    # Space
    "RKLB", "ASTS", "LUNR",
    # Financials
    "JPM", "GS", "BAC", "MS", "AXP",
    # Consumer / Other
    "HD", "LOW", "NKE", "MCD", "SBUX", "TGT", "WMT",
    # Growth / Momentum
    "COIN", "HOOD", "SHOP", "SQ", "PYPL", "ABNB", "UBER", "LYFT",
    "CRM", "ORCL", "NOW", "TEAM", "WDAY", "CRAD", "HUBS",
    "PSTG", "GDDY", "YELP", "DUOL", "RBLX", "U", "RDDT",
    # More tech
    "INTC", "MU", "STX", "WDC", "DELL", "HPQ", "HPE", "IBM",
    "ORCL", "ADBE", "INTU", "AMD", "QLYS", "KVYO", "GTLB",
    "PATH", "AI", "RBRK", "KBR", "LDOS", "NOC", "RTX",
    # Newer names
    "IONQ", "RGTI", "QBTS", "QBT", "QMCO", "RXRX", "SDGR",
    "NTRA", "GH", "CRL", "MEDP", "ICLR", "CTRE", "VRE",
    # Fintech / Crypto
    "COIN", "MSTR", "RIOT", "MARA", "CLSK", "IREN", "BTBT",
]

# Target date: exactly 2 years ago from today
TODAY = pd.Timestamp(datetime.now().date())
TARGET_DATE = TODAY - pd.DateOffset(years=2)


def compute_technical_indicators(df):
    """Compute technical indicators for a given dataframe."""
    if df is None or len(df) < 50:
        return None

    df = df.copy()
    latest = df.iloc[-1]
    price = float(latest['Close'])

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = float(100 - (100 / (1 + rs.iloc[-1])))

    # Moving averages
    sma_50 = float(df['Close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else np.nan
    sma_200 = float(df['Close'].rolling(200).mean().iloc[-1]) if len(df) >= 200 else np.nan
    dist_50 = ((price / sma_50) - 1) * 100 if sma_50 > 0 and not np.isnan(sma_50) else 0
    dist_200 = ((price / sma_200) - 1) * 100 if sma_200 > 0 and not np.isnan(sma_200) else 0

    # ADX
    plus_dm = df['High'].diff()
    minus_dm = -df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([
        df['High'] - df['Low'],
        abs(df['High'] - df['Close'].shift(1)),
        abs(df['Low'] - df['Close'].shift(1))
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_safe)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_safe)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * abs(plus_di - minus_di) / di_sum
    adx = float(dx.rolling(14).mean().iloc[-1]) if len(df) >= 28 else np.nan

    # Bollinger Bands
    bb_middle = float(df['Close'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else np.nan
    bb_std = float(df['Close'].rolling(20).std().iloc[-1]) if len(df) >= 20 else np.nan
    bb_pct = (price - (bb_middle - 2 * bb_std)) / (4 * bb_std) if bb_std > 0 and not np.isnan(bb_std) else 0.5

    # Returns
    return_1m = float(df['Close'].pct_change(21).iloc[-1]) * 100 if len(df) >= 22 else 0
    return_3m = float(df['Close'].pct_change(63).iloc[-1]) * 100 if len(df) >= 64 else 0
    return_6m = float(df['Close'].pct_change(126).iloc[-1]) * 100 if len(df) >= 127 else 0

    # Volatility
    volatility = float(df['Close'].pct_change().rolling(21).std().iloc[-1]) * np.sqrt(252) * 100 if len(df) >= 22 else 0

    # Trend
    if not np.isnan(sma_50) and not np.isnan(sma_200):
        if price > sma_50 > sma_200:
            trend = "BULLISH"
        elif price < sma_50 < sma_200:
            trend = "BEARISH"
        else:
            trend = "MIXED"
    else:
        trend = "MIXED"

    return {
        'price': price,
        'rsi': rsi,
        'adx': adx,
        'trend': trend,
        'dist_50': dist_50,
        'dist_200': dist_200,
        'bb_pct': bb_pct,
        'return_1m': return_1m,
        'return_3m': return_3m,
        'return_6m': return_6m,
        'volatility': volatility,
    }


def score_setup(indicators):
    """Score a setup using the same logic as stock_screener.py."""
    if indicators is None:
        return 0

    score = 0
    # Trend
    if indicators['trend'] == "BULLISH":
        score += 30
    elif indicators['trend'] == "MIXED":
        score += 15

    # ADX
    if indicators['adx'] > 30:
        score += 20
    elif indicators['adx'] > 25:
        score += 15
    elif indicators['adx'] > 20:
        score += 10

    # RSI
    if 40 <= indicators['rsi'] <= 60:
        score += 20
    elif 30 <= indicators['rsi'] < 40:
        score += 15
    elif 60 < indicators['rsi'] <= 70:
        score += 10
    elif indicators['rsi'] < 30:
        score += 5

    # Distance from 200 DMA
    if indicators['dist_200'] > 0:
        if 10 <= indicators['dist_200'] <= 40:
            score += 15
        elif 0 <= indicators['dist_200'] < 10:
            score += 10
        elif 40 < indicators['dist_200'] <= 60:
            score += 5

    # Momentum
    if indicators['return_3m'] > 20 and indicators['return_3m'] < 100:
        score += 15
    elif indicators['return_3m'] > 10:
        score += 10
    elif indicators['return_3m'] > 0:
        score += 5

    return score


def compute_similarity(ind1, ind2):
    """Compute similarity score between two technical profiles (0-100)."""
    if ind1 is None or ind2 is None:
        return 0

    score = 0

    # RSI similarity (weight 15)
    rsi_diff = abs(ind1['rsi'] - ind2['rsi'])
    if rsi_diff < 5:
        score += 15
    elif rsi_diff < 10:
        score += 10
    elif rsi_diff < 15:
        score += 5

    # ADX similarity (weight 15)
    adx_diff = abs(ind1['adx'] - ind2['adx'])
    if adx_diff < 5:
        score += 15
    elif adx_diff < 10:
        score += 10
    elif adx_diff < 15:
        score += 5

    # Trend match (weight 20)
    if ind1['trend'] == ind2['trend']:
        score += 20

    # dist_200 similarity (weight 15)
    d200_diff = abs(ind1['dist_200'] - ind2['dist_200'])
    if d200_diff < 10:
        score += 15
    elif d200_diff < 20:
        score += 10
    elif d200_diff < 30:
        score += 5

    # Volatility similarity (weight 15)
    vol_diff = abs(ind1['volatility'] - ind2['volatility'])
    if vol_diff < 10:
        score += 15
    elif vol_diff < 20:
        score += 10
    elif vol_diff < 30:
        score += 5

    # Return_3m similarity (weight 10)
    r3m_diff = abs(ind1['return_3m'] - ind2['return_3m'])
    if r3m_diff < 10:
        score += 10
    elif r3m_diff < 20:
        score += 5

    # Return_6m similarity (weight 10)
    r6m_diff = abs(ind1['return_6m'] - ind2['return_6m'])
    if r6m_diff < 15:
        score += 10
    elif r6m_diff < 30:
        score += 5

    return score


def main():
    print("=" * 80)
    print(f"PATTERN-MATCH WATCHLIST: {TARGET_DATE.date()} vs {TODAY.date()}")
    print("=" * 80)

    # STEP 1: Get historical data for current holdings as of 2 years ago
    print(f"\n--- STEP 1: Fetching {TARGET_DATE.date()} data for current holdings ---")

    hist_start = (TARGET_DATE - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    hist_end = (TARGET_DATE + pd.DateOffset(days=1)).strftime("%Y-%m-%d")

    historical_profiles = {}
    for symbol, name in CURRENT_HOLDINGS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=hist_start, end=hist_end)
            if hist is None or len(hist) < 50:
                print(f"  {symbol} ({name}): insufficient data")
                continue

            hist.index = hist.index.tz_localize(None)
            hist = hist[hist.index <= TARGET_DATE]

            if len(hist) < 50:
                print(f"  {symbol} ({name}): insufficient data up to target date")
                continue

            indicators = compute_technical_indicators(hist)
            if indicators:
                indicators['score'] = score_setup(indicators)
                historical_profiles[symbol] = indicators
                print(f"  {symbol} ({name}): Price=${indicators['price']:.2f}, "
                      f"RSI={indicators['rsi']:.1f}, ADX={indicators['adx']:.1f}, "
                      f"Trend={indicators['trend']}, Score={indicators['score']}/100")
        except Exception as e:
            print(f"  {symbol} ({name}): error - {e}")

    print(f"\n  Retrieved {len(historical_profiles)} of {len(CURRENT_HOLDINGS)} holdings")

    # STEP 2: Get current data for the broader universe
    print(f"\n--- STEP 2: Fetching current ({TODAY.date()}) data for screening universe ---")

    current_profiles = {}
    universe_to_screen = [s for s in set(CURRENT_UNIVERSE) if s not in CURRENT_HOLDINGS]

    for i, symbol in enumerate(universe_to_screen):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y")
            if hist is None or len(hist) < 50:
                continue

            indicators = compute_technical_indicators(hist)
            if indicators:
                indicators['score'] = score_setup(indicators)
                current_profiles[symbol] = indicators

            if (i + 1) % 20 == 0:
                print(f"  Processed {i+1}/{len(universe_to_screen)}...")
        except Exception:
            continue

    print(f"  Retrieved {len(current_profiles)} stocks for current screening")

    # STEP 3: Match current stocks to historical profiles
    print(f"\n--- STEP 3: Matching current stocks to {TARGET_DATE.date()} profiles ---")

    matches = []
    for hist_sym, hist_ind in historical_profiles.items():
        for curr_sym, curr_ind in current_profiles.items():
            similarity = compute_similarity(hist_ind, curr_ind)
            if similarity >= 55:
                matches.append({
                    'matched_on': hist_sym,
                    'matched_on_name': CURRENT_HOLDINGS.get(hist_sym, hist_sym),
                    'candidate': curr_sym,
                    'similarity': similarity,
                    'hist_indicators': hist_ind,
                    'curr_indicators': curr_ind,
                    'hist_score': hist_ind['score'],
                    'curr_score': curr_ind['score'],
                })

    matches.sort(key=lambda x: x['similarity'], reverse=True)

    # Deduplicate
    seen_candidates = set()
    unique_matches = []
    for m in matches:
        if m['candidate'] not in seen_candidates:
            seen_candidates.add(m['candidate'])
            unique_matches.append(m)

    print(f"\n  Found {len(unique_matches)} unique candidates with similarity >= 55")

    # Print top matches
    print("\n" + "=" * 80)
    print(f"TOP CANDIDATES: Stocks today that mirror {TARGET_DATE.date()} profiles")
    print("=" * 80)

    for i, m in enumerate(unique_matches[:25]):
        h = m['hist_indicators']
        c = m['curr_indicators']
        print(f"\n  #{i+1}: {m['candidate']} (similarity: {m['similarity']:.0f}%)")
        print(f"      Mirrors: {m['matched_on']} ({m['matched_on_name']}) — hist score: {m['hist_score']}/100")
        print(f"      Today: RSI={c['rsi']:.1f}, ADX={c['adx']:.1f}, Trend={c['trend']}, "
              f"Score={c['score']}/100")

    # Save results
    output_path = os.path.join(DATA_DIR, "pattern_match_results.json")
    with open(output_path, "w") as f:
        json.dump({
            'generated': str(TODAY.date()),
            'target_date': str(TARGET_DATE.date()),
            'historical_profiles': historical_profiles,
            'unique_matches': unique_matches[:50],
            'total_matches': len(unique_matches),
        }, f, indent=2, default=str)

    print(f"\n\nResults saved to {output_path}")
    return unique_matches


if __name__ == "__main__":
    main()

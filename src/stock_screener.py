"""
Stock Screener — Identifies stocks showing early signs of growth
Based on patterns from top 10 growth stocks (AI exposure, supply constraints,
earnings momentum, product launches, sector tailwinds, good technical setup)
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.trading_strategy_engine import fetch_data




def calculate_technical_score(data: pd.DataFrame) -> Dict:
    """Calculate technical entry score for a stock."""
    if data is None or len(data) < 50:
        return None
    
    latest = data.iloc[-1]
    price = float(latest['Close'])
    
    # RSI (guard against division by zero when loss == 0)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = float(100 - (100 / (1 + rs.iloc[-1]))) if pd.notna(rs.iloc[-1]) else 100.0
    
    # Moving averages
    sma_50 = float(data['Close'].rolling(50).mean().iloc[-1])
    sma_200 = float(data['Close'].rolling(200).mean().iloc[-1])
    dist_50 = ((price / sma_50) - 1) * 100 if sma_50 > 0 else 0
    dist_200 = ((price / sma_200) - 1) * 100 if sma_200 > 0 else 0
    
    # ADX (with division-by-zero guards)
    plus_dm = data['High'].diff()
    minus_dm = -data['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([data['High'] - data['Low'], abs(data['High'] - data['Close'].shift(1)), abs(data['Low'] - data['Close'].shift(1))], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_safe)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_safe)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * abs(plus_di - minus_di) / di_sum
    adx = float(dx.rolling(14).mean().iloc[-1]) if pd.notna(dx.rolling(14).mean().iloc[-1]) else 0.0
    
    # Bollinger Bands
    bb_middle = float(data['Close'].rolling(20).mean().iloc[-1])
    bb_std = float(data['Close'].rolling(20).std().iloc[-1])
    bb_pct = (price - (bb_middle - 2 * bb_std)) / (4 * bb_std) if bb_std > 0 else 0.5
    
    # Returns
    return_1m = float(data['Close'].pct_change(21).iloc[-1]) * 100
    return_3m = float(data['Close'].pct_change(63).iloc[-1]) * 100
    return_6m = float(data['Close'].pct_change(126).iloc[-1]) * 100
    
    # Volatility
    volatility = float(data['Close'].pct_change().rolling(21).std().iloc[-1]) * np.sqrt(252) * 100
    
    # Trend
    if price > sma_50 > sma_200:
        trend = "BULLISH"
    elif price < sma_50 < sma_200:
        trend = "BEARISH"
    else:
        trend = "MIXED"
    
    # Entry score (0-100)
    score = 0
    
    # Trend score (30 points)
    if trend == "BULLISH":
        score += 30
    elif trend == "MIXED":
        score += 15
    
    # ADX score (20 points)
    if adx > 30:
        score += 20
    elif adx > 25:
        score += 15
    elif adx > 20:
        score += 10
    
    # RSI score (20 points) — prefer not overbought
    if 40 <= rsi <= 60:
        score += 20
    elif 30 <= rsi < 40:
        score += 15
    elif 60 < rsi <= 70:
        score += 10
    elif rsi < 30:
        score += 5  # Oversold but could be value trap
    
    # Distance from 200 DMA score (15 points)
    # If sma_200 is NaN (insufficient data), dist_200 defaults to 0, which would
    # award 10 free points. Guard against this: only score if sma_200 is valid.
    if sma_200 > 0 and sma_200 == sma_200:  # valid sma_200
        if 10 <= dist_200 <= 40:
            score += 15
        elif 0 <= dist_200 < 10:
            score += 10
        elif 40 < dist_200 <= 60:
            score += 5
        elif dist_200 > 60:
            score += 0  # Too extended
    # else: insufficient data for 200-DMA, no points awarded
    
    # Momentum score (15 points)
    if return_3m > 20 and return_3m < 100:
        score += 15
    elif return_3m > 10:
        score += 10
    elif return_3m > 0:
        score += 5
    
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
        'entry_score': score,
    }


def screen_stock(ticker: str, name: str, sector: str) -> Optional[Dict]:
    """Screen a single stock for entry quality."""
    try:
        data = fetch_data(ticker, "1y")
        if data is None or len(data) < 50:
            return None
        
        tech = calculate_technical_score(data)
        if tech is None:
            return None
        
        # Determine entry rating
        if tech['entry_score'] >= 70:
            rating = "STRONG BUY"
        elif tech['entry_score'] >= 55:
            rating = "BUY"
        elif tech['entry_score'] >= 40:
            rating = "WATCH"
        else:
            rating = "AVOID"
        
        return {
            'ticker': ticker,
            'name': name,
            'sector': sector,
            'rating': rating,
            **tech,
        }
        
    except Exception as e:
        return None


def run_screener():
    """Run the stock screener on candidate stocks."""
    
    # Candidate stocks — mix of AI, semiconductor, biotech, healthcare
    candidates = [
        # Semiconductors / AI
        ("MRVL", "Marvell Technology", "Semiconductors"),
        ("AVGO", "Broadcom", "Semiconductors"),
        ("TSM", "Taiwan Semiconductor", "Semiconductors"),
        ("ASML", "ASML Holding", "Semiconductors"),
        ("LRCX", "Lam Research", "Semiconductors"),
        ("AMAT", "Applied Materials", "Semiconductors"),
        ("KLAC", "KLA Corporation", "Semiconductors"),
        ("SNPS", "Synopsys", "Semiconductors"),
        ("CDNS", "Cadence Design", "Semiconductors"),
        ("ANET", "Arista Networks", "Networking"),
        
        # AI / Cloud
        ("CRWD", "CrowdStrike", "Cybersecurity"),
        ("PANW", "Palo Alto Networks", "Cybersecurity"),
        ("OKTA", "Okta", "Cybersecurity"),
        ("DDOG", "Datadog", "Cloud"),
        ("SNOW", "Snowflake", "Cloud"),
        ("MDB", "MongoDB", "Cloud"),
        ("NET", "Cloudflare", "Cloud"),
        ("PLTR", "Palantir", "AI"),
        ("AI", "C3.ai", "AI"),
        ("SMCI", "Super Micro Computer", "AI Infrastructure"),
        
        # Biotech / Healthcare
        ("LLY", "Eli Lilly", "Biotech"),
        ("MRNA", "Moderna", "Biotech"),
        ("IOVA", "Iovance", "Immunotherapy"),
        ("KOD", "Kodiak Sciences", "Biotech"),
        ("TXG", "10x Genomics", "Genomics"),
        ("CRSP", "CRISPR Therapeutics", "Genomics"),
        ("NTLA", "Intellia Therapeutics", "Genomics"),
        ("BEAM", "Beam Therapeutics", "Genomics"),
        ("EDIT", "Editas Medicine", "Genomics"),
        ("VRTX", "Vertex Pharmaceuticals", "Biotech"),
        
        # Power / Energy
        ("GEV", "GE Vernova", "Power"),
        ("VICR", "Vicor", "Power Conversion"),
        ("BE", "Bloom Energy", "Renewable Energy"),
        ("ENPH", "Enphase Energy", "Renewable Energy"),
        ("FSLR", "First Solar", "Renewable Energy"),
        
        # Space
        ("RKLB", "Rocket Lab", "Space"),
        ("ASTS", "AST SpaceMobile", "Satellites"),
        ("LUNR", "Lunar", "Space"),
        
        # Memory
        ("MU", "Micron", "Memory"),
        ("SNDK", "Sandisk", "Memory"),
        
        # Optical
        ("LITE", "Lumentum", "Optical"),
        ("MXL", "MaxLinear", "Optical"),
        ("COHR", "Coherent", "Optical"),
    ]
    
    print("=" * 100)
    print("  STOCK SCREENER — Early Growth Entry Detection")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Criteria: Bullish trend + ADX>25 + RSI 40-60 + 10-40% above 200 DMA + positive momentum")
    print("=" * 100)
    
    results = []
    
    for ticker, name, sector in candidates:
        result = screen_stock(ticker, name, sector)
        if result:
            results.append(result)
            print(f"  {name} ({ticker}): Score {result['entry_score']}/100 — {result['rating']}")
    
    # Sort by entry score
    results.sort(key=lambda x: x['entry_score'], reverse=True)
    
    # Print top candidates
    print(f"\n{'─'*100}")
    print(f"  TOP CANDIDATES (Score >= 55)")
    print(f"{'─'*100}")
    
    top_candidates = [r for r in results if r['entry_score'] >= 55]
    
    if top_candidates:
        print(f"\n  {'Ticker':<8} {'Company':<25} {'Score':>6} {'RSI':>6} {'ADX':>6} {'Trend':<10} {'vs 200DMA':>10} {'3M Return':>10} {'Rating':<12}")
        print(f"  {'─'*95}")
        
        for r in top_candidates:
            print(f"  {r['ticker']:<8} {r['name']:<25} {r['entry_score']:>6} {r['rsi']:>6.1f} {r['adx']:>6.1f} {r['trend']:<10} {r['dist_200']:>+9.1f}% {r['return_3m']:>+9.1f}% {r['rating']:<12}")
    else:
        print("\n  No candidates met the threshold (score >= 55).")
    
    # Print watchlist candidates
    print(f"\n{'─'*100}")
    print(f"  WATCHLIST CANDIDATES (Score 40-54)")
    print(f"{'─'*100}")
    
    watchlist = [r for r in results if 40 <= r['entry_score'] < 55]
    
    if watchlist:
        print(f"\n  {'Ticker':<8} {'Company':<25} {'Score':>6} {'RSI':>6} {'ADX':>6} {'Trend':<10} {'vs 200DMA':>10} {'3M Return':>10} {'Rating':<12}")
        print(f"  {'─'*95}")
        
        for r in watchlist:
            print(f"  {r['ticker']:<8} {r['name']:<25} {r['entry_score']:>6} {r['rsi']:>6.1f} {r['adx']:>6.1f} {r['trend']:<10} {r['dist_200']:>+9.1f}% {r['return_3m']:>+9.1f}% {r['rating']:<12}")
    else:
        print("\n  No watchlist candidates found.")
    
    # Summary
    print(f"\n{'─'*100}")
    print(f"  SUMMARY")
    print(f"{'─'*100}")
    
    strong_buys = [r for r in results if r['rating'] == 'STRONG BUY']
    buys = [r for r in results if r['rating'] == 'BUY']
    watch = [r for r in results if r['rating'] == 'WATCH']
    avoid = [r for r in results if r['rating'] == 'AVOID']
    
    print(f"\n  STRONG BUY: {len(strong_buys)}")
    for r in strong_buys:
        print(f"    {r['name']} ({r['ticker']}) — Score {r['entry_score']}, RSI {r['rsi']:.1f}, ADX {r['adx']:.1f}")
    
    print(f"\n  BUY: {len(buys)}")
    for r in buys:
        print(f"    {r['name']} ({r['ticker']}) — Score {r['entry_score']}, RSI {r['rsi']:.1f}, ADX {r['adx']:.1f}")
    
    print(f"\n  WATCH: {len(watch)}")
    for r in watch:
        print(f"    {r['name']} ({r['ticker']}) — Score {r['entry_score']}, RSI {r['rsi']:.1f}, ADX {r['adx']:.1f}")
    
    print(f"\n  AVOID: {len(avoid)}")
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "screener_results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to: {output_path}")
    print("=" * 100)
    
    return results


def main():
    """Run the stock screener."""
    results = run_screener()
    
    # Return top candidates for watchlist
    top_candidates = [r for r in results if r['entry_score'] >= 55]
    return top_candidates


if __name__ == "__main__":
    main()

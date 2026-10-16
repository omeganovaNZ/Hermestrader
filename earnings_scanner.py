"""
Pre-Earnings Scanner
Checks earnings calendars for watched stocks and flags upcoming reports.
Helps avoid buying right before earnings (or identifies post-earnings opportunities).
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os


def get_earnings_date(ticker: str):
    """Get next earnings date for a ticker using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if calendar is not None:
            # yfinance calendar can be a dict or DataFrame
            if isinstance(calendar, dict):
                # Dict format: {'Earnings Date': [date], 'Earnings Average': ...}
                if 'Earnings Date' in calendar:
                    dates = calendar['Earnings Date']
                    if isinstance(dates, list) and len(dates) > 0:
                        return pd.Timestamp(dates[0])
                    elif isinstance(dates, (pd.Timestamp, datetime)):
                        return pd.Timestamp(dates)
            elif isinstance(calendar, pd.DataFrame):
                if 'Earnings Date' in calendar.columns:
                    dates = calendar['Earnings Date'].dropna()
                    if len(dates) > 0:
                        return pd.Timestamp(dates.iloc[0])
        return None
    except Exception as e:
        print(f"  Error getting earnings for {ticker}: {e}")
        return None


def scan_earnings(watchlist: dict, days_ahead: int = 14):
    """
    Scan for upcoming earnings in the next N days.
    Returns list of stocks with earnings dates.
    """
    today = datetime.now().date()
    upcoming = []
    
    print(f"Scanning earnings for next {days_ahead} days (from {today})...\n")
    
    for ticker, name in watchlist.items():
        try:
            earnings_date = get_earnings_date(ticker)
            if earnings_date is not None:
                earnings_date = earnings_date.date() if hasattr(earnings_date, 'date') else earnings_date
                days_until = (earnings_date - today).days
                
                if 0 <= days_until <= days_ahead:
                    upcoming.append({
                        'ticker': ticker,
                        'name': name,
                        'earnings_date': str(earnings_date),
                        'days_until': days_until,
                    })
                    print(f"  {name} ({ticker}): Earnings in {days_until} days ({earnings_date})")
                elif days_until < 0:
                    print(f"  {name} ({ticker}): Earnings was {-days_until} days ago ({earnings_date})")
                else:
                    print(f"  {name} ({ticker}): Earnings in {days_until} days ({earnings_date})")
            else:
                print(f"  {name} ({ticker}): No earnings date found")
        except Exception as e:
            print(f"  {name} ({ticker}): Error - {e}")
    
    return upcoming


def get_earnings_history(ticker: str, count: int = 4):
    """Get recent earnings history for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_dates
        if earnings is not None and not earnings.empty:
            return earnings.head(count)
    except Exception as e:
        print(f"  Error getting earnings history for {ticker}: {e}")
    return None


def main():
    watchlist = {
        "RKLB": "Rocket Lab",
        "NVDA": "NVIDIA",
        "MU": "Micron",
        "AMD": "AMD",
        "INTC": "Intel",
        "GOOGL": "Alphabet",
        "XOM": "Exxon Mobil",
        "CVX": "Chevron",
        "NEE": "NextEra Energy",
    }
    
    print("=" * 70)
    print("  PRE-EARNINGS SCANNER")
    print("  Checking upcoming earnings for watched stocks")
    print("=" * 70)
    
    # Scan for upcoming earnings
    upcoming = scan_earnings(watchlist, days_ahead=30)
    
    print(f"\n{'='*70}")
    print(f"  SUMMARY: {len(upcoming)} stocks reporting in next 30 days")
    print(f"{'='*70}")
    
    if upcoming:
        print("\n  UPCOMING EARNINGS:")
        for e in upcoming:
            print(f"    {e['name']} ({e['ticker']}): {e['days_until']} days ({e['earnings_date']})")
        
        print("\n  STRATEGY IMPLICATIONS:")
        print("    - Avoid NEW positions 2-3 days before earnings")
        print("    - Existing positions: consider reducing size if uncertain")
        print("    - Post-earnings: watch for gap direction and hold through if positive")
        print("    - Long-term holders: earnings noise is temporary, focus on fundamentals")
    else:
        print("\n  No upcoming earnings in the next 30 days.")
        print("  Good time to accumulate positions without earnings risk.")
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earnings_calendar.json")
    with open(output_path, 'w') as f:
        json.dump(upcoming, f, indent=2)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()

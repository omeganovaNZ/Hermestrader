"""
Portfolio Allocation Framework
Based on structural trends and market-aware strategy results.
Designed for long-term holding with risk management.
"""

import json
import os
from datetime import datetime


# Portfolio allocation based on backtesting results and structural trends
ALLOCATION_FRAMEWORK = {
    "core_holdings": {
        "description": "Long-term holds with strong fundamentals and structural tailwinds",
        "stocks": [
            {
                "ticker": "NVDA",
                "name": "NVIDIA",
                "allocation_pct": 0.15,
                "rationale": "AI infrastructure supercycle, $31.6T projected investment through 2050",
                "config": "SEMICONDUCTOR_LOGIC",
                "entry_strategy": "Buy on pullbacks to 50-day EMA, hold through volatility",
                "risk_level": "high",
            },
            {
                "ticker": "MU",
                "name": "Micron",
                "allocation_pct": 0.12,
                "rationale": "Memory chip AI demand, cyclical recovery with hybrid strategy edge",
                "config": "SEMICONDUCTOR_MEMORY",
                "entry_strategy": "Buy on dips when RSI < 30, hold through cycle",
                "risk_level": "high",
            },
            {
                "ticker": "GOOGL",
                "name": "Alphabet",
                "allocation_pct": 0.10,
                "rationale": "AI and cloud growth, undervalued vs peers",
                "config": "US_TECH",
                "entry_strategy": "Buy on market weakness, long-term hold",
                "risk_level": "medium",
            },
        ],
    },
    "growth_holdings": {
        "description": "Higher risk/reward with structural tailwinds",
        "stocks": [
            {
                "ticker": "RKLB",
                "name": "Rocket Lab",
                "allocation_pct": 0.08,
                "rationale": "Space economy growth, satellite demand from defense and commercial",
                "config": "NZ_AUS",
                "entry_strategy": "Small position, wide stops, hold for multi-year growth",
                "risk_level": "very_high",
            },
            {
                "ticker": "AMD",
                "name": "AMD",
                "allocation_pct": 0.08,
                "rationale": "AI GPU market share gains, undervalued vs NVDA",
                "config": "SEMICONDUCTOR_LOGIC",
                "entry_strategy": "Buy on pullbacks, hold through volatility",
                "risk_level": "high",
            },
        ],
    },
    "energy_transition": {
        "description": "Energy stocks benefiting from geopolitical tensions — BUY & HOLD (backtesting showed active trading underperforms)",
        "stocks": [
            {
                "ticker": "XOM",
                "name": "Exxon Mobil",
                "allocation_pct": 0.10,
                "rationale": "Energy price upside from geopolitical tensions, strong dividends. B&H +233% vs MA +27% over 5y.",
                "config": "BUY_AND_HOLD",
                "entry_strategy": "Buy and hold — do NOT trade actively. Strong uptrend favors passive holding.",
                "risk_level": "medium",
            },
            {
                "ticker": "CVX",
                "name": "Chevron",
                "allocation_pct": 0.08,
                "rationale": "Energy security focus, integrated oil major. B&H +145% vs MA +19% over 5y.",
                "config": "BUY_AND_HOLD",
                "entry_strategy": "Buy and hold — do NOT trade actively. Strong uptrend favors passive holding.",
                "risk_level": "medium",
            },
            {
                "ticker": "NEE",
                "name": "NextEra Energy",
                "allocation_pct": 0.05,
                "rationale": "Renewable energy transition, AI data center power demand. Smaller allocation due to recent underperformance.",
                "config": "BUY_AND_HOLD",
                "entry_strategy": "Buy on weakness, hold for long-term energy transition theme",
                "risk_level": "medium",
            },
        ],
    },
    "cash_buffer": {
        "description": "Cash reserve for opportunities and risk management",
        "allocation_pct": 0.20,
        "rationale": "20% cash allows buying opportunities during market stress",
    },
}


def print_allocation():
    """Print the portfolio allocation framework."""
    print("=" * 80)
    print("  PORTFOLIO ALLOCATION FRAMEWORK")
    print("  Based on Structural Trends and Market-Aware Backtesting")
    print("=" * 80)
    
    total_allocated = 0
    
    for category, details in ALLOCATION_FRAMEWORK.items():
        if category == "cash_buffer":
            continue
        
        print(f"\n{'─'*80}")
        print(f"  {category.upper().replace('_', ' ')}")
        print(f"  {details['description']}")
        print(f"{'─'*80}")
        
        for stock in details["stocks"]:
            print(f"  {stock['name']} ({stock['ticker']})")
            print(f"    Allocation: {stock['allocation_pct']:.0%}")
            print(f"    Risk Level: {stock['risk_level']}")
            print(f"    Rationale: {stock['rationale']}")
            print(f"    Entry Strategy: {stock['entry_strategy']}")
            print()
            total_allocated += stock['allocation_pct']
    
    cash = ALLOCATION_FRAMEWORK["cash_buffer"]["allocation_pct"]
    print(f"{'─'*80}")
    print(f"  CASH BUFFER")
    print(f"    Allocation: {cash:.0%}")
    print(f"    Purpose: {ALLOCATION_FRAMEWORK['cash_buffer']['rationale']}")
    print(f"{'─'*80}")
    
    print(f"\n  Total Allocated: {total_allocated:.0%}")
    print(f"  Total Cash: {cash:.0%}")
    print(f"  Total: {total_allocated + cash:.0%}")
    print("=" * 80)


def save_allocation():
    """Save allocation to JSON."""
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_allocation.json")
    with open(output_path, 'w') as f:
        json.dump(ALLOCATION_FRAMEWORK, f, indent=2)
    print(f"\nSaved to: {output_path}")


def main():
    print_allocation()
    save_allocation()


if __name__ == "__main__":
    main()

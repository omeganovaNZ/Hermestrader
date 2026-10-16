"""
Multi-stock backtest: Buy & Hold vs Mean Reversion
Tests across a basket of tech/semiconductor stocks.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import json
import os
import sys

# Import from main engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trading_strategy_engine import (
    BacktestEngine, MeanReversionStrategy,
    fetch_data, Trade
)


def run_mean_reversion_backtest(ticker: str, period: str = "5y"):
    """Run mean reversion strategy on a ticker."""
    data = fetch_data(ticker, period)
    engine = BacktestEngine(initial_capital=100_000, commission=0.001)
    strategy = MeanReversionStrategy(lookback=20, num_std=2.0)
    result = engine.run(data, strategy, ticker, "Mean Reversion (BB)")
    return result, data


def run_buy_and_hold(data: pd.DataFrame, ticker: str):
    """Calculate buy and hold returns."""
    start_price = data['Close'].iloc[0]
    end_price = data['Close'].iloc[-1]
    total_return = (end_price / start_price - 1) * 100
    
    # Calculate max drawdown
    rolling_max = data['Close'].expanding().max()
    drawdown = (data['Close'] - rolling_max) / rolling_max
    max_dd = drawdown.min() * 100
    
    # Annualized return
    days = (data.index[-1] - data.index[0]).days
    years = days / 365.25 if days > 0 else 1
    ann_return = ((end_price / start_price) ** (1/years) - 1) * 100 if years > 0 else 0
    
    # Sharpe
    daily_returns = data['Close'].pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0
    
    return {
        'ticker': ticker,
        'total_return': total_return,
        'ann_return': ann_return,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'start_price': start_price,
        'end_price': end_price,
    }


def main():
    tickers = [
        ("RKLB", "Rocket Lab"),
        ("NVDA", "NVIDIA"),
        ("MU", "Micron"),
        ("AMD", "AMD"),
        ("INTC", "Intel"),
        ("005930.KS", "Samsung"),
        ("GOOGL", "Alphabet/Google"),
    ]
    
    period = "5y"
    
    print("=" * 80)
    print("  MULTI-STOCK BACKTEST: BUY & HOLD vs MEAN REVERSION")
    print("=" * 80)
    
    all_results = {}
    
    for ticker, name in tickers:
        print(f"\n{'─'*80}")
        print(f"  {name} ({ticker})")
        print(f"{'─'*80}")
        
        try:
            # Mean Reversion
            mr_result, data = run_mean_reversion_backtest(ticker, period)
            print(mr_result.summary())
            
            # Buy & Hold
            bh = run_buy_and_hold(data, ticker)
            print(f"\n  Buy & Hold:")
            print(f"    Total Return:      {bh['total_return']:+.2f}%")
            print(f"    Annualized:       {bh['ann_return']:+.2f}%")
            print(f"    Sharpe:           {bh['sharpe']:.3f}")
            print(f"    Max Drawdown:     {bh['max_dd']:.2f}%")
            
            all_results[ticker] = {
                'name': name,
                'mean_reversion': {
                    'total_return': round(mr_result.total_return_pct, 2),
                    'ann_return': round(mr_result.annualized_return_pct, 2),
                    'sharpe': round(mr_result.sharpe_ratio, 3),
                    'max_dd': round(mr_result.max_drawdown_pct, 2),
                    'num_trades': mr_result.num_trades,
                    'win_rate': round(mr_result.win_rate, 4),
                    'avg_trade_return': round(mr_result.avg_trade_return, 2),
                },
                'buy_and_hold': {
                    'total_return': round(bh['total_return'], 2),
                    'ann_return': round(bh['ann_return'], 2),
                    'sharpe': round(bh['sharpe'], 3),
                    'max_dd': round(bh['max_dd'], 2),
                }
            }
            
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results[ticker] = {'name': name, 'error': str(e)}
    
    # Summary table
    print("\n\n" + "=" * 80)
    print("  SUMMARY COMPARISON TABLE")
    print("=" * 80)
    print(f"{'Stock':<20} {'B&H Return':>12} {'MR Return':>12} {'B&H Sharpe':>12} {'MR Sharpe':>12} {'B&H MaxDD':>12} {'MR MaxDD':>12}")
    print("-" * 80)
    
    for ticker, name in tickers:
        if ticker in all_results and 'error' not in all_results[ticker]:
            r = all_results[ticker]
            bh = r['buy_and_hold']
            mr = r['mean_reversion']
            print(f"{name:<20} {bh['total_return']:>+11.2f}% {mr['total_return']:>+11.2f}% {bh['sharpe']:>11.3f} {mr['sharpe']:>11.3f} {bh['max_dd']:>+11.2f}% {mr['max_dd']:>+11.2f}%")
    
    print("=" * 80)
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_stock_backtest_results.json")
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    # Create comparison chart
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    axes = axes.flatten()
    
    for idx, (ticker, name) in enumerate(tickers):
        if ticker in all_results and 'error' not in all_results[ticker]:
            ax = axes[idx]
            r = all_results[ticker]
            
            strategies = ['Buy & Hold', 'Mean Reversion']
            returns = [r['buy_and_hold']['total_return'], r['mean_reversion']['total_return']]
            colors = ['#757575', '#FF9800']
            
            bars = ax.bar(strategies, returns, color=colors, alpha=0.8, edgecolor='black')
            ax.set_title(f'{name} ({ticker})', fontsize=11, fontweight='bold')
            ax.set_ylabel('Total Return %')
            ax.axhline(y=0, color='black', linewidth=0.5)
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add value labels
            for bar, val in zip(bars, returns):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (2 if val >= 0 else -6),
                       f'{val:+.1f}%', ha='center', va='bottom' if val >= 0 else 'top',
                       fontsize=9, fontweight='bold')
    
    # Remove empty subplot
    if len(tickers) < 8:
        fig.delaxes(axes[7])
    
    plt.suptitle('Buy & Hold vs Mean Reversion — 5 Year Performance', fontsize=14, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_stock_comparison.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to: {chart_path}")


if __name__ == "__main__":
    main()

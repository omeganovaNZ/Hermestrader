"""
Hybrid Strategy: Dynamic Regime Switching
- Trending market: Buy & Hold behavior (stay long)
- Stagnant/ranging market: Mean Reversion (buy oversold, sell overbought)

Uses ADX (Average Directional Index) to detect trend strength.
When ADX is high, the stock is trending → hold.
When ADX is low, the stock is ranging → apply mean reversion.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trading_strategy_engine import (
    BacktestEngine, MeanReversionStrategy, fetch_data, Trade
)


class HybridStrategy:
    """
    Dynamic regime-switching strategy.
    
    When trend is strong (ADX > threshold): Buy & Hold (stay long)
    When trend is weak (ADX <= threshold): Mean Reversion (trade the range)
    """
    
    def __init__(self, 
                 adx_lookback: int = 14,
                 adx_threshold: float = 25.0,
                 mr_lookback: int = 20,
                 mr_num_std: float = 2.0,
                 trend_ma_lookback: int = 50):
        self.adx_lookback = adx_lookback
        self.adx_threshold = adx_threshold
        self.mr_lookback = mr_lookback
        self.mr_num_std = mr_num_std
        self.trend_ma_lookback = trend_ma_lookback
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average Directional Index (ADX)."""
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # Smooth TR, +DM, -DM
        n = self.adx_lookback
        atr = tr.rolling(n).mean()
        plus_di = 100 * (plus_dm.rolling(n).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(n).mean() / atr)
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(n).mean()
        
        return adx
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Calculate ADX
        df['adx'] = self._calculate_adx(df)
        
        # Calculate Bollinger Bands for mean reversion
        df['sma'] = df['Close'].rolling(self.mr_lookback).mean()
        df['std'] = df['Close'].rolling(self.mr_lookback).std()
        df['upper_band'] = df['sma'] + self.mr_num_std * df['std']
        df['lower_band'] = df['sma'] - self.mr_num_std * df['std']
        df['pct_b'] = (df['Close'] - df['lower_band']) / (df['upper_band'] - df['lower_band'])
        
        # Calculate trend MA for Buy & Hold mode
        df['trend_ma'] = df['Close'].rolling(self.trend_ma_lookback).mean()
        
        # Regime detection: 1 = trending (Buy & Hold), 0 = ranging (Mean Reversion)
        df['regime'] = 0  # Default to ranging
        df.loc[df['adx'] > self.adx_threshold, 'regime'] = 1  # Trending
        
        # Generate signals based on regime
        df['signal'] = 0
        
        # In trending regime: Buy & Hold behavior (buy and stay long)
        # Buy when we don't have a position and regime is trending
        # Sell only when regime changes from trending to ranging
        
        # In ranging regime: Mean Reversion behavior
        # Buy when price hits lower band (oversold)
        # Sell when price hits upper band (overbought)
        
        position = 0
        signals = []
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            if position == 0:
                # No position - look for entry
                if row['regime'] == 1:
                    # Trending: buy to enter Buy & Hold mode
                    signals.append(1)
                    position = 1
                elif row['pct_b'] < 0.05 and row['regime'] == 0:
                    # Ranging: buy oversold (mean reversion)
                    signals.append(1)
                    position = 1
                else:
                    signals.append(0)
            else:
                # Have position - look for exit
                if row['regime'] == 1:
                    # Trending: hold (Buy & Hold behavior)
                    signals.append(0)
                elif row['pct_b'] > 0.95:
                    # Ranging: sell overbought (mean reversion)
                    signals.append(-1)
                    position = 0
                elif row['regime'] == 0 and row['pct_b'] > 0.5:
                    # Was trending, now ranging and price is above middle: exit
                    signals.append(-1)
                    position = 0
                else:
                    signals.append(0)
        
        df['signal'] = signals
        return df


def run_hybrid_backtest(ticker: str, period: str = "5y"):
    """Run hybrid strategy on a ticker."""
    data = fetch_data(ticker, period)
    engine = BacktestEngine(initial_capital=100_000, commission=0.001)
    strategy = HybridStrategy(
        adx_lookback=14,
        adx_threshold=25.0,
        mr_lookback=20,
        mr_num_std=2.0,
        trend_ma_lookback=50
    )
    result = engine.run(data, strategy, ticker, "Hybrid (BH+MR)")
    return result, data


def run_buy_and_hold(data: pd.DataFrame, ticker: str):
    """Calculate buy and hold returns."""
    start_price = data['Close'].iloc[0]
    end_price = data['Close'].iloc[-1]
    total_return = (end_price / start_price - 1) * 100
    
    rolling_max = data['Close'].expanding().max()
    drawdown = (data['Close'] - rolling_max) / rolling_max
    max_dd = drawdown.min() * 100
    
    days = (data.index[-1] - data.index[0]).days
    years = days / 365.25 if days > 0 else 1
    ann_return = ((end_price / start_price) ** (1/years) - 1) * 100 if years > 0 else 0
    
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
    }


def run_mean_reversion(data: pd.DataFrame, ticker: str):
    """Run mean reversion for comparison."""
    engine = BacktestEngine(initial_capital=100_000, commission=0.001)
    strategy = MeanReversionStrategy(lookback=20, num_std=2.0)
    result = engine.run(data, strategy, ticker, "Mean Reversion (BB)")
    return result


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
    
    print("=" * 90)
    print("  HYBRID STRATEGY BACKTEST: DYNAMIC REGIME SWITCHING")
    print("  Trending (ADX > 25): Buy & Hold behavior")
    print("  Ranging  (ADX <= 25): Mean Reversion behavior")
    print("=" * 90)
    
    all_results = {}
    
    for ticker, name in tickers:
        print(f"\n{'─'*90}")
        print(f"  {name} ({ticker})")
        print(f"{'─'*90}")
        
        try:
            # Hybrid strategy
            hybrid_result, data = run_hybrid_backtest(ticker, period)
            print(hybrid_result.summary())
            
            # Mean Reversion for comparison
            mr_result = run_mean_reversion(data, ticker)
            print(f"\n  Mean Reversion (BB) — {ticker}")
            print(f"    Total Return:      {mr_result.total_return_pct:+.2f}%")
            print(f"    Sharpe:           {mr_result.sharpe_ratio:.3f}")
            print(f"    Max Drawdown:     {mr_result.max_drawdown_pct:.2f}%")
            print(f"    Trades:           {mr_result.num_trades}")
            print(f"    Win Rate:         {mr_result.win_rate:.1%}")
            
            # Buy & Hold
            bh = run_buy_and_hold(data, ticker)
            print(f"\n  Buy & Hold:")
            print(f"    Total Return:      {bh['total_return']:+.2f}%")
            print(f"    Sharpe:           {bh['sharpe']:.3f}")
            print(f"    Max Drawdown:     {bh['max_dd']:.2f}%")
            
            all_results[ticker] = {
                'name': name,
                'hybrid': {
                    'total_return': round(hybrid_result.total_return_pct, 2),
                    'ann_return': round(hybrid_result.annualized_return_pct, 2),
                    'sharpe': round(hybrid_result.sharpe_ratio, 3),
                    'max_dd': round(hybrid_result.max_drawdown_pct, 2),
                    'num_trades': hybrid_result.num_trades,
                    'win_rate': round(hybrid_result.win_rate, 4),
                    'avg_trade_return': round(hybrid_result.avg_trade_return, 2),
                },
                'mean_reversion': {
                    'total_return': round(mr_result.total_return_pct, 2),
                    'sharpe': round(mr_result.sharpe_ratio, 3),
                    'max_dd': round(mr_result.max_drawdown_pct, 2),
                    'num_trades': mr_result.num_trades,
                    'win_rate': round(mr_result.win_rate, 4),
                },
                'buy_and_hold': {
                    'total_return': round(bh['total_return'], 2),
                    'sharpe': round(bh['sharpe'], 3),
                    'max_dd': round(bh['max_dd'], 2),
                }
            }
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            all_results[ticker] = {'name': name, 'error': str(e)}
    
    # Summary table
    print("\n\n" + "=" * 90)
    print("  SUMMARY: HYBRID vs MEAN REVERSION vs BUY & HOLD")
    print("=" * 90)
    print(f"{'Stock':<20} {'B&H Return':>12} {'MR Return':>12} {'Hybrid Return':>14} {'B&H Sharpe':>12} {'MR Sharpe':>12} {'Hybrid Sharpe':>14}")
    print("-" * 90)
    
    for ticker, name in tickers:
        if ticker in all_results and 'error' not in all_results[ticker]:
            r = all_results[ticker]
            bh = r['buy_and_hold']
            mr = r['mean_reversion']
            hy = r['hybrid']
            print(f"{name:<20} {bh['total_return']:>+11.2f}% {mr['total_return']:>+11.2f}% {hy['total_return']:>+13.2f}% {bh['sharpe']:>11.3f} {mr['sharpe']:>11.3f} {hy['sharpe']:>13.3f}")
    
    print("\n")
    print(f"{'Stock':<20} {'B&H MaxDD':>12} {'MR MaxDD':>12} {'Hybrid MaxDD':>14} {'MR Trades':>10} {'Hybrid Trades':>14}")
    print("-" * 90)
    
    for ticker, name in tickers:
        if ticker in all_results and 'error' not in all_results[ticker]:
            r = all_results[ticker]
            bh = r['buy_and_hold']
            mr = r['mean_reversion']
            hy = r['hybrid']
            print(f"{name:<20} {bh['max_dd']:>+11.2f}% {mr['max_dd']:>+11.2f}% {hy['max_dd']:>+13.2f}% {mr['num_trades']:>10} {hy['num_trades']:>14}")
    
    print("=" * 90)
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hybrid_strategy_results.json")
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
            
            strategies = ['Buy & Hold', 'Mean Reversion', 'Hybrid']
            returns = [r['buy_and_hold']['total_return'], r['mean_reversion']['total_return'], r['hybrid']['total_return']]
            colors = ['#757575', '#FF9800', '#9C27B0']
            
            bars = ax.bar(strategies, returns, color=colors, alpha=0.8, edgecolor='black')
            ax.set_title(f'{name} ({ticker})', fontsize=11, fontweight='bold')
            ax.set_ylabel('Total Return %')
            ax.axhline(y=0, color='black', linewidth=0.5)
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add value labels
            for bar, val in zip(bars, returns):
                y_pos = bar.get_height() + (max(returns)*0.02 if val >= 0 else min(returns)*0.02)
                ax.text(bar.get_x() + bar.get_width()/2, y_pos,
                       f'{val:+.1f}%', ha='center', va='bottom' if val >= 0 else 'top',
                       fontsize=8, fontweight='bold')
    
    # Remove empty subplot
    if len(tickers) < 8:
        fig.delaxes(axes[7])
    
    plt.suptitle('Hybrid Strategy vs Mean Reversion vs Buy & Hold — 5 Year Performance', fontsize=14, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hybrid_strategy_comparison.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to: {chart_path}")


if __name__ == "__main__":
    main()

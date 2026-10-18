"""
Market-Aware Hybrid Strategy Engine
Incorporates region/industry-specific parameters from research.

Regions: US, Korea, NZ/Australia
Industries: Tech, Semiconductor (Memory), Semiconductor (Logic/GPU)
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.trading_strategy_engine import (
    BacktestEngine, fetch_data
)


# ===================== MARKET CONFIGURATIONS =====================

MARKET_CONFIGS = {
    "US_TECH": {
        "region": "US",
        "industry": "Tech",
        "adx_lookback": 14,
        "adx_threshold": 33,  # Raised from 30 to 33 (high trend environment Oct 2026)
        "adx_transition_low": 20,
        "mr_lookback": 20,
        "mr_num_std": 2.0,
        "trend_ma": 50,
        "atr_lookback": 14,
    },
    "KOREA": {
        "region": "Korea",
        "industry": "Semiconductor",
        "adx_lookback": 10,  # Faster for Korean trends
        "adx_threshold": 18,  # Lower threshold — Korean trends start earlier
        "adx_transition_low": 15,
        "mr_lookback": 10,  # Faster adaptation
        "mr_num_std": 2.5,  # Wider bands for fat tails
        "trend_ma": 50,
        "atr_lookback": 14,
    },
    "SEMICONDUCTOR_MEMORY": {
        "region": "US",
        "industry": "Semiconductor/Memory",
        "adx_lookback": 14,
        "adx_threshold": 25,
        "adx_transition_low": 20,
        "mr_lookback": 20,
        "mr_num_std": 2.0,
        "trend_ma": 50,
        "atr_lookback": 14,
    },
    "SEMICONDUCTOR_LOGIC": {
        "region": "US",
        "industry": "Semiconductor/Logic",
        "adx_lookback": 14,
        "adx_threshold": 30,
        "adx_transition_low": 20,
        "mr_lookback": 20,
        "mr_num_std": 2.0,
        "trend_ma": 50,
        "atr_lookback": 14,
    },
    "NZ_AUS": {
        "region": "NZ/Australia",
        "industry": "Small Cap Growth",
        "adx_lookback": 14,
        "adx_threshold": 25,
        "adx_transition_low": 20,
        "mr_lookback": 20,
        "mr_num_std": 2.0,
        "trend_ma": 50,
        "atr_lookback": 14,
    },
}


# ===================== Helper Functions =====================

def _exit_persistence(adx_val):
    """Regime-dependent exit persistence: 5d trending (ADX>33), 4d ranging (ADX<20), linear between."""
    if pd.isna(adx_val):
        return 4.0
    if adx_val > 33:
        return 5.0
    elif adx_val < 20:
        return 4.0
    else:
        return 4.0 + (adx_val - 20.0) / 13.0


def _entry_persistence(regime):
    """2-day entry persistence in trends, 3-day in ranging."""
    if regime == "trending":
        return 2
    elif regime == "ranging":
        return 3
    else:
        return 2


def _max_trades_per_week(regime):
    """Regime-dependent frequency cap: 2-4 trades/week."""
    if regime == "trending":
        return 2
    elif regime == "ranging":
        return 4
    else:
        return 3


# ===================== MARKET-AWARE STRATEGY =====================

class MarketAwareHybridStrategy:
    """
    Hybrid strategy with market-specific parameters.
    Automatically detects regime and applies appropriate logic.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.region = config.get("region", "US")
        self.industry = config.get("industry", "Tech")
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ADX with configurable lookback."""
        n = self.config["adx_lookback"]
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        atr = tr.rolling(n).mean()
        atr_safe = atr.replace(0, np.nan)
        plus_di = 100 * (plus_dm.rolling(n).mean() / atr_safe)
        minus_di = 100 * (minus_dm.rolling(n).mean() / atr_safe)
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = 100 * abs(plus_di - minus_di) / di_sum
        adx = dx.rolling(n).mean()
        
        return adx
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR with configurable lookback."""
        n = self.config["atr_lookback"]
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(n).mean()
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Calculate indicators
        df['adx'] = self._calculate_adx(df)
        df['atr'] = self._calculate_atr(df)
        df['trend_ma'] = df['Close'].rolling(self.config["trend_ma"]).mean()

        # Round-4 additional indicators
        df['ma20'] = df['Close'].rolling(20).mean()
        df['ma200'] = df['Close'].rolling(200).mean()

        # RSI for exit confirmation
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)

        # 20-day momentum and slope
        df['momentum_20d'] = df['Close'].pct_change(20)
        df['momentum_slope'] = df['momentum_20d'].diff(5)

        # 12-month momentum for trend-strength override
        df['momentum_12m'] = df['Close'].pct_change(252)

        # Annualized volatility (20-day rolling)
        daily_returns = df['Close'].pct_change()
        df['volatility'] = daily_returns.rolling(20).std() * np.sqrt(252)

        # Bollinger Bands
        df['sma'] = df['Close'].rolling(self.config["mr_lookback"]).mean()
        df['std'] = df['Close'].rolling(self.config["mr_lookback"]).std()
        df['upper_band'] = df['sma'] + self.config["mr_num_std"] * df['std']
        df['lower_band'] = df['sma'] - self.config["mr_num_std"] * df['std']
        bb_range = df['upper_band'] - df['lower_band']
        df['pct_b'] = (df['Close'] - df['lower_band']) / bb_range.replace(0, np.nan)
        df['pct_b'] = df['pct_b'].fillna(0.5)

        # ADX slope (rising or falling)
        df['adx_slope'] = df['adx'].diff(5)

        # Regime detection
        adx_high = self.config["adx_threshold"]
        adx_low = self.config["adx_transition_low"]

        df['regime'] = "transition"  # Default
        df.loc[df['adx'] > adx_high, 'regime'] = "trending"
        df.loc[df['adx'] < adx_low, 'regime'] = "ranging"

        # Generate signals with round-4 persistence and overrides
        signals = []
        position = 0
        exit_counter = 0
        entry_counter = 0

        for i in range(len(df)):
            row = df.iloc[i]
            regime = row['regime']
            adx_val = row['adx']

            req_exit_persist = _exit_persistence(adx_val)
            req_entry_persist = _entry_persistence(regime)

            # Frequency cap: check trades in last 5 bars (approx 1 week)
            recent = signals[-5:] if len(signals) >= 5 else signals
            trades_this_week = sum(1 for s in recent if s != 0)
            freq_cap = _max_trades_per_week(regime)
            freq_ok = trades_this_week < freq_cap

            if position == 0:
                # Look for entry
                entry_signal = False
                if regime == "trending":
                    if row['Close'] > row['trend_ma'] and row['adx_slope'] > 0:
                        entry_signal = True
                elif regime == "ranging":
                    if row['pct_b'] < 0.05:
                        entry_signal = True

                if entry_signal:
                    # Volatility-scaled momentum bypass
                    mom_20d = row['momentum_20d']
                    vol = row['volatility']
                    slope = row['momentum_slope']

                    bypass = False
                    if not pd.isna(mom_20d) and not pd.isna(vol) and not pd.isna(slope):
                        if vol > 0.60:
                            mom_thresh = 0.12
                        else:
                            mom_thresh = 0.15
                        if mom_20d > mom_thresh and slope > 0:
                            bypass = True

                    if bypass and freq_ok:
                        signals.append(1)
                        position = 1
                        entry_counter = 0
                    elif freq_ok:
                        entry_counter += 1
                        if entry_counter >= req_entry_persist:
                            signals.append(1)
                            position = 1
                            entry_counter = 0
                        else:
                            signals.append(0)
                    else:
                        entry_counter = 0
                        signals.append(0)
                else:
                    entry_counter = 0
                    signals.append(0)
            else:
                # Look for exit with persistence and trend override
                exit_signal = False

                # Graduated trend override
                if adx_val > 40:
                    exit_allowed = True
                elif adx_val > 33:
                    exit_allowed = (row['rsi'] < 40) or (row['Close'] < row['ma20'])
                else:
                    mom_12m = row['momentum_12m']
                    if not pd.isna(mom_12m) and mom_12m > 0.50 and row['Close'] > row['ma200']:
                        exit_allowed = False
                    else:
                        exit_allowed = True

                if exit_allowed:
                    if regime == "trending":
                        if row['pct_b'] > 0.95:
                            exit_signal = True
                    elif regime == "ranging":
                        if row['pct_b'] > 0.95:
                            exit_signal = True
                    else:
                        exit_signal = True

                if exit_signal:
                    exit_counter += 1
                    if exit_counter >= req_exit_persist:
                        signals.append(-1)
                        position = 0
                        exit_counter = 0
                    else:
                        signals.append(0)
                else:
                    exit_counter = 0
                    signals.append(0)

        df['signal'] = signals
        return df


# ===================== BACKTEST WITH MARKET CONFIG =====================

def run_market_aware_backtest(ticker: str, config_name: str, period: str = "5y"):
    """Run market-aware strategy on a ticker."""
    config = MARKET_CONFIGS[config_name]
    data = fetch_data(ticker, period)
    engine = BacktestEngine(initial_capital=100_000, commission=0.001)
    strategy = MarketAwareHybridStrategy(config)
    result = engine.run(data, strategy, ticker, f"Market-Aware ({config_name})")
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


def main():
    # Define which strategy to use for each stock
    stock_configs = [
        ("RKLB", "Rocket Lab", "NZ_AUS"),
        ("NVDA", "NVIDIA", "SEMICONDUCTOR_LOGIC"),
        ("MU", "Micron", "SEMICONDUCTOR_MEMORY"),
        ("AMD", "AMD", "SEMICONDUCTOR_LOGIC"),
        ("INTC", "Intel", "US_TECH"),
        ("005930.KS", "Samsung", "KOREA"),
        ("GOOGL", "Alphabet/Google", "US_TECH"),
    ]
    
    period = "5y"
    
    print("=" * 100)
    print("  MARKET-AWARE HYBRID STRATEGY BACKTEST")
    print("  Region/Industry-Specific Parameters from Research")
    print("=" * 100)
    
    all_results = {}
    
    for ticker, name, config_name in stock_configs:
        print(f"\n{'─'*100}")
        print(f"  {name} ({ticker}) — Config: {config_name}")
        print(f"{'─'*100}")
        
        try:
            # Market-aware strategy
            ma_result, data = run_market_aware_backtest(ticker, config_name, period)
            print(ma_result.summary())
            
            # Buy & Hold
            bh = run_buy_and_hold(data, ticker)
            print(f"\n  Buy & Hold:")
            print(f"    Total Return:      {bh['total_return']:+.2f}%")
            print(f"    Sharpe:           {bh['sharpe']:.3f}")
            print(f"    Max Drawdown:     {bh['max_dd']:.2f}%")
            
            all_results[ticker] = {
                'name': name,
                'config': config_name,
                'market_aware': {
                    'total_return': round(ma_result.total_return_pct, 2),
                    'ann_return': round(ma_result.annualized_return_pct, 2),
                    'sharpe': round(ma_result.sharpe_ratio, 3),
                    'max_dd': round(ma_result.max_drawdown_pct, 2),
                    'num_trades': ma_result.num_trades,
                    'win_rate': round(ma_result.win_rate, 4),
                    'avg_trade_return': round(ma_result.avg_trade_return, 2),
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
    print("\n\n" + "=" * 100)
    print("  SUMMARY: MARKET-AWARE vs BUY & HOLD")
    print("=" * 100)
    print(f"{'Stock':<20} {'Config':<25} {'B&H Return':>12} {'MA Return':>12} {'B&H Sharpe':>12} {'MA Sharpe':>12} {'B&H MaxDD':>12} {'MA MaxDD':>12}")
    print("-" * 100)
    
    for ticker, name, config_name in stock_configs:
        if ticker in all_results and 'error' not in all_results[ticker]:
            r = all_results[ticker]
            bh = r['buy_and_hold']
            ma = r['market_aware']
            print(f"{name:<20} {config_name:<25} {bh['total_return']:>+11.2f}% {ma['total_return']:>+11.2f}% {bh['sharpe']:>11.3f} {ma['sharpe']:>11.3f} {bh['max_dd']:>+11.2f}% {ma['max_dd']:>+11.2f}%")
    
    print("=" * 100)
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "market_aware_results.json")
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    # Create comparison chart
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    axes = axes.flatten()
    
    for idx, (ticker, name, config_name) in enumerate(stock_configs):
        if ticker in all_results and 'error' not in all_results[ticker]:
            ax = axes[idx]
            r = all_results[ticker]
            
            strategies = ['Buy & Hold', 'Market-Aware']
            returns = [r['buy_and_hold']['total_return'], r['market_aware']['total_return']]
            colors = ['#757575', '#9C27B0']
            
            bars = ax.bar(strategies, returns, color=colors, alpha=0.8, edgecolor='black')
            ax.set_title(f'{name}\n({config_name})', fontsize=10, fontweight='bold')
            ax.set_ylabel('Total Return %')
            ax.axhline(y=0, color='black', linewidth=0.5)
            ax.grid(True, alpha=0.3, axis='y')
            
            for bar, val in zip(bars, returns):
                y_pos = bar.get_height() + (max(returns)*0.02 if val >= 0 else min(returns)*0.02)
                ax.text(bar.get_x() + bar.get_width()/2, y_pos,
                       f'{val:+.1f}%', ha='center', va='bottom' if val >= 0 else 'top',
                       fontsize=8, fontweight='bold')
    
    if len(stock_configs) < 8:
        fig.delaxes(axes[7])
    
    plt.suptitle('Market-Aware Strategy vs Buy & Hold — Region/Industry-Specific Parameters', fontsize=14, fontweight='bold')
    plt.tight_layout()
    chart_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_aware_comparison.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to: {chart_path}")


if __name__ == "__main__":
    main()

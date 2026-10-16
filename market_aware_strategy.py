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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trading_strategy_engine import (
    BacktestEngine, MeanReversionStrategy, fetch_data, Trade
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
        "stop_loss_atr_mult": 2.5,
        "trailing_stop_atr_mult": 2.5,
        "max_position_pct": 0.15,
        "earnings_pause_days": 2,
        "volatility_filter_percentile": 90,
        "transition_filter": True,  # Don't trade in transition — wait for confirmation
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
        "stop_loss_atr_mult": 1.5,  # Tighter due to gap risk
        "trailing_stop_atr_mult": 2.0,
        "max_position_pct": 0.10,  # Smaller due to extreme volatility
        "earnings_pause_days": 2,
        "volatility_filter_percentile": 85,
        "gap_threshold": 0.02,  # 2% gap = stand aside
        "circuit_breaker_protocol": True,
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
        "stop_loss_atr_mult": 2.5,
        "trailing_stop_atr_mult": 2.5,
        "max_position_pct": 0.15,
        "cycle_detection": True,  # Use memory price indicators
        "earnings_pause_days": 2,
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
        "stop_loss_atr_mult": 3.0,  # Wider for high-beta logic stocks
        "trailing_stop_atr_mult": 3.0,
        "max_position_pct": 0.12,
        "momentum_preference": True,  # Prefer trend following over mean reversion
        "earnings_pause_days": 2,
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
        "stop_loss_atr_mult": 2.5,
        "trailing_stop_atr_mult": 2.5,
        "max_position_pct": 0.025,  # Much smaller — extreme volatility
        "risk_per_trade": 0.01,  # 1% risk per trade
        "rr_minimum": 3.0,  # 3:1 reward-to-risk
        "holding_period_max": 365,  # Days
        "earnings_pause_days": 2,
    },
}


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
        plus_di = 100 * (plus_dm.rolling(n).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(n).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
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
        
        # Bollinger Bands
        df['sma'] = df['Close'].rolling(self.config["mr_lookback"]).mean()
        df['std'] = df['Close'].rolling(self.config["mr_lookback"]).std()
        df['upper_band'] = df['sma'] + self.config["mr_num_std"] * df['std']
        df['lower_band'] = df['sma'] - self.config["mr_num_std"] * df['std']
        df['pct_b'] = (df['Close'] - df['lower_band']) / (df['upper_band'] - df['lower_band'])
        
        # ADX slope (rising or falling)
        df['adx_slope'] = df['adx'].diff(5)
        
        # Regime detection
        adx_high = self.config["adx_threshold"]
        adx_low = self.config["adx_transition_low"]
        
        df['regime'] = "transition"  # Default
        df.loc[df['adx'] > adx_high, 'regime'] = "trending"
        df.loc[df['adx'] < adx_low, 'regime'] = "ranging"
        
        # Generate signals based on regime and market config
        signals = []
        position = 0
        
        for i in range(len(df)):
            row = df.iloc[i]
            regime = row['regime']
            
            if position == 0:
                # Look for entry
                if regime == "trending":
                    # Trending: buy if price > trend MA and ADX rising
                    if row['Close'] > row['trend_ma'] and row['adx_slope'] > 0:
                        signals.append(1)
                        position = 1
                    else:
                        signals.append(0)
                elif regime == "ranging":
                    # Ranging: mean reversion — buy oversold
                    if row['pct_b'] < 0.05:
                        signals.append(1)
                        position = 1
                    else:
                        signals.append(0)
                else:
                    # Transition: reduce size or wait
                    signals.append(0)
            else:
                # Look for exit
                if regime == "trending":
                    # Hold in trending regime
                    signals.append(0)
                elif regime == "ranging":
                    # Mean reversion exit: sell overbought
                    if row['pct_b'] > 0.95:
                        signals.append(-1)
                        position = 0
                    else:
                        signals.append(0)
                else:
                    # Transition: exit to be safe
                    signals.append(-1)
                    position = 0
        
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
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_aware_results.json")
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

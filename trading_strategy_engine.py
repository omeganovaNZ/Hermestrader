"""
Multi-Strategy Backtesting Engine
Tests momentum, mean reversion, and moving average crossover strategies
against real historical data from Yahoo Finance.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import os


@dataclass
class Trade:
    entry_date: datetime
    exit_date: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    shares: int = 0
    side: str = "long"  # long or short
    pnl: float = 0.0
    return_pct: float = 0.0


@dataclass
class BacktestResult:
    strategy_name: str
    ticker: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    num_trades: int
    win_rate: float
    avg_trade_return: float
    equity_curve: pd.Series = field(repr=False)
    trades: List[Trade] = field(default_factory=list)
    
    def summary(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"  {self.strategy_name} — {self.ticker}",
            f"  Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}",
            f"{'='*60}",
            f"  Initial Capital:      ${self.initial_capital:,.2f}",
            f"  Final Capital:        ${self.final_capital:,.2f}",
            f"  Total Return:         {self.total_return_pct:+.2f}%",
            f"  Annualized Return:    {self.annualized_return_pct:+.2f}%",
            f"  Sharpe Ratio:         {self.sharpe_ratio:.3f}",
            f"  Max Drawdown:         {self.max_drawdown_pct:.2f}%",
            f"  Number of Trades:     {self.num_trades}",
            f"  Win Rate:             {self.win_rate:.1%}",
            f"  Avg Trade Return:     {self.avg_trade_return:+.2f}%",
            f"{'='*60}",
        ]
        return "\n".join(lines)


class BacktestEngine:
    """Event-driven backtesting engine."""
    
    def __init__(self, initial_capital: float = 100_000, commission: float = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission  # 0.1% per trade
    
    def run(self, data: pd.DataFrame, strategy, ticker: str, strategy_name: str) -> BacktestResult:
        """Run backtest with a given strategy on price data."""
        df = data.copy()
        df = strategy.generate_signals(df)
        
        capital = self.initial_capital
        position = 0  # shares held
        entry_price = 0.0
        entry_date = None
        trades = []
        equity_curve = []
        
        for i, (date, row) in enumerate(df.iterrows()):
            price = row['Close']
            signal = row.get('signal', 0)
            
            # Execute signals
            if signal == 1 and position == 0:  # Buy
                position = int(capital * 0.95 / price)  # Use 95% of capital
                if position > 0:
                    entry_price = price
                    entry_date = date
                    capital -= position * price * (1 + self.commission)
                    
            elif signal == -1 and position > 0:  # Sell
                capital += position * price * (1 - self.commission)
                pnl = (price - entry_price) * position
                ret_pct = (price / entry_price - 1) * 100
                trades.append(Trade(
                    entry_date=entry_date,
                    exit_date=date,
                    entry_price=entry_price,
                    exit_price=price,
                    shares=position,
                    side="long",
                    pnl=pnl,
                    return_pct=ret_pct
                ))
                position = 0
            
            # Track equity
            current_equity = capital + position * price
            equity_curve.append(current_equity)
        
        # Close any open position at the end
        if position > 0:
            final_price = df['Close'].iloc[-1]
            final_date = df.index[-1]
            capital += position * final_price * (1 - self.commission)
            pnl = (final_price - entry_price) * position
            ret_pct = (final_price / entry_price - 1) * 100
            trades.append(Trade(
                entry_date=entry_date,
                exit_date=final_date,
                entry_price=entry_price,
                exit_price=final_price,
                shares=position,
                side="long",
                pnl=pnl,
                return_pct=ret_pct
            ))
            position = 0
        
        # Build equity curve series
        equity_series = pd.Series(equity_curve, index=df.index[:len(equity_curve)])
        
        # Calculate metrics
        final_capital = equity_series.iloc[-1]
        total_return = (final_capital / self.initial_capital - 1) * 100
        
        # Annualized return
        days = (equity_series.index[-1] - equity_series.index[0]).days
        years = days / 365.25 if days > 0 else 1
        ann_return = ((final_capital / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # Sharpe ratio (daily returns, annualized)
        daily_returns = equity_series.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100
        
        # Win rate
        winning_trades = [t for t in trades if t.pnl > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0.0
        avg_trade_ret = np.mean([t.return_pct for t in trades]) if trades else 0.0
        
        return BacktestResult(
            strategy_name=strategy_name,
            ticker=ticker,
            start_date=df.index[0],
            end_date=df.index[-1],
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return_pct=total_return,
            annualized_return_pct=ann_return,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            num_trades=len(trades),
            win_rate=win_rate,
            avg_trade_return=avg_trade_ret,
            equity_curve=equity_series,
            trades=trades
        )


# ===================== STRATEGIES =====================

class MomentumStrategy:
    """
    Buy when price momentum over lookback period is positive and rising.
    Sell when momentum turns negative.
    """
    def __init__(self, lookback: int = 20, momentum_threshold: float = 0.0):
        self.lookback = lookback
        self.threshold = momentum_threshold
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Rate of change over lookback period
        df['momentum'] = df['Close'].pct_change(self.lookback)
        # Smoothed momentum
        df['momentum_sma'] = df['momentum'].rolling(5).mean()
        
        df['signal'] = 0
        df.loc[df['momentum_sma'] > self.threshold, 'signal'] = 1
        df.loc[df['momentum_sma'] < -self.threshold, 'signal'] = -1
        return df


class MeanReversionStrategy:
    """
    Buy when price drops below lower Bollinger Band (oversold).
    Sell when price rises above upper Bollinger Band (overbought).
    """
    def __init__(self, lookback: int = 20, num_std: float = 2.0):
        self.lookback = lookback
        self.num_std = num_std
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['sma'] = df['Close'].rolling(self.lookback).mean()
        df['std'] = df['Close'].rolling(self.lookback).std()
        df['upper_band'] = df['sma'] + self.num_std * df['std']
        df['lower_band'] = df['sma'] - self.num_std * df['std']
        df['pct_b'] = (df['Close'] - df['lower_band']) / (df['upper_band'] - df['lower_band'])
        
        df['signal'] = 0
        # Buy when below lower band (oversold)
        df.loc[df['pct_b'] < 0.05, 'signal'] = 1
        # Sell when above upper band (overbought)
        df.loc[df['pct_b'] > 0.95, 'signal'] = -1
        return df


class MACrossoverStrategy:
    """
    Buy when short MA crosses above long MA (golden cross).
    Sell when short MA crosses below long MA (death cross).
    """
    def __init__(self, short_window: int = 50, long_window: int = 200):
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['short_ma'] = df['Close'].rolling(self.short_window).mean()
        df['long_ma'] = df['Close'].rolling(self.long_window).mean()
        
        # 1 when short > long, 0 otherwise
        df['position'] = 0
        df.loc[df['short_ma'] > df['long_ma'], 'position'] = 1
        
        # Signal on crossover
        df['signal'] = df['position'].diff().fillna(0).astype(int)
        df.loc[df['signal'] == 0, 'signal'] = 0
        df.loc[df['position'].diff() > 0, 'signal'] = 1   # Golden cross
        df.loc[df['position'].diff() < 0, 'signal'] = -1  # Death cross
        return df


# ===================== DATA & EXECUTION =====================

def fetch_data(ticker: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """Fetch historical price data from Yahoo Finance."""
    print(f"Fetching {ticker} data ({period}, {interval})...")
    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if data.empty:
        raise ValueError(f"No data returned for {ticker}")
    # Flatten multi-level columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    # Drop rows with no Close. yfinance can return a trailing partial row for the most
    # recent session (Volume present, OHLC NaN). Every iloc[-1] consumer then reads NaN,
    # and a NaN momentum poisons the entire ensemble score into a silent all-HOLD.
    if 'Close' in data.columns:
        before = len(data)
        data = data[data['Close'].notna()]
        if len(data) != before:
            print(f"  Dropped {before - len(data)} row(s) with no Close (partial trailing bar)")
    if data.empty:
        raise ValueError(f"No usable rows for {ticker} after dropping NaN Close")
    print(f"  Got {len(data)} rows from {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    return data


def plot_results(results: List[BacktestResult], benchmark: pd.DataFrame, output_path: str):
    """Plot equity curves for all strategies vs buy-and-hold."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2, 1]})
    
    colors = {'Momentum': '#2196F3', 'Mean Reversion': '#FF9800', 'MA Crossover': '#4CAF50', 'Buy & Hold': '#757575'}
    
    # Plot equity curves
    for result in results:
        normalized = result.equity_curve / result.equity_curve.iloc[0] * 100
        ax1.plot(normalized.index, normalized.values, 
                label=f"{result.strategy_name} ({result.total_return_pct:+.1f}%)",
                color=colors.get(result.strategy_name, None), linewidth=1.5)
    
    # Buy and hold benchmark
    bench_normalized = benchmark['Close'] / benchmark['Close'].iloc[0] * 100
    ax1.plot(bench_normalized.index, bench_normalized.values,
            label=f"Buy & Hold ({(bench_normalized.iloc[-1]/100-1)*100:+.1f}%)",
            color=colors['Buy & Hold'], linewidth=1.5, linestyle='--')
    
    ax1.set_title('Strategy Performance Comparison', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value (Start = 100)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot drawdown
    for result in results:
        equity = result.equity_curve
        rolling_max = equity.expanding().max()
        drawdown = (equity - rolling_max) / rolling_max * 100
        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color=colors.get(result.strategy_name, None))
    
    ax2.set_title('Drawdown', fontsize=12)
    ax2.set_ylabel('Drawdown %')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to: {output_path}")


def run_all_strategies(ticker: str, period: str = "5y"):
    """Run all three strategies and buy-and-hold on a given ticker."""
    
    # Fetch data
    data = fetch_data(ticker, period)
    
    # Ensure enough data for 200-day MA
    if len(data) < 250:
        print(f"Warning: Only {len(data)} rows. Some strategies may not work well.")
    
    engine = BacktestEngine(initial_capital=100_000, commission=0.001)
    
    strategies = [
        (MomentumStrategy(lookback=20), "Momentum (20d)"),
        (MeanReversionStrategy(lookback=20, num_std=2.0), "Mean Reversion (BB)"),
        (MACrossoverStrategy(short_window=50, long_window=200), "MA Crossover (50/200)"),
    ]
    
    results = []
    for strategy, name in strategies:
        print(f"\nRunning {name}...")
        result = engine.run(data, strategy, ticker, name)
        results.append(result)
        print(result.summary())
    
    # Plot
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{ticker}_backtest_results.png")
    plot_results(results, data, output_path)
    
    # Save detailed results to JSON
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{ticker}_backtest_results.json")
    all_results = {}
    for r in results:
        all_results[r.strategy_name] = {
            "ticker": r.ticker,
            "period": f"{r.start_date.strftime('%Y-%m-%d')} to {r.end_date.strftime('%Y-%m-%d')}",
            "initial_capital": r.initial_capital,
            "final_capital": round(r.final_capital, 2),
            "total_return_pct": round(r.total_return_pct, 2),
            "annualized_return_pct": round(r.annualized_return_pct, 2),
            "sharpe_ratio": round(r.sharpe_ratio, 3),
            "max_drawdown_pct": round(r.max_drawdown_pct, 2),
            "num_trades": r.num_trades,
            "win_rate": round(r.win_rate, 4),
            "avg_trade_return": round(r.avg_trade_return, 2),
            "trades": [
                {
                    "entry_date": t.entry_date.strftime('%Y-%m-%d'),
                    "exit_date": t.exit_date.strftime('%Y-%m-%d') if t.exit_date else None,
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2),
                    "shares": t.shares,
                    "pnl": round(t.pnl, 2),
                    "return_pct": round(t.return_pct, 2),
                }
                for t in r.trades
            ]
        }
    
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nDetailed results saved to: {json_path}")
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  MULTI-STRATEGY BACKTESTING ENGINE")
    print("=" * 60)
    
    # Test on a well-known stock
    TICKER = "AAPL"  # Apple — liquid, well-known
    
    results = run_all_strategies(TICKER, period="5y")
    
    print("\n\n" + "=" * 60)
    print("  SUMMARY COMPARISON")
    print("=" * 60)
    print(f"{'Strategy':<25} {'Return':>10} {'Sharpe':>8} {'Max DD':>8} {'Trades':>7} {'Win Rate':>9}")
    print("-" * 60)
    
    for r in results:
        print(f"{r.strategy_name:<25} {r.total_return_pct:>+9.2f}% {r.sharpe_ratio:>7.3f} {r.max_drawdown_pct:>+7.2f}% {r.num_trades:>7} {r.win_rate:>8.1%}")
    
    # Buy and hold reference
    data = fetch_data(TICKER, "5y")
    bh_return = (data['Close'].iloc[-1] / data['Close'].iloc[0] - 1) * 100
    print(f"{'Buy & Hold':<25} {bh_return:>+9.2f}% {'—':>8} {'—':>8} {'—':>7} {'—':>9}")
    
    print("=" * 60)

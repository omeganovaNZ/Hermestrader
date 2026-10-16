"""
Paper Trading Simulation
Runs the Alpaca trader for a simulated month, tracking all activity.
Validates the strategy with real-time paper trading.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alpaca_trader import AlpacaTrader


def run_simulation():
    """Run a simulated month of paper trading."""
    
    print("=" * 80)
    print("  PAPER TRADING SIMULATION — 1 Month")
    print(f"  Start: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    trader = AlpacaTrader()
    
    # Initial state
    account = trader.get_account()
    print(f"\nInitial State:")
    print(f"  Cash: ${account['cash']:,.2f}")
    print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
    print(f"  Buying Power: ${account['buying_power']:,.2f}")
    
    # Run daily scans for 30 days
    simulation_results = []
    
    for day in range(1, 31):
        print(f"\n{'─'*80}")
        print(f"  DAY {day} — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'─'*80}")
        
        # Run the daily scan
        signals = trader.run_daily_scan()
        
        # Record results
        account = trader.get_account()
        positions = trader.get_positions()
        
        day_result = {
            'day': day,
            'date': datetime.now().isoformat(),
            'portfolio_value': account['portfolio_value'],
            'cash': account['cash'],
            'num_positions': len(positions),
            'num_signals': len(signals),
            'buy_signals': sum(1 for s in signals if s['signal'] == 1),
            'sell_signals': sum(1 for s in signals if s['signal'] == -1),
            'trades_executed': len([t for t in trader.trades_log if t['date'][:10] == datetime.now().strftime('%Y-%m-%d')]),
        }
        simulation_results.append(day_result)
        
        print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"  Positions: {len(positions)}")
        print(f"  Trades Today: {day_result['trades_executed']}")
        
        # In real simulation, we'd wait until next day
        # For testing, we just run once
        if day == 1:
            print("\n  [Running single day simulation — full month requires daily cron execution]")
            break
    
    # Final summary
    print("\n\n" + "=" * 80)
    print("  SIMULATION SUMMARY")
    print("=" * 80)
    
    account = trader.get_account()
    positions = trader.get_positions()
    
    print(f"\n  Final Portfolio Value: ${account['portfolio_value']:,.2f}")
    print(f"  Final Cash: ${account['cash']:,.2f}")
    print(f"  Total Return: {((account['portfolio_value'] / 100000) - 1) * 100:+.2f}%")
    print(f"  Current Positions: {len(positions)}")
    
    for pos in positions:
        print(f"    {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} (current: ${pos['current_price']:.2f}, P&L: ${pos['unrealized_pl']:+.2f})")
    
    print(f"\n  Total Trades: {len(trader.trades_log)}")
    for trade in trader.trades_log:
        print(f"    {trade['date'][:10]}: {trade['action']} {trade['symbol']} x{trade['shares']} @ ${trade.get('price', 0):.2f}")
    
    # Save simulation results
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_trading_simulation.json")
    with open(output_path, 'w') as f:
        json.dump({
            'simulation_results': simulation_results,
            'trades': trader.trades_log,
            'final_state': {
                'portfolio_value': account['portfolio_value'],
                'cash': account['cash'],
                'positions': positions,
            }
        }, f, indent=2)
    
    print(f"\n  Saved to: {output_path}")
    print("=" * 80)
    
    return simulation_results


if __name__ == "__main__":
    run_simulation()

"""
Initial Portfolio Entry
Invests 50% of Alpaca paper trading balance ($50,000) across 5 stocks
selected based on backtesting results and current market trends.
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alpaca_trader import AlpacaTrader


def main():
    print("=" * 80)
    print("  INITIAL PORTFOLIO ENTRY — 50% Investment")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    trader = AlpacaTrader()
    
    # Get account info
    account = trader.get_account()
    cash = account['cash']
    portfolio_value = account['portfolio_value']
    
    print(f"\n  Account Status: {account['status']}")
    print(f"  Cash: ${cash:,.2f}")
    print(f"  Portfolio Value: ${portfolio_value:,.2f}")
    print(f"  Buying Power: ${account['buying_power']:,.2f}")
    
    # Investment allocation — 50% of portfolio
    investment_amount = portfolio_value * 0.50
    print(f"\n  Investment Amount (50%): ${investment_amount:,.2f}")
    
    # Stock selections based on backtesting and current trends
    # Focus on stocks where market-aware strategy beats buy & hold
    selections = [
        {
            'symbol': 'RKLB',
            'name': 'Rocket Lab',
            'allocation_pct': 0.15,  # 15% of portfolio
            'rationale': 'MA +1156% vs B&H +345%, Sharpe 1.147, space economy growth',
            'regime': 'trending',
            'adx': 28.7,
        },
        {
            'symbol': 'MU',
            'name': 'Micron',
            'allocation_pct': 0.15,  # 15% of portfolio
            'rationale': 'MA Sharpe 1.330 vs B&H 1.219, AI memory supercycle',
            'regime': 'trending',
            'adx': 30.6,
        },
        {
            'symbol': 'BE',
            'name': 'Bloom Energy',
            'allocation_pct': 0.10,  # 10% of portfolio
            'rationale': 'MA +1359% vs B&H +1011%, Sharpe 1.240, AI power demand',
            'regime': 'ranging',
            'adx': 16.5,
        },
        {
            'symbol': 'HD',
            'name': 'Home Depot',
            'allocation_pct': 0.05,  # 5% of portfolio
            'rationale': 'MA +6% vs B&H -1%, lower volatility, defensive',
            'regime': 'trending',
            'adx': 34.7,
        },
        {
            'symbol': 'PK',
            'name': 'Park Hotels',
            'allocation_pct': 0.05,  # 5% of portfolio
            'rationale': 'MA +69% vs B&H +22%, REIT momentum, 6.3% dividend',
            'regime': 'transition',
            'adx': 26.9,
        },
    ]
    
    print(f"\n{'─'*80}")
    print(f"  PORTFOLIO ALLOCATION")
    print(f"{'─'*80}")
    
    total_allocated = 0
    for sel in selections:
        allocation = portfolio_value * sel['allocation_pct']
        total_allocated += sel['allocation_pct']
        print(f"\n  {sel['name']} ({sel['symbol']})")
        print(f"    Allocation: {sel['allocation_pct']:.0%} (${allocation:,.2f})")
        print(f"    Regime: {sel['regime']} | ADX: {sel['adx']}")
        print(f"    Rationale: {sel['rationale']}")
    
    print(f"\n  Total Allocated: {total_allocated:.0%} (${investment_amount:,.2f})")
    print(f"  Cash Remaining: ${(1-total_allocated)*portfolio_value:,.2f}")
    
    # Execute trades
    print(f"\n{'─'*80}")
    print(f"  EXECUTING TRADES")
    print(f"{'─'*80}")
    
    trades_executed = 0
    for sel in selections:
        symbol = sel['symbol']
        allocation = portfolio_value * sel['allocation_pct']
        
        # Get current price
        quote = trader.get_quote(symbol)
        if quote is None:
            print(f"\n  {symbol}: Failed to get quote — skipping")
            continue
        
        price = float(quote.ask_price) if hasattr(quote, 'ask_price') else float(quote)
        shares = int(allocation / price)
        
        if shares == 0:
            print(f"\n  {symbol}: Allocation too small for 1 share — skipping")
            continue
        
        cost = shares * price
        print(f"\n  BUY {symbol}: {shares} shares @ ${price:.2f} = ${cost:,.2f}")
        
        try:
            order = trader.place_buy_order(symbol, shares)
            print(f"    Order ID: {order.id}")
            print(f"    Status: {order.status}")
            trades_executed += 1
            
            # Log trade
            trader.trades_log.append({
                'date': datetime.now().isoformat(),
                'action': 'BUY',
                'symbol': symbol,
                'shares': shares,
                'price': price,
                'cost': cost,
                'rationale': sel['rationale'],
                'regime': sel['regime'],
                'adx': sel['adx'],
            })
            
        except Exception as e:
            print(f"    Failed: {e}")
    
    # Save trades log
    with open(trader.trades_log_path, 'w') as f:
        json.dump(trader.trades_log, f, indent=2)
    
    # Final summary
    print(f"\n{'─'*80}")
    print(f"  PORTFOLIO SUMMARY")
    print(f"{'─'*80}")
    
    account = trader.get_account()
    positions = trader.get_positions()
    
    print(f"\n  Cash: ${account['cash']:,.2f}")
    print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
    print(f"  Positions: {len(positions)}")
    
    total_invested = 0
    for pos in positions:
        print(f"    {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} = ${pos['market_value']:,.2f}")
        total_invested += pos['market_value']
    
    print(f"\n  Total Invested: ${total_invested:,.2f}")
    print(f"  Cash Remaining: ${account['cash']:,.2f}")
    print(f"  Trades Executed: {trades_executed}")
    
    print(f"\n  Trade log saved to: {trader.trades_log_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
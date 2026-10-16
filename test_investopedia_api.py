"""Test script for Investopedia API connection.
Run this to verify your credentials work with the API.
"""

from InvestopediaApi.ita import Account

email = input("Investopedia email: ")
password = input("Investopedia password: ")

try:
    account = Account(email, password)
    status = account.get_portfolio_status()
    print(f"\nLogin successful!")
    print(f"Account Value: ${status.account_val:,.2f}")
    print(f"Buying Power: ${status.buying_power:,.2f}")
    print(f"Cash: ${status.cash:,.2f}")
    print(f"Annual Return: {status.annual_return:.2f}%")
    
    securities = account.get_current_securities()
    print(f"\nCurrent Holdings: {len(securities.bought)} stocks")
    for stock in securities.bought:
        print(f"  {stock.symbol}: {stock.quantity} shares @ ${stock.purchase_price:.2f} (current: ${stock.current_price:.2f})")
    
    open_trades = account.get_open_trades()
    print(f"\nOpen Trades: {len(open_trades)}")
    for trade in open_trades:
        print(f"  {trade.date_time}: {trade.description} {trade.symbol} x{trade.quantity}")
        
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

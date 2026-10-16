"""Test Alpaca Paper Trading connection.
Reads credentials from alpaca_config.txt — never hardcodes secrets.
"""

import os
import sys

# Read credentials from local config file
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alpaca_config.txt")

API_KEY = None
API_SECRET = None

with open(config_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith("API_KEY="):
            API_KEY = line.split("=", 1)[1]
        elif line.startswith("API_SECRET="):
            API_SECRET = line.split("=", 1)[1]

if not API_KEY or not API_SECRET:
    print("Error: Could not read API credentials from config file")
    sys.exit(1)

print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
print(f"API Secret: {'*' * 20}")

# Test connection
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    
    # Connect to paper trading
    trading_client = TradingClient(API_KEY, API_SECRET, paper=True)
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
    
    # Get account info
    account = trading_client.get_account()
    print(f"\nConnected to Alpaca Paper Trading!")
    print(f"Account Status: {account.status}")
    print(f"Cash: ${float(account.cash):,.2f}")
    print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
    print(f"Buying Power: ${float(account.buying_power):,.2f}")
    
    # Get current positions
    positions = trading_client.get_all_positions()
    print(f"\nCurrent Positions: {len(positions)}")
    for pos in positions:
        print(f"  {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f} (current: ${float(pos.current_price):.2f})")
    
    # Test a quote
    from alpaca.data.requests import StockLatestQuoteRequest
    request = StockLatestQuoteRequest(symbol_or_symbols="AAPL")
    quote = data_client.get_stock_latest_quote(request)
    # Handle different response formats
    if hasattr(quote, 'get'):
        aapl_quote = quote.get('AAPL', quote)
        if hasattr(aapl_quote, 'ask_price'):
            print(f"\nAAPL Quote: ${aapl_quote.ask_price:.2f}")
        else:
            print(f"\nAAPL Quote: {aapl_quote}")
    else:
        print(f"\nAAPL Quote: {quote}")
    
    print("\nConnection test successful!")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

"""
Alpaca Paper Trading System
Connects the market-aware strategy to Alpaca Paper Trading for autonomous trading.
Reads credentials from alpaca_config.txt — never hardcodes secrets.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.market_aware_strategy import MarketAwareHybridStrategy, MARKET_CONFIGS
from src.portfolio_rules import theme_cap_check_safe
from src.fundamentals import fundamental_check_safe


def load_credentials(config_file=None):
    """Load API credentials from a local config file.

    `config_file` is a config FILENAME in the repo root (not a path), defaulting to
    alpaca_config.txt. Each Alpaca paper account has its own key, so running the scanner
    against more than one book means pointing it at that book's own config file.
    """
    filename = config_file or "alpaca_config.txt"
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
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
        raise ValueError(f"Could not read API credentials from config file: {filename}")
    return API_KEY, API_SECRET


class AlpacaTrader:
    """Connects market-aware strategy to Alpaca Paper Trading."""
    
    def __init__(self, config_file=None):
        """`config_file` is an optional config FILENAME selecting which paper account to
        connect to. None = alpaca_config.txt, which is what every existing caller uses."""
        self.config_file = config_file or "alpaca_config.txt"
        self.API_KEY, self.API_SECRET = load_credentials(self.config_file)
        self.trading_client = None
        self.data_client = None
        self.connect()
        
        # Watchlist with strategy configs — refined based on backtesting + screener
        self.watchlist = [
            # High-conviction: MA beats B&H with better Sharpe
            ("RKLB", "Rocket Lab", "NZ_AUS"),           # MA +1156% vs B&H +345%
            ("MU", "Micron", "SEMICONDUCTOR_MEMORY"),   # MA Sharpe 1.330 vs B&H 1.219
            ("BE", "Bloom Energy", "POWER_FOR_AI"),     # MA +1359% vs B&H +1011%; fuel cells sold to data-centre load
            ("PK", "Park Hotels", "US_TECH"),           # MA +69% vs B&H +22%
            ("HD", "Home Depot", "US_TECH"),            # MA +6% vs B&H -1%
            
            # Screener STRONG BUY candidates (Score >= 75)
            ("MRVL", "Marvell Technology", "SEMICONDUCTOR_LOGIC"),  # Score 95
            ("DDOG", "Datadog", "US_TECH"),                         # Score 90
            ("PLTR", "Palantir", "US_TECH"),                        # Score 90
            ("CRWD", "CrowdStrike", "US_TECH"),                     # Score 85
            ("MXL", "MaxLinear", "SEMICONDUCTOR_LOGIC"),            # Score 85
            ("SNOW", "Snowflake", "US_TECH"),                       # Score 80
            ("LLY", "Eli Lilly", "US_TECH"),                        # Score 80
            ("TXG", "10x Genomics", "US_TECH"),                      # Score 80
            ("OKTA", "Okta", "US_TECH"),                            # Score 75
            ("LITE", "Lumentum", "SEMICONDUCTOR_LOGIC"),            # Score 75
            
            # Screener BUY candidates (Score 60-74)
            ("SNPS", "Synopsys", "SEMICONDUCTOR_LOGIC"),            # Score 70
            ("ANET", "Arista Networks", "US_TECH"),                 # Score 70
            ("NET", "Cloudflare", "US_TECH"),                       # Score 70
            ("MRNA", "Moderna", "US_TECH"),                         # Score 70
            ("TSM", "Taiwan Semiconductor", "SEMICONDUCTOR_LOGIC"), # Score 65
            ("SMCI", "Super Micro Computer", "US_TECH"),            # Score 65
            ("VRTX", "Vertex Pharmaceuticals", "US_TECH"),          # Score 65
            ("ASML", "ASML Holding", "SEMICONDUCTOR_LOGIC"),        # Score 60
            ("PANW", "Palo Alto Networks", "US_TECH"),              # Score 60
            ("IOVA", "Iovance", "US_TECH"),                         # Score 60
            ("KOD", "Kodiak Sciences", "US_TECH"),                  # Score 60
            ("SNDK", "Sandisk", "SEMICONDUCTOR_MEMORY"),            # Score 60
            ("CDNS", "Cadence Design", "SEMICONDUCTOR_LOGIC"),      # Score 55
            
            # Existing holdings to monitor
            ("NVDA", "NVIDIA", "SEMICONDUCTOR_LOGIC"),
            ("AMD", "AMD", "SEMICONDUCTOR_LOGIC"),
            ("GOOGL", "Alphabet", "US_TECH"),
            ("XOM", "Exxon Mobil", "US_TECH"),
            ("CVX", "Chevron", "US_TECH"),
            ("NEE", "NextEra Energy", "US_TECH"),
            ("CAT", "Caterpillar", "US_TECH"),
            ("GEV", "GE Vernova", "US_TECH"),
            ("RTX", "RTX Corp", "US_TECH"),
        ]
        
        # Load previous trades log if exists
        self.trades_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "alpaca_trades_log.json")
        self.trades_log = []
        if os.path.exists(self.trades_log_path):
            try:
                with open(self.trades_log_path, 'r') as f:
                    self.trades_log = json.load(f)
            except (ValueError, OSError):
                print("  WARNING: alpaca_trades_log.json unreadable - starting fresh")
                self.trades_log = []
        
        # Risk tolerance: Higher risk OK, but require multiple confirming signals.
        # NOTE: this is NOT currently enforced — the buy path uses a single signal
        # from MarketAwareHybridStrategy. The ensemble screener (ensemble_trader.py)
        # is a separate tool that generates ensemble_score but is not wired into
        # this buy path. This attribute is kept as documentation of intent.
        # Note: min_confirming_signals is defined for documentation but NOT currently enforced
        # Cap on a NEW position's share of account value. Kept BELOW the trim cap
        # (position_manager.max_position_pct = 0.10) so a position is never born over-cap
        # and has room to rise before the cap binds. This attribute used to be dead: it said
        # 0.20 while calculate_position_size hardcoded 0.15 and the trimmer enforced 0.10 -
        # three different caps, none of them agreeing, which is how four positions ended up
        # over-cap on the day they were bought.
        self.max_position_pct = 0.08
        # ENSEMBLE GATE. The standing rule is to act only on multiple independent
        # confirming signals. The buy path used to trade on a single technical layer
        # while `min_confirming_signals` sat unused; this flag turns the rule on.
        self.require_ensemble = True
        self._ensemble = None       # lazily built (trains LightGBM per symbol)
        self._ensemble_cache = {}   # symbol -> (decision, note, live_layers)
        self.ensemble_min_live_layers = 3   # MIN_LIVE_LAYERS
        # CONVICTION TIERS. A flat 8% entry cap treats a high-conviction name the same as
        # a satellite. This maps a symbol to a higher or lower entry cap (all still
        # below the 10% trim cap, so a position is never born over-cap).
        self.conviction_pct = {
            "RKLB": 0.10,   # owner's conviction hold (Neutron)
            "PLTR": 0.10,
            "NTAP": 0.10,
            "MSFT": 0.10,
        }
        self.satellite_pct = 0.04   # default tier for unlisted names
        # The trim cap lives in position_manager; the entry cap must never exceed it,
        # or a position is born over-cap and (since the cap trim only sells winners)
        # can never be corrected. Clamp the tier to it here.
        self.trim_cap_pct = 0.10
        # CASH DRAG. Cash above this share of equity is deployed within `cash_drag_days`
        # rather than left idle (idle cash was measured to cost the cap its point).
        self.cash_drag_pct = 0.10
        self.cash_drag_days = 5
        self.cash_drag_max_names = 5   # cap the number of cash-drag buys
        # NOTE: there used to be a `self.risk_per_trade = 0.03` here. It was never read -
        # calculate_position_size is called without a risk_pct argument - and even if it
        # were wired in it could not change the answer: risking 3% against a 10% stop
        # implies a 30% position, which the 8% entry cap always truncates. Size is
        # determined by the cap. Removed rather than left looking like a live control.

    def connect(self):
        """Connect to Alpaca Paper Trading."""
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        self.trading_client = TradingClient(self.API_KEY, self.API_SECRET, paper=True)
        self.data_client = StockHistoricalDataClient(self.API_KEY, self.API_SECRET)
        print("Connected to Alpaca Paper Trading")
    
    def get_account(self):
        """Get account status."""
        account = self.trading_client.get_account()
        return {
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'equity': float(account.equity),
            'long_market_value': float(account.long_market_value),
            'buying_power': float(account.buying_power),
            'status': str(account.status),
        }
    
    def get_positions(self):
        """Get current positions."""
        positions = self.trading_client.get_all_positions()
        result = []
        for pos in positions:
            result.append({
                'symbol': pos.symbol,
                # float, not int: trims are fractional, so positions go fractional and
                # int() would silently truncate them (5.6 shares -> 5), corrupting every
                # downstream calculation.
                'qty': float(pos.qty),
                'avg_entry_price': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'market_value': float(pos.market_value),
                'unrealized_pl': float(pos.unrealized_pl),
            })
        return result
    
    def get_open_orders(self):
        """Open (unfilled) orders as dicts: {'symbol', 'side', 'qty'}.

        Used to stop a cap trim being placed twice: while a cap-trim sell order
        is still pending the position still looks over-cap, and a cap trim
        carries no ladder rung, so nothing else would prevent the duplicate.
        Returns [] rather than raising if the response is unusable.
        """
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        orders = self.trading_client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
        if not isinstance(orders, (list, tuple)):
            return []
        out = []
        for o in orders:
            qty = getattr(o, 'qty', None)
            out.append({
                'symbol': o.symbol,
                'side': str(getattr(o.side, 'value', o.side)).lower(),
                'qty': float(qty) if qty is not None else 0.0,
            })
        return out

    def get_first_buy_date(self, symbol):
        """Earliest FILLED buy for symbol, or None. Used for the holding-period rule.

        Alpaca's position object carries no open date, so the holding period has to be
        derived from order history. Returns a timezone-aware datetime, or None when it
        cannot be determined - callers must treat None as "unknown" and NOT as "old
        enough", since trimming a position held for less than 6 months is the one thing
        the profit-trim rule forbids.

        Limitation: this is the earliest buy ever filled for the symbol. If a position
        was fully sold and later re-bought, the returned date is older than the current
        holding. That errs toward allowing a trim too early rather than blocking one.
        """
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        orders = self.trading_client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, symbols=[symbol],
                                    limit=500))
        if not isinstance(orders, (list, tuple)):
            return None
        dates = []
        for o in orders:
            if str(getattr(o.side, 'value', o.side)).lower() != 'buy':
                continue
            filled = getattr(o, 'filled_at', None)
            if filled is not None:
                dates.append(filled)
        return min(dates) if dates else None

    def get_historical_data(self, symbol, days=250):
        """Get historical price data from Alpaca."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        
        start = datetime.now() - timedelta(days=days)
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
        )
        bars = self.data_client.get_stock_bars(request)
        
        if symbol not in bars.data or len(bars.data[symbol]) == 0:
            return None
        
        df = pd.DataFrame([{
            'High': bar.high,
            'Low': bar.low,
            'Close': bar.close,
            'Open': bar.open,
            'Volume': bar.volume,
            'Date': bar.timestamp,
        } for bar in bars.data[symbol]])
        
        df.set_index('Date', inplace=True)
        return df
    
    def get_quote(self, symbol):
        """Get current quote for a stock."""
        from alpaca.data.requests import StockLatestQuoteRequest
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = self.data_client.get_stock_latest_quote(request)
        
        if hasattr(quote, 'get'):
            result = quote.get(symbol, quote)
            if result is None:
                return None
            return result
        return quote
    
    def generate_signals(self, symbol, config_name):
        """Generate trading signals using market-aware strategy."""
        # Get historical data
        data = self.get_historical_data(symbol)
        if data is None or len(data) < 50:
            return None
        
        # Apply market-aware strategy
        config = MARKET_CONFIGS[config_name]
        strategy = MarketAwareHybridStrategy(config)
        signals_df = strategy.generate_signals(data)
        
        # Get the latest signal
        latest_signal = signals_df['signal'].iloc[-1]
        latest_row = signals_df.iloc[-1]
        
        return {
            'symbol': symbol,
            'signal': int(latest_signal),
            'regime': latest_row['regime'],
            'adx': float(latest_row['adx']),
            'close': float(latest_row['Close']),
            'trend_ma': float(latest_row['trend_ma']),
            'upper_band': float(latest_row['upper_band']),
            'lower_band': float(latest_row['lower_band']),
            'pct_b': float(latest_row['pct_b']),
        }
    
    def ensemble_gate(self, symbol, name=None, config_name=None):
        """(ok, reason): does `symbol` pass the multi-layer ensemble gate?

        The standing rule is to act only on multiple independent confirming signals.
        This blocks a buy unless the ensemble has at least `ensemble_min_live_layers`
        live layers and its decision is not a SELL. Fails OPEN (returns True with a
        note) when the ensemble cannot be built, so a data outage does not silently
        block every buy — but the skip is reported rather than hidden.
        """
        if symbol in self._ensemble_cache:
            decision, note, live = self._ensemble_cache[symbol]
        else:
            try:
                from src.ensemble_trader import EnsembleTrader
                if self._ensemble is None:
                    self._ensemble = EnsembleTrader()
                cfg = config_name or "US_TECH"
                sig = self._ensemble.generate_ensemble_signal(symbol, cfg, name or symbol)
                decision = sig.get('decision', 'HOLD')
                live = len(sig.get('layers_used', []))
                note = sig.get('decision_note', '')
                self._ensemble_cache[symbol] = (decision, note, live)
            except Exception as e:
                return True, f"ensemble unavailable ({type(e).__name__}: {e}) - gate skipped"
        min_live = int(getattr(self, 'ensemble_min_live_layers', 3))
        if live < min_live:
            return False, f"only {live} live layer(s), need {min_live}"
        if decision in ('SELL', 'STRONG_SELL'):
            return False, f"ensemble decision {decision}: {note}"
        return True, f"ensemble {decision} ({live} live layers)"

    def calculate_position_size(self, symbol, signal, account_value, risk_pct=0.02):
        """Size a new position, capped BELOW the trim cap so it is never born over-cap.

        The cap here used to be a hardcoded 0.15 while the trimmer enforced 0.10, so any
        position sized between 10% and 15% was over-cap the moment it was bought - and
        because the cap trim only ever sells WINNERS, an over-cap position that then went
        down could never be corrected. MRVL (23% of equity and falling), MU, RKLB and DDOG
        all arrived that way, and all four cap-trim orders had to be cancelled rather than
        sold at a loss.

        The cap is now `self.max_position_pct`, deliberately set BELOW the trim cap so a
        position has room to rise before the cap binds. Sizing exactly AT the trim cap would
        mean trimming on the first good day.
        """
        quote = self.get_quote(symbol)
        if quote is None:
            return 0, 0

        price = float(quote.ask_price) if hasattr(quote, 'ask_price') else float(quote)
        if not (price > 0) or price != price:  # NaN-safe: NaN > 0 is False
            return 0, 0

        # Risk-based sizing: risking risk_pct of the account against a 10% stop.
        risk_amount = account_value * risk_pct
        stop_distance = price * 0.10
        shares = int(risk_amount / stop_distance)

        # Cap at the configured position size (below the trim cap). Conviction-tiered:
        # a name on the conviction list may be sized higher (still below the 10% trim
        # cap), a satellite is sized lower. Default is the flat entry cap.
        tier_pct = float(getattr(self, 'conviction_pct', {}).get(symbol, self.max_position_pct))
        tier_pct = min(tier_pct, float(getattr(self, 'trim_cap_pct', 0.10)))
        max_position = account_value * tier_pct
        max_shares = int(max_position / price)
        shares = min(shares, max_shares)

        return shares, price
    
    def place_buy_order(self, symbol, shares, price=None):
        """Place a buy order."""
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        import uuid
        if price is None:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                client_order_id=str(uuid.uuid4()),
            )
        else:
            from alpaca.trading.requests import LimitOrderRequest
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=price,
                client_order_id=str(uuid.uuid4()),
            )
        
        order = self.trading_client.submit_order(order_data)
        return order
    
    def place_sell_order(self, symbol, shares):
        """Place a sell order."""
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        import uuid
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=str(uuid.uuid4()),
        )
        
        order = self.trading_client.submit_order(order_data)
        return order
    
    def run_daily_scan(self):
        """Run daily scan of all watched stocks."""
        print("=" * 80)
        print(f"  ALPACA PAPER TRADING — Daily Scan")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 80)
        
        try:
            account = self.get_account()
        except Exception as e:
            print(f"  ERROR fetching account: {e}")
            return []

        try:
            positions = self.get_positions()
        except Exception as e:
            print(f"  ERROR fetching positions: {e}")
            return []
        
        print(f"\n  Account Status: {account['status']}")
        print(f"  Cash: ${account['cash']:,.2f}")
        print(f"  Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"  Buying Power: ${account['buying_power']:,.2f}")
        print(f"  Current Positions: {len(positions)}")
        
        for pos in positions:
            print(f"    {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f} (current: ${pos['current_price']:.2f}, P&L: ${pos['unrealized_pl']:+.2f})")
        
        print(f"\n{'─'*80}")
        print(f"  SCANNING WATCHLIST...")
        print(f"{'─'*80}")
        
        signals = []
        for ticker, name, config_name in self.watchlist:
            try:
                signal = self.generate_signals(ticker, config_name)
                if signal:
                    signal['name'] = name
                    signal['config_name'] = config_name
                    signals.append(signal)
                    action = "BUY" if signal['signal'] == 1 else "SELL" if signal['signal'] == -1 else "HOLD"
                    print(f"  {name} ({ticker}): {action} | Regime: {signal['regime']} | ADX: {signal['adx']:.1f} | Price: ${signal['close']:.2f}")
            except Exception as e:
                print(f"  {name} ({ticker}): Error - {e}")
        
        # Execute trades based on signals
        print(f"\n{'─'*80}")
        print(f"  EXECUTING TRADES...")
        print(f"{'─'*80}")
        
        trades_executed = 0
        for signal in signals:
            symbol = signal['symbol']
            
            # Check if we already have a position
            existing_position = None
            for pos in positions:
                if pos['symbol'] == symbol:
                    existing_position = pos
                    break
            
            if signal['signal'] == 1:  # Buy signal
                if existing_position is None:
                    # No position, buy
                    # Check for pending buy orders to avoid duplicates
                    try:
                        pending_buys = {o['symbol'] for o in self.get_open_orders()
                                        if str(o.get('side', '')).lower() == 'buy'}
                        if symbol in pending_buys:
                            print(f"  BUY {symbol}: Skipped (buy order already pending)")
                            continue
                    except Exception as e:
                        print(f"  BUY {symbol}: WARNING - could not check pending orders: {e}")
                    # FUNDAMENTALS GATE. The technical screen has no forward edge (the
                    # 2026-04-25 fair test: picks +3.5% vs SPY +7.0%), so a technical buy
                    # signal alone is not enough. Require a verified fundamentals record.
                    fok, fwhy = fundamental_check_safe(symbol)
                    if not fok:
                        print(f"  BUY {symbol}: BLOCKED by the fundamentals gate - {fwhy}")
                        continue

                    # ENSEMBLE GATE. The standing rule is to act only on multiple
                    # independent confirming signals; this is where it is enforced. A
                    # single technical layer is not enough. Skipped (not blocking) when
                    # the ensemble cannot be built, but reported.
                    if self.require_ensemble:
                        eok, ewhy = self.ensemble_gate(symbol, signal.get('name'),
                                                       signal.get('config_name'))
                        if not eok:
                            print(f"  BUY {symbol}: BLOCKED by the ensemble gate - {ewhy}")
                            continue

                    shares, price = self.calculate_position_size(
                        symbol, signal['signal'], account['portfolio_value']
                    )
                    if shares > 0:
                        # THEME (SLEEVE) CAP. The playbook declared a 40% ceiling on the
                        # AI-hardware sleeve and nothing enforced it, which is how that
                        # sleeve reached 75% of long market value. Refuse any order that
                        # would push its theme past the ceiling.
                        #
                        # FAILS CLOSED: theme_cap_check_safe refuses the buy when the check
                        # cannot be evaluated. A risk limit that opens up whenever it fails
                        # is not a limit. It sits outside the order try/except below, so a
                        # failure here cannot be mistaken for a broker rejection.
                        try:
                            ok, why = theme_cap_check_safe(
                                symbol, shares * price, positions, float(account['equity']))
                        except Exception as e:
                            ok, why = False, f"theme cap check crashed: {type(e).__name__}: {e}"
                        if not ok:
                            print(f"  BUY {symbol}: BLOCKED by the theme cap - {why}")
                            continue
                        try:
                            order = self.place_buy_order(symbol, shares)
                            print(f"  BUY {symbol}: {shares} shares  [{why}]")
                            trades_executed += 1
                            # Track the new holding so LATER buys in this SAME scan are
                            # measured against the updated book, not the pre-scan snapshot.
                            # `positions` is fetched once before the loop, so without this
                            # every buy in a scan is checked against the same stale list and
                            # two buys that each pass individually can collectively breach
                            # the theme cap. Only symbol and market_value are needed - that
                            # is all the theme guard reads - so no extra API call is made.
                            positions = positions + [{'symbol': symbol,
                                                      'market_value': shares * price}]
                            self.trades_log.append({
                                'date': datetime.now().isoformat(),
                                'action': 'BUY',
                                'symbol': symbol,
                                'shares': shares,
                                'price': price,
                                'signal': signal,
                            })
                        except Exception as e:
                            print(f"  BUY {symbol}: Failed - {e}")
                    else:
                        print(f"  BUY {symbol}: Skipped (position size too small)")
                else:
                    print(f"  BUY {symbol}: Skipped (already have position)")
                    
            elif signal['signal'] == -1:  # Sell signal
                if existing_position is not None:
                    # WINNERS ONLY. The owner's rule is that invested capital is never
                    # trimmed on weakness. A sell signal on a loser is NOT acted on.
                    pl = float(existing_position.get('unrealized_pl', 0))
                    if pl <= 0:
                        print(f"  SELL {symbol}: BLOCKED - position is down {pl:,.2f} - not selling a loser")
                        continue
                    # Check for pending sell orders to avoid duplicates
                    try:
                        pending_sells = {o['symbol'] for o in self.get_open_orders()
                                         if str(o.get('side', '')).lower() == 'sell'}
                        if symbol in pending_sells:
                            print(f"  SELL {symbol}: Skipped (sell order already pending)")
                            continue
                    except Exception as e:
                        print(f"  SELL {symbol}: WARNING - could not check pending orders: {e}")
                    try:
                        self.place_sell_order(symbol, existing_position['qty'])
                        print(f"  SELL {symbol}: {existing_position['qty']} shares")
                        trades_executed += 1
                        # Remove from positions list so a later signal for the same symbol
                        # in this scan is not incorrectly skipped
                        positions = [p for p in positions if p['symbol'] != symbol]
                        self.trades_log.append({
                            'date': datetime.now().isoformat(),
                            'action': 'SELL',
                            'symbol': symbol,
                            'shares': existing_position['qty'],
                            'price': signal['close'],
                            'signal': signal,
                        })
                    except Exception as e:
                        print(f"  SELL {symbol}: Failed - {e}")
                else:
                    print(f"  SELL {symbol}: Skipped (no position to sell)")
        
        if trades_executed == 0:
            print("  No trades executed.")
        
        # Save trades log
        try:
            _tmp = self.trades_log_path + '.tmp'
            with open(_tmp, 'w') as f:
                json.dump(self.trades_log, f, indent=2)
            os.replace(_tmp, self.trades_log_path)
        except Exception as e:
            print(f"  WARNING: could not save trades log - {e}")
        
        print(f"\n  Trades executed: {trades_executed}")
        print(f"  Total trades in log: {len(self.trades_log)}")
        print("=" * 80)
        
        return signals


def main():
    """Run the daily trading scan."""
    trader = AlpacaTrader()
    signals = trader.run_daily_scan()
    
    # Print summary
    print("\n" + "=" * 80)
    print("  DAILY SCAN COMPLETE")
    print("=" * 80)
    print(f"  Stocks scanned: {len(signals)}")
    print(f"  Buy signals: {sum(1 for s in signals if s['signal'] == 1)}")
    print(f"  Sell signals: {sum(1 for s in signals if s['signal'] == -1)}")
    print(f"  Hold: {sum(1 for s in signals if s['signal'] == 0)}")
    print("=" * 80)


if __name__ == "__main__":
    main()

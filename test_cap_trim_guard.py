"""Tests for the cap-trim duplicate-order guard.

A cap trim is placed with rung=None, so the ladder's `rungs_fired` guard does
not cover it. While a cap-trim sell order is still pending (unfilled) the
position still looks over-cap on the next scan, and a second identical order
would be placed. These tests pin the guard that prevents it:

  1. A pending SELL order for an over-cap symbol suppresses its cap trim.
  2. With no pending order the cap trim is emitted as before.
  3. A pending BUY order must NOT suppress the cap trim.
  4. If the open-orders query fails, trim anyway (fail open) - silently
     refusing to trim would disable the cap entirely.
  5. Only the affected symbol is skipped; other over-cap names still trim.
  6. get_open_orders() parses the SDK order objects, and returns [] rather
     than raising on an unusable response.

The Alpaca client is mocked; nothing touches the network or the order path.
"""
from unittest.mock import MagicMock

from alpaca.trading.enums import OrderSide

from alpaca_trader import AlpacaTrader
from position_manager import PositionManager

EQUITY = 100_000.0          # 10% cap -> $10,000 max market value


def pos(symbol, qty, price):
    return {'symbol': symbol, 'qty': float(qty), 'current_price': float(price),
            'market_value': float(qty) * float(price), 'avg_entry_price': float(price),
            'unrealized_pl': 0.0}


def make_pm(positions, open_orders):
    pm = PositionManager.__new__(PositionManager)      # skip __init__ (connects to Alpaca)
    pm.alpaca = MagicMock()
    pm.alpaca.get_account.return_value = {'equity': EQUITY}
    pm.alpaca.get_positions.return_value = positions
    if isinstance(open_orders, Exception):
        pm.alpaca.get_open_orders.side_effect = open_orders
    else:
        pm.alpaca.get_open_orders.return_value = open_orders
    pm.trim_rules = {'max_position_pct': 0.10}
    return pm


# MRVL 98 @ 227.83 = $22,327 -> 22.3% of equity (over the 10% cap)
OVER_CAP = [pos('MRVL', 98, 227.83)]
# MU 15 @ 878.84 = $13,183 -> 13.2% (also over)
TWO_OVER = OVER_CAP + [pos('MU', 15, 878.84)]

PENDING_SELL = [{'symbol': 'MRVL', 'side': 'sell', 'qty': 55.6052}]


def test_pending_sell_suppresses_cap_trim():
    pm = make_pm(OVER_CAP, PENDING_SELL)
    assert pm.position_cap_signals() == [], "a pending cap trim must not be re-issued"


def test_no_pending_order_still_trims():
    pm = make_pm(OVER_CAP, [])
    sigs = pm.position_cap_signals()
    assert len(sigs) == 1 and sigs[0]['symbol'] == 'MRVL', f"got {sigs}"
    assert sigs[0]['shares_to_sell'] > 0


def test_pending_buy_does_not_suppress():
    pm = make_pm(OVER_CAP, [{'symbol': 'MRVL', 'side': 'buy', 'qty': 5}])
    assert len(pm.position_cap_signals()) == 1, "only a pending SELL should suppress"


def test_open_orders_failure_fails_open():
    pm = make_pm(OVER_CAP, RuntimeError("api down"))
    assert len(pm.position_cap_signals()) == 1, "must trim when open orders are unknown"


def test_only_affected_symbol_is_skipped():
    pm = make_pm(TWO_OVER, PENDING_SELL)
    sigs = pm.position_cap_signals()
    assert [s['symbol'] for s in sigs] == ['MU'], f"got {[s['symbol'] for s in sigs]}"


def test_get_open_orders_parses_sdk_objects():
    trader = AlpacaTrader.__new__(AlpacaTrader)        # skip __init__ (loads creds, connects)
    trader.trading_client = MagicMock()
    o = MagicMock()
    o.symbol, o.side, o.qty = 'MRVL', OrderSide.SELL, 55.6052
    trader.trading_client.get_orders.return_value = [o]
    assert trader.get_open_orders() == [{'symbol': 'MRVL', 'side': 'sell', 'qty': 55.6052}]


def test_get_open_orders_handles_unusable_response():
    trader = AlpacaTrader.__new__(AlpacaTrader)
    trader.trading_client = MagicMock()
    trader.trading_client.get_orders.return_value = {'code': 401, 'message': 'unauthorized'}
    assert trader.get_open_orders() == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

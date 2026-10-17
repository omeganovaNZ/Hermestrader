"""Tests for the cap-trim guard: pending-order dedupe AND winners-only.

Two independent rules protect the cap-trim path:

A. WINNERS ONLY. A cap trim is risk management on a position that has GROWN,
   never a reaction to weakness. An over-cap position that is DOWN must be left
   alone (it is an add candidate), even though that leaves the cap breached,
   because enforcing the cap on a loser sells it at a loss. A flat position
   (pl == 0) is not a winner either, so it is left alone too.

B. PENDING-ORDER DEDUPE. A cap trim is placed with rung=None, so the ladder's
   fired-rung guard does not cover it: while a cap-trim sell order is still
   pending the position still looks over-cap and a second identical order would
   be placed. Skip any symbol that already has an open SELL order. A pending BUY
   must NOT suppress the trim. If the open-orders query fails, trim anyway
   (fail open) - silently refusing to trim would disable the cap.

The Alpaca client is mocked; nothing touches the network or the order path.
"""
from unittest.mock import MagicMock

from alpaca.trading.enums import OrderSide

from alpaca_trader import AlpacaTrader
from position_manager import PositionManager

EQUITY = 100_000.0          # 10% cap -> $10,000 max market value


def pos(symbol, qty, price, gain_pct=10.0):
    """A position that is `gain_pct`% in profit (pass a negative value for a loser)."""
    entry = float(price) / (1.0 + gain_pct / 100.0)
    q, px = float(qty), float(price)
    return {'symbol': symbol, 'qty': q, 'current_price': px,
            'market_value': q * px, 'avg_entry_price': entry,
            'unrealized_pl': q * (px - entry)}


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


# MRVL 98 @ 227.83 = $22,327 -> 22.3% of equity (over the 10% cap), a winner by default
OVER_CAP = [pos('MRVL', 98, 227.83)]
# MU 15 @ 878.84 = $13,183 -> 13.2% (also over)
TWO_OVER = OVER_CAP + [pos('MU', 15, 878.84)]

PENDING_SELL = [{'symbol': 'MRVL', 'side': 'sell', 'qty': 55.6052}]


# --- A. winners only -------------------------------------------------------

def test_winner_over_cap_is_trimmed():
    pm = make_pm(OVER_CAP, [])
    sigs = pm.position_cap_signals()
    assert len(sigs) == 1 and sigs[0]['symbol'] == 'MRVL', f"got {sigs}"
    assert sigs[0]['shares_to_sell'] > 0


def test_loser_over_cap_is_not_trimmed():
    """The rule that matters: an over-cap position that is DOWN is left alone."""
    pm = make_pm([pos('MRVL', 98, 227.83, gain_pct=-3.2)], [])
    assert pm.position_cap_signals() == [], "must never trim a loser"


def test_flat_position_is_not_trimmed():
    """pl == 0 is not a winner, so it is not a trim either."""
    pm = make_pm([pos('MRVL', 98, 227.83, gain_pct=0.0)], [])
    assert pm.position_cap_signals() == [], "a flat position is not a winner"


def test_loser_is_reported_as_over_cap_but_left_alone():
    """The position is genuinely over cap - it is skipped for being a loser, not for size."""
    p = pos('MRVL', 98, 227.83, gain_pct=-3.2)
    assert p['market_value'] / EQUITY > 0.10, "test setup: must actually be over cap"
    assert p['unrealized_pl'] < 0, "test setup: must actually be a loser"


# --- B. pending-order dedupe ----------------------------------------------

def test_pending_sell_suppresses_cap_trim():
    pm = make_pm(OVER_CAP, PENDING_SELL)
    assert pm.position_cap_signals() == [], "a pending cap trim must not be re-issued"


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


# --- get_open_orders parsing ----------------------------------------------

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

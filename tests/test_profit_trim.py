"""Tests for THE profit-trim rule.

A position is trimmed only when ALL FOUR hold:
  1. held LONGER than 6 months
  2. +100% ROI from its reference price
  3. the last 2 days both closed DOWN
  4. still above the 200-day average (a pullback, not a trend break)
...and then it sells 20% of the shares held.

Growth alone never trims. After a trim the reference re-bases to the trim price, so the
next trim needs another +100% from there. These tests pin each condition individually, so
a regression in any one of them fails loudly rather than silently allowing a trim.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.position_manager import PositionManager

RULES = {
    'profit_trim_pct': 1.00,
    'profit_trim_size': 0.20,
    'min_hold_days': 183,
    'pullback_days': 2,
    'trend_ma': 200,
    'max_position_pct': 0.10,
    'add_drawdown': 0.20,
}


def pos(symbol='MRVL', qty=100.0, entry=100.0, price=250.0):
    return {'symbol': symbol, 'qty': float(qty), 'avg_entry_price': float(entry),
            'current_price': float(price), 'market_value': float(qty) * float(price),
            'unrealized_pl': float(qty) * (float(price) - float(entry))}


def uptrend(n=250, base=100.0, step=0.1):
    return [base + i * step for i in range(n)]


def with_down_days(closes, n=2, drop=1.0):
    out = list(closes)
    for _ in range(n):
        out.append(out[-1] - drop)
    return out


def make_pm(position=None, closes=None, opened_days_ago=200, open_orders=None):
    pm = PositionManager.__new__(PositionManager)      # skip __init__ (connects to Alpaca)
    pm.alpaca = MagicMock()
    pm.alpaca.get_positions.return_value = [position or pos()]
    if opened_days_ago is None:
        pm.alpaca.get_first_buy_date.return_value = None
    else:
        pm.alpaca.get_first_buy_date.return_value = (
            datetime.now(timezone.utc) - timedelta(days=opened_days_ago))
    pm.alpaca.get_open_orders.return_value = open_orders or []
    pm.trim_rules = dict(RULES)
    pm.ladder_state = {}
    d = tempfile.mkdtemp()
    pm.ladder_state_path = os.path.join(d, "trim_ladder_state.json")
    pm.trim_log = []
    pm.trim_log_path = os.path.join(d, "trim_log.json")
    pm._daily_closes = lambda sym: closes
    return pm


def eligible(**kw):
    """A position that satisfies every condition, so one change isolates one failure."""
    kw.setdefault('closes', with_down_days(uptrend()))
    return make_pm(**kw)


# --- the happy path --------------------------------------------------------

def test_all_four_conditions_trims():
    sigs = eligible().check_trim_signals('MRVL')
    assert len(sigs) == 1, f"expected a trim, got {sigs}"
    s = sigs[0]
    assert s['type'] == 'PROFIT_TRIM_100'
    assert s['trim_pct'] == 0.20
    assert s['shares_to_sell'] == 20.0, "20% of 100 shares"
    assert s['down_days'] >= 2


# --- each condition, broken one at a time ----------------------------------

def test_held_under_six_months_does_not_trim():
    pm = eligible(opened_days_ago=100)
    assert pm.check_trim_signals('MRVL') == [], "held 100d - must not trim"


def test_held_exactly_six_months_does_not_trim():
    """The rule is LONGER than 6 months, so 183 days exactly is not enough."""
    pm = eligible(opened_days_ago=183)
    assert pm.check_trim_signals('MRVL') == [], "183d is not 'longer than' 183d"


def test_unknown_holding_period_does_not_trim():
    """Unknown must NOT read as old enough - that would trim a fresh position."""
    pm = eligible(opened_days_ago=None)
    assert pm.check_trim_signals('MRVL') == [], "unknown holding period must not trim"


def test_under_100pct_roi_does_not_trim():
    pm = eligible(position=pos(entry=150.0, price=250.0))     # +67%
    assert pm.check_trim_signals('MRVL') == [], "+67% ROI must not trim"


def test_exactly_100pct_roi_does_trim():
    pm = eligible(position=pos(entry=125.0, price=250.0))     # +100%
    assert len(pm.check_trim_signals('MRVL')) == 1, "+100% is the threshold"


def test_one_down_day_does_not_trim():
    pm = eligible(closes=with_down_days(uptrend(), n=1))
    assert pm.check_trim_signals('MRVL') == [], "1 down day must not trim"


def test_below_200day_does_not_trim():
    """A fall below the long-term average is a trend break, not a pullback."""
    closes = with_down_days([300.0 + i * 0.1 for i in range(250)])
    pm = eligible(closes=closes)                              # current 250 < sma ~300
    assert pm.check_trim_signals('MRVL') == [], "below the 200-day must not trim"


def test_pending_sell_does_not_trim():
    pm = eligible(open_orders=[{'symbol': 'MRVL', 'side': 'sell', 'qty': 20}])
    assert pm.check_trim_signals('MRVL') == [], "must not stack a second sell order"


# --- helpers ---------------------------------------------------------------

def test_consecutive_down_days_counts():
    pm = make_pm()
    assert pm.consecutive_down_days([1, 2, 3]) == 0
    assert pm.consecutive_down_days([3, 2, 1]) == 2
    assert pm.consecutive_down_days([5, 4, 4]) == 0, "a flat latest close is not a decline"
    assert pm.consecutive_down_days([10, 9, 8, 7]) == 3
    assert pm.consecutive_down_days([9, 1, 2, 3]) == 0


# --- re-basing: one trim event per doubling, never a cascade ---------------

def test_reference_rebases_so_a_second_trim_needs_another_doubling():
    pm = eligible()
    pm.ladder_state['MRVL'] = {'base_price': 250.0, 'rungs_fired': [1.0], 'trim_count': 1}
    # price still 250 -> 0% ROI from the new base -> nothing
    assert pm.check_trim_signals('MRVL') == [], "must not trim again at the trim price"
    st = pm.profit_trim_status('MRVL', 100.0, 250.0)
    assert abs(st['gain_from_base']) < 1e-9, f"ROI must reset, got {st['gain_from_base']}"
    # price doubles again from the trim price -> eligible again
    pm.alpaca.get_positions.return_value = [pos(entry=100.0, price=500.0)]
    assert len(pm.check_trim_signals('MRVL')) == 1, "another +100% must re-arm the rule"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

"""Tests for the redeploy step in position_manager.

A cap trim sells a winner and parks the proceeds. Over a 2-year replay on the Core book's
own names that parked cash was the ENTIRE cost of the cap: +173% leaving it idle vs +246%
redeployed (Sharpe 2.12 -> 2.26). Easing the cap to 25% instead reached +288% but at
Sharpe 1.86 and a deeper drawdown, so redeployment dominates easing.

These tests exercise redeploy_signals as a pure function. No network: the Alpaca client is
stubbed, so nothing here can place an order. Coverage is deliberately aimed at the failure
modes a new limit actually has - the boundary at the minimum gap, the throttle, the
fail-CLOSED theme path, and malformed rows - not at the happy path, which is trivially right.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src.position_manager import PositionManager

EQUITY = 100_000.0


class StubAlpaca:
    def __init__(self, positions, cash=50_000.0, equity=EQUITY, open_orders=None):
        self._positions = positions
        self._cash = cash
        self._equity = equity
        self._orders = open_orders or []

    def get_positions(self):
        return self._positions

    def get_account(self):
        return {'cash': self._cash, 'equity': self._equity, 'portfolio_value': self._equity}

    def get_open_orders(self):
        return self._orders


def pm(positions, cash=50_000.0, equity=EQUITY, open_orders=None):
    """A PositionManager with __init__ skipped, so no Alpaca connection is made."""
    m = object.__new__(PositionManager)
    m.alpaca = StubAlpaca(positions, cash, equity, open_orders)
    m.trim_rules = {
        'profit_trim_pct': 1.00, 'profit_trim_size': 0.20, 'min_hold_days': 183,
        'pullback_days': 2, 'trend_ma': 200,
        'max_position_pct': 0.10,
        'add_drawdown': 0.20,
        'redeploy_target_pct': 0.08,
        'redeploy_min_gap_pct': 0.01,
        'redeploy_max_pct': 0.10,
        'redeploy_reserve_pct': 0.01,
        'redeploy_enabled': True,
    }
    return m


def pos(symbol, market_value, price=100.0):
    return {'symbol': symbol, 'qty': market_value / price, 'avg_entry_price': price,
            'current_price': price, 'market_value': float(market_value),
            'unrealized_pl': 0.0}


# ── the invariant that keeps the target honest ──────────────────────────────────────────

def test_redeploy_target_sits_below_the_trim_cap():
    """Topping up TO the trim cap would leave every position on the trim boundary, so the
    first good day trims it again - the churn the entry-below-trim split exists to avoid."""
    m = pm([])
    assert m.trim_rules['redeploy_target_pct'] < m.trim_rules['max_position_pct'], \
        "redeploy target must be BELOW the trim cap (entry cap < trim cap)"


def test_redeploy_target_matches_the_live_entry_cap():
    """alpaca_trader.max_position_pct is the live entry cap. The two must not drift apart."""
    from src.alpaca_trader import AlpacaTrader
    import inspect
    src = inspect.getsource(AlpacaTrader.__init__)
    assert 'self.max_position_pct = 0.08' in src, "entry cap changed - align redeploy_target_pct"
    assert pm([]).trim_rules['redeploy_target_pct'] == 0.08


# ── the happy path (brief) ──────────────────────────────────────────────────────────────

def test_an_underweight_holding_is_topped_up_toward_the_target():
    # 5% of equity against an 8% target -> a $3,000 gap, above the $1,000 minimum
    out = pm([pos('LLY', 5_000)]).redeploy_signals()
    assert len(out) == 1, f"expected one top-up, got {out}"
    assert out[0]['symbol'] == 'LLY'
    assert abs(out[0]['notional'] - 3_000) < 1, out[0]


def test_a_holding_at_the_target_is_not_topped_up():
    assert pm([pos('LLY', 8_000)]).redeploy_signals() == []


def test_a_holding_above_the_target_is_not_topped_up():
    assert pm([pos('LLY', 12_000)]).redeploy_signals() == []


# ── boundaries: the minimum gap ─────────────────────────────────────────────────────────

def test_gap_exactly_at_the_minimum_is_taken():
    # equity 100k, min gap 1% -> $1,000. mv 7,000 -> gap exactly 1,000 -> taken.
    out = pm([pos('LLY', 7_000)]).redeploy_signals()
    assert len(out) == 1, f"gap at the boundary should be taken, got {out}"


def test_gap_just_below_the_minimum_is_ignored():
    # mv 7,001 -> gap 999 -> below the minimum -> ignored.
    assert pm([pos('LLY', 7_001)]).redeploy_signals() == []


def test_min_gap_scales_with_equity():
    """The minimum is max($1000, equity * min_gap_pct), so it is not a fixed dollar floor."""
    m = pm([pos('LLY', 7_000)], equity=400_000.0)
    # 8% of 400k = 32k target; mv 7k -> gap 25k, well above both floors
    assert len(m.redeploy_signals()) == 1


# ── the throttle and the reserve ────────────────────────────────────────────────────────

def test_total_deployed_is_throttled_to_max_pct_of_equity():
    # four holdings each 0% of equity -> each wants ~$8,000, total $32,000, but the
    # throttle caps a single scan at 10% of equity = $10,000.
    positions = [pos(s, 0) for s in ('LLY', 'PK', 'AMD', 'BE')]
    out = pm(positions).redeploy_signals()
    total = sum(d['notional'] for d in out)
    assert total <= EQUITY * 0.10 + 1, f"throttle breached: deployed {total}"
    assert total > 9_000, f"throttle should still deploy close to the cap, got {total}"


def test_reserve_is_kept_in_cash():
    # cash 2,000 against a 1% reserve (1,000) -> only 1,000 is deployable
    out = pm([pos('LLY', 0)], cash=2_000.0).redeploy_signals()
    total = sum(d['notional'] for d in out)
    assert total <= 1_000 + 1, f"reserve breached: deployed {total}"


def test_no_cash_deploys_nothing():
    assert pm([pos('LLY', 0)], cash=0.0).redeploy_signals() == []


def test_cash_below_the_reserve_deploys_nothing():
    assert pm([pos('LLY', 0)], cash=500.0).redeploy_signals() == []


def test_negative_cash_deploys_nothing():
    """A margin book can report negative cash. Redeploying on borrowed money is not this."""
    assert pm([pos('LLY', 0)], cash=-5_000.0).redeploy_signals() == []


def test_zero_equity_deploys_nothing():
    assert pm([pos('LLY', 0)], equity=0.0).redeploy_signals() == []


# ── the theme cap must still bind, and must FAIL CLOSED ─────────────────────────────────

def test_top_up_into_an_over_cap_theme_is_refused():
    """AI_HARDWARE well past its 40% ceiling: a top-up into MRVL must be blocked, so
    redeploying cannot become a side door around the sleeve cap."""
    positions = [pos('MRVL', 50_000), pos('MU', 20_000), pos('LLY', 0)]
    out = pm(positions).redeploy_signals()
    syms = [d['symbol'] for d in out]
    assert 'MRVL' not in syms, f"MRVL is in an over-cap theme and must be refused: {out}"
    assert 'LLY' in syms, f"a BIOTECH name should still be allowed: {out}"


def test_unclassified_symbol_is_refused():
    """portfolio_rules fails closed on an unclassified symbol - redeploy must inherit that."""
    out = pm([pos('ZZZZ', 0)]).redeploy_signals()
    assert out == [], f"an unclassified symbol must be refused, got {out}"


# ── duplicate-order guard ───────────────────────────────────────────────────────────────

def test_a_pending_buy_is_not_stacked():
    orders = [{'symbol': 'LLY', 'side': 'buy', 'qty': 10.0}]
    out = pm([pos('LLY', 0)], open_orders=orders).redeploy_signals()
    assert out == [], f"a pending buy must block a second one, got {out}"


def test_a_pending_sell_does_not_block_a_top_up():
    orders = [{'symbol': 'LLY', 'side': 'sell', 'qty': 10.0}]
    out = pm([pos('LLY', 0)], open_orders=orders).redeploy_signals()
    assert len(out) == 1, f"a sell order is not a reason to skip a buy, got {out}"


# ── ordering and robustness ─────────────────────────────────────────────────────────────

def test_most_underweight_is_topped_up_first():
    positions = [pos('LLY', 6_000), pos('PK', 1_000), pos('AMD', 4_000)]
    out = pm(positions).redeploy_signals()
    assert out[0]['symbol'] == 'PK', f"widest gap first, got {[d['symbol'] for d in out]}"


def test_malformed_rows_are_skipped_not_crashed():
    bad = [{'symbol': 'X'}, {'symbol': 'Y', 'market_value': None, 'current_price': 1},
           {'symbol': 'Z', 'market_value': 0, 'current_price': 0}]
    out = pm(bad + [pos('LLY', 0)]).redeploy_signals()
    assert [d['symbol'] for d in out] == ['LLY'], f"got {[d['symbol'] for d in out]}"


def test_non_finite_market_value_is_skipped_not_crashed():
    """Every comparison against a NaN is False, so NaN slips past the minimum-gap test AND
    past the theme check's `after > max_pct`. This is a real bug that shipped in the first
    draft: a NaN market_value produced a bogus ALLOWED buy with a NaN notional."""
    p = pos('LLY', 0)
    p['market_value'] = float('nan')
    assert pm([p]).redeploy_signals() == []


def test_infinite_market_value_is_skipped_not_crashed():
    p = pos('LLY', 0)
    p['market_value'] = float('inf')
    assert pm([p]).redeploy_signals() == []


def test_non_finite_price_is_skipped_not_crashed():
    p = pos('LLY', 0)
    p['current_price'] = float('nan')
    assert pm([p]).redeploy_signals() == []


def test_non_finite_notional_is_refused_by_the_buy_path():
    m = pm([pos('LLY', 5_000)])
    assert m.execute_redeploy('LLY', float('nan'), 'test') is False
    assert m.execute_redeploy('LLY', float('inf'), 'test') is False


def test_a_failing_open_orders_query_does_not_abort_the_scan():
    class Broken(StubAlpaca):
        def get_open_orders(self):
            raise RuntimeError("api down")
    m = pm([pos('LLY', 0)])
    m.alpaca = Broken([pos('LLY', 0)])
    out = m.redeploy_signals()
    assert len(out) == 1, f"a failed order query must not stop the redeploy, got {out}"


def test_a_failing_account_read_returns_nothing():
    class Broken(StubAlpaca):
        def get_account(self):
            raise RuntimeError("api down")
    m = pm([pos('LLY', 0)])
    m.alpaca = Broken([pos('LLY', 0)])
    assert m.redeploy_signals() == []


# ── the buy path only ever touches holdings that exist ──────────────────────────────────

def test_execute_redeploy_refuses_a_symbol_we_do_not_hold():
    """This is a rebalance, not a screener. Opening a position needs a confirmed signal."""
    m = pm([pos('LLY', 5_000)])
    assert m.execute_redeploy('NOTHELD', 1_000, 'test') is False


def test_execute_redeploy_refuses_a_non_positive_notional():
    m = pm([pos('LLY', 5_000)])
    assert m.execute_redeploy('LLY', 0, 'test') is False
    assert m.execute_redeploy('LLY', -100, 'test') is False
    assert m.execute_redeploy('LLY', float('nan'), 'test') is False


def test_execute_redeploy_refuses_when_a_buy_is_pending():
    orders = [{'symbol': 'LLY', 'side': 'buy', 'qty': 5.0}]
    m = pm([pos('LLY', 5_000)], open_orders=orders)
    assert m.execute_redeploy('LLY', 1_000, 'test') is False


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

"""Tests for entry sizing.

The bug this pins: the buy path capped a new position at a hardcoded 15% of account value
while the trimmer enforced a 10% cap, and a third value (0.20) sat unused on the class. Any
position sized between 10% and 15% was therefore over-cap from birth - and because the cap
trim only ever sells WINNERS, an over-cap position that then fell could not be corrected.
MRVL (23% of equity, down), MU, RKLB and DDOG all arrived that way.

The fix sizes BELOW the trim cap so a position has room to rise before the cap binds.
"""
from alpaca_trader import AlpacaTrader

TRIM_CAP = 0.10          # position_manager.trim_rules['max_position_pct']
ENTRY_CAP = 0.08         # alpaca_trader default, deliberately below the trim cap


def trader(cap=ENTRY_CAP):
    t = AlpacaTrader.__new__(AlpacaTrader)     # skip __init__ (loads creds, connects)
    t.max_position_pct = cap
    return t


def test_entry_cap_is_below_the_trim_cap():
    """The invariant that was violated: if entry sizing exceeds the trim cap, the cap
    cannot do its job, and a losers-only cap can never repair the oversize."""
    assert ENTRY_CAP < TRIM_CAP, "entry cap must sit below the trim cap"
    assert abs(trader().max_position_pct - ENTRY_CAP) < 1e-12


def test_new_position_is_capped_at_the_configured_size():
    t = trader()
    t.get_quote = lambda sym: 100.0
    shares, price = t.calculate_position_size('TEST', 1, 100_000.0)
    value = shares * price
    assert value <= 100_000.0 * ENTRY_CAP + 1e-9, f"sized {value:,.0f}, over the cap"
    assert shares == 80, f"expected 80 shares (8% of 100k at $100), got {shares}"


def test_sizing_no_longer_uses_the_old_hardcoded_15pct():
    """15% of 100k at $100 would be 150 shares; 20% would be 200."""
    t = trader()
    t.get_quote = lambda sym: 100.0
    shares, _ = t.calculate_position_size('TEST', 1, 100_000.0)
    assert shares < 150, "must not size at the old hardcoded 15%"
    assert shares < 200, "must not size at the dead 20% attribute value"


def test_cap_scales_with_account_value():
    t = trader()
    t.get_quote = lambda sym: 50.0
    shares, _ = t.calculate_position_size('TEST', 1, 200_000.0)
    assert shares * 50.0 <= 200_000.0 * ENTRY_CAP + 1e-9


def test_zero_or_negative_price_returns_zero():
    t = trader()
    t.get_quote = lambda sym: 0.0
    shares, price = t.calculate_position_size('TEST', 1, 100_000.0)
    assert shares == 0 and price == 0
    t.get_quote = lambda sym: -5.0
    shares, price = t.calculate_position_size('TEST', 1, 100_000.0)
    assert shares == 0 and price == 0


def test_missing_quote_returns_zero():
    t = trader()
    t.get_quote = lambda sym: None
    shares, price = t.calculate_position_size('TEST', 1, 100_000.0)
    assert shares == 0 and price == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

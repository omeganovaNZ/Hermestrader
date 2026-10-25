"""Tests for the ETF sleeve (index funds) in portfolio_rules.

The books are high-beta and concentrated; index funds are the cheapest drawdown control.
But an ETF used to be UNCLASSIFIED and therefore refused by the theme cap — unbuyable,
not uncapped. These tests pin the new ETF sleeves and their cap.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src import portfolio_rules as pr

EQUITY = 100_000.0


def pos(symbol, market_value, price=100.0):
    return {'symbol': symbol, 'qty': market_value / price, 'avg_entry_price': price,
            'current_price': price, 'market_value': float(market_value),
            'unrealized_pl': 0.0}


def test_a_known_etf_is_classified():
    assert pr.etf_theme_of("SPY") == "BROAD_MARKET"
    assert pr.etf_theme_of("QQQ") == "GROWTH_INDEX"
    assert pr.etf_theme_of("SCHD") == "DIVIDEND_VALUE"
    assert pr.etf_theme_of("XLV") == "SECTOR"


def test_an_unknown_symbol_is_not_an_etf():
    assert pr.etf_theme_of("ZZZZ") is None


def test_etf_buy_is_allowed_when_the_sleeve_has_room():
    ok, why = pr.etf_cap_check_safe("SPY", 8_000, [], EQUITY)
    assert ok is True, why


def test_etf_buy_is_refused_when_the_sleeve_would_breach_the_cap():
    positions = [pos("SPY", 39_000)]
    ok, why = pr.etf_cap_check_safe("VOO", 5_000, positions, EQUITY)
    assert ok is False
    assert "ETF cap" in why


def test_theme_cap_routes_an_etf_to_the_etf_cap():
    # SPY is not a stock theme, but it IS an ETF sleeve — the stock cap must not
    # refuse it as "unclassified".
    ok, why = pr.theme_cap_check("SPY", 8_000, [], EQUITY)
    assert ok is True, why


def test_unclassified_symbol_is_still_refused():
    ok, why = pr.theme_cap_check("ZZZZ", 1_000, [], EQUITY)
    assert ok is False
    assert "unclassified" in why


def test_etf_exposure_is_reported():
    positions = [pos("SPY", 10_000), pos("QQQ", 5_000), pos("MSFT", 20_000)]
    exp = pr.theme_exposure(positions, EQUITY)
    assert "BROAD_MARKET" in exp
    assert "GROWTH_INDEX" in exp
    assert "MEGA_INTERNET" in exp
    assert abs(exp["BROAD_MARKET"]["pct"] - 0.10) < 1e-9


def test_etf_sleeves_do_not_overlap():
    seen = {}
    for name, members in pr.ETF_THEMES.items():
        for m in members:
            assert m not in seen, f"{m} is in both {seen.get(m)} and {name}"
            seen[m] = name


def test_etf_cap_is_separate_from_the_stock_cap():
    assert pr.MAX_ETF_PCT == 0.40
    assert pr.MAX_THEME_PCT == 0.40


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

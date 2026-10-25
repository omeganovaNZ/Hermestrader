"""Tests for the buy-path gates: ensemble gate, conviction tiers, cash drag.

No network: the Alpaca client is stubbed.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src.alpaca_trader import AlpacaTrader
from src.position_manager import PositionManager

EQUITY = 100_000.0


class StubQuote:
    ask_price = 100.0


def make_trader():
    t = object.__new__(AlpacaTrader)
    t.max_position_pct = 0.08
    t.conviction_pct = {"MSFT": 0.10}
    t.get_quote = lambda s: StubQuote()
    return t


# ── ensemble gate ────────────────────────────────────────────────────────────────

def test_ensemble_gate_blocks_too_few_live_layers():
    t = make_trader()
    t._ensemble_cache = {"X": ("BUY", "note", 2)}
    ok, why = t.ensemble_gate("X")
    assert ok is False
    assert "live layer" in why


def test_ensemble_gate_blocks_a_sell():
    t = make_trader()
    t._ensemble_cache = {"X": ("STRONG_SELL", "weak", 4)}
    ok, why = t.ensemble_gate("X")
    assert ok is False
    assert "STRONG_SELL" in why


def test_ensemble_gate_allows_a_buy_with_enough_layers():
    t = make_trader()
    t._ensemble_cache = {"X": ("BUY", "ok", 4)}
    ok, why = t.ensemble_gate("X")
    assert ok is True, why


def test_ensemble_gate_allows_a_hold():
    t = make_trader()
    t._ensemble_cache = {"X": ("HOLD", "neutral", 3)}
    ok, why = t.ensemble_gate("X")
    assert ok is True, why


def test_ensemble_gate_fails_open_when_unavailable():
    t = make_trader()
    t._ensemble = type("E", (), {
        "generate_ensemble_signal": lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("api down"))
    })()
    t._ensemble_cache = {}
    # The gate must fail OPEN (not block every buy) when the ensemble is unavailable.
    ok, why = t.ensemble_gate("X")
    assert ok is True
    assert "skipped" in why


# ── conviction tiers ──────────────────────────────────────────────────────────────

def test_default_entry_cap_is_eight_percent():
    t = make_trader()
    shares, _ = t.calculate_position_size("UNKNOWN", 1, EQUITY)
    # 8% of 100k = 8000 / 100 = 80 shares (risk term is larger, so the cap binds)
    assert shares == 80, shares


def test_conviction_tier_sizes_higher():
    t = make_trader()
    shares, _ = t.calculate_position_size("MSFT", 1, EQUITY)
    assert shares == 100, shares   # 10% of 100k / 100


def test_conviction_tier_never_exceeds_the_trim_cap():
    t = make_trader()
    t.conviction_pct = {"MSFT": 0.15}   # above the 10% trim cap
    shares, _ = t.calculate_position_size("MSFT", 1, EQUITY)
    assert shares <= 100, shares


# ── cash drag ─────────────────────────────────────────────────────────────────────

class StubPM:
    pass


def make_pm(positions, cash, equity):
    m = object.__new__(PositionManager)
    m.alpaca = type("A", (), {
        "get_account": lambda self: {'cash': cash, 'equity': equity, 'portfolio_value': equity},
        "get_positions": lambda self: positions,
        "get_open_orders": lambda self: [],
        "cash_drag_pct": 0.10,
    })()
    return m


def test_cash_drag_deploys_when_cash_is_high():
    positions = [{'symbol': 'MSFT', 'qty': 1, 'avg_entry_price': 100, 'current_price': 100,
                  'market_value': 10_000.0, 'unrealized_pl': 0.0}]
    m = make_pm(positions, cash=30_000.0, equity=EQUITY)
    out = m.cash_drag_signals()
    assert len(out) > 0, "idle cash should be deployed"
    assert all(d['symbol'] != 'MSFT' for d in out), "must not buy an existing holding"


def test_cash_drag_does_nothing_when_cash_is_low():
    m = make_pm([], cash=5_000.0, equity=EQUITY)
    assert m.cash_drag_signals() == []


def test_cash_drag_respects_the_theme_cap():
    # A single AI_HARDWARE name at 39% leaves no room for another AI name.
    positions = [{'symbol': 'NVDA', 'qty': 1, 'avg_entry_price': 100, 'current_price': 100,
                  'market_value': 39_000.0, 'unrealized_pl': 0.0}]
    m = make_pm(positions, cash=30_000.0, equity=EQUITY)
    out = m.cash_drag_signals()
    assert all(d['symbol'] != 'NVDA' for d in out)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

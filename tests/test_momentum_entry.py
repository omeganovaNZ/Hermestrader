"""Tests for the momentum-first entry (src/market_aware_strategy.py).

The ADX/regime entry waits for a trend to confirm, so it sits out the initial breakout
of the biggest winners. The momentum-first entry catches that leg. These tests pin the
behaviour: the default is on, the flag and threshold are honoured, and the entry is
never later than the base entry.
"""
import os
import sys
import json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import pandas as pd
from src.market_aware_strategy import (
    MarketAwareHybridStrategy, MARKET_CONFIGS,
    MOMENTUM_ENTRY_DEFAULT, MOMENTUM_ENTRY_THRESHOLD_DEFAULT,
)


def _kod():
    """KOD's cached 3y bars - the name the momentum entry was measured on."""
    path = os.path.join(REPO, "scratch", "bars_full.json")
    if not os.path.exists(path):
        return None
    raw = json.load(open(path, encoding="utf-8"))
    rows = raw.get("KOD")
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date").sort_index()


def _first_entry(df, extra):
    cfg = dict(MARKET_CONFIGS["US_TECH"])
    cfg.update(extra)
    d = MarketAwareHybridStrategy(cfg).generate_signals(df)
    sig = d[d["signal"] == 1]
    return (sig.index[0] if len(sig) else None, int(d["signal"].abs().sum()))


def test_default_is_on():
    assert MOMENTUM_ENTRY_DEFAULT is True
    assert MOMENTUM_ENTRY_THRESHOLD_DEFAULT > 0


def test_momentum_entry_is_not_later_than_base():
    df = _kod()
    if df is None:
        print("    (skipped - no scratch/bars_full.json in this checkout)")
        return
    off = _first_entry(df, {"momentum_entry": False})
    on = _first_entry(df, {"momentum_entry": True})
    assert off[0] is not None, "base strategy should enter KOD at some point"
    assert on[0] is not None, "momentum-first entry should enter KOD"
    assert on[0] <= off[0], f"momentum entry must not be later: {on[0]} vs {off[0]}"
    assert on[1] >= off[1], "adding an entry cannot reduce the signal count"


def test_default_matches_explicit_on():
    df = _kod()
    if df is None:
        print("    (skipped - no scratch/bars_full.json in this checkout)")
        return
    assert _first_entry(df, {}) == _first_entry(df, {"momentum_entry": True})


def test_threshold_is_honoured():
    df = _kod()
    if df is None:
        print("    (skipped - no scratch/bars_full.json in this checkout)")
        return
    strict = _first_entry(df, {"momentum_entry": True, "momentum_entry_threshold": 0.90})
    loose = _first_entry(df, {"momentum_entry": True, "momentum_entry_threshold": 0.05})
    # a stricter momentum floor can only make the first entry later or never
    assert strict[0] is None or (loose[0] is not None and strict[0] >= loose[0])


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

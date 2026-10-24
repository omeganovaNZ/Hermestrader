"""Tests for the POWER_FOR_AI sleeve.

The sleeve exists because grouping power INFRASTRUCTURE with fuel PRODUCERS made the 40%
cap blind: BE correlates +0.363 with AI hardware and +0.149 with energy; GEV +0.424/+0.118;
while XOM runs -0.019/+0.418 and MPC +0.149/+0.492. Those are two different risk factors and
one ceiling cannot govern both.

These tests pin three things a later edit could silently undo:
  1. the MEASURED membership, so it cannot drift back to nominal sector labels;
  2. the FITTED config, including that its ADX threshold sits below the 33 cliff;
  3. the cross-module invariant that actually broke - every config_name named in the
     watchlist must exist in MARKET_CONFIGS, or the scan raises KeyError at signal time.

No network: the watchlist is read from the source text rather than by instantiating
AlpacaTrader, whose __init__ connects to Alpaca.
"""
import inspect
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src.portfolio_rules import THEMES, theme_of
from src.market_aware_strategy import MARKET_CONFIGS
from src.alpaca_trader import AlpacaTrader

# The membership as measured (corr vs AI_HARDWARE >= 0.33, vs POWER_ENERGY <= 0.18).
# Re-derived 2026-10-22 on the 2-year window (2024-10-01..2026-10-21): FSLR moved in
# (+0.324 vs POWER_FOR_AI, +0.081 vs POWER_ENERGY) and ENPH was added as the weakest fit
# on the map. See test_the_re_decided_names_are_pinned_with_their_reason below.
MEASURED = {'BE', 'GEV', 'VICR', 'CEG', 'TLN', 'NRG', 'VRT', 'ETN', 'PWR', 'OKLO',
            'AES', 'FSLR', 'GE', 'TT', 'VST', 'ENPH'}
# Fuel producers: they track energy by a wide margin and must NOT be moved.
FUEL = {'XOM', 'CVX', 'MPC', 'PSX', 'VLO', 'DINO', 'CVI', 'APA'}


def _watchlist():
    """Parse the watchlist out of AlpacaTrader.__init__ without connecting to Alpaca."""
    src = inspect.getsource(AlpacaTrader.__init__)
    return re.findall(r'\("([A-Z0-9.]+)",\s*"[^"]+",\s*"([A-Z_0-9]+)"\)', src)


# ── the measured membership ─────────────────────────────────────────────────────────────

def test_power_for_ai_holds_exactly_the_measured_members():
    assert THEMES['POWER_FOR_AI'] == MEASURED, (
        f"membership drifted. extra: {THEMES['POWER_FOR_AI'] - MEASURED}, "
        f"missing: {MEASURED - THEMES['POWER_FOR_AI']}")


def test_fuel_producers_stayed_in_power_energy():
    """The falsifiable half of the split. If a name here moved to POWER_FOR_AI, the sleeve
    would be a nominal relabel rather than a measured risk grouping."""
    for sym in FUEL:
        assert theme_of(sym) == 'POWER_ENERGY', f"{sym} should still be POWER_ENERGY"


def test_vicr_moved_out_of_power_energy():
    """VICR was in POWER_ENERGY at 80% vol while tracking AI (+0.375) far more than energy
    (+0.093) - the same error that put BE there."""
    assert theme_of('VICR') == 'POWER_FOR_AI'


def test_the_sleeves_do_not_share_a_member():
    overlap = THEMES['POWER_FOR_AI'] & THEMES['POWER_ENERGY']
    assert overlap == set(), f"in both sleeves: {overlap}"


def test_power_for_ai_is_not_folded_into_ai_hardware():
    """Folding it in would have taken Core's AI_HARDWARE exposure from 53.9% to 63.2%."""
    assert not (THEMES['POWER_FOR_AI'] & THEMES['AI_HARDWARE'])


def test_the_re_decided_names_are_pinned_with_their_reason():
    """Three names the previous map left in place "so it is not re-litigated". Re-measured on
    the 2-year window the measurement is now good enough that leaving them was the less
    defensible choice, so the decisions are pinned here with the number that drove them."""
    # FSLR: +0.324 vs POWER_FOR_AI, +0.250 vs AI_HARDWARE, +0.081 vs POWER_ENERGY. It tracks
    # the power sleeve, not the fuel producers - the old reading ("leans AI but weakly") was
    # taken on a shorter window.
    assert theme_of('FSLR') == 'POWER_FOR_AI'
    # ENPH: the weakest fit on the whole map - best measured AI_HARDWARE +0.223, second
    # MATERIALS +0.196, POWER_FOR_AI +0.172. A solar microinverter and home-battery maker,
    # kept in the nearest power-equipment sleeve rather than the fuel producers.
    assert theme_of('ENPH') == 'POWER_FOR_AI'
    # NEE: +0.516 vs REGULATED_UTILITIES against +0.147 for energy. A regulated utility at
    # 25% vol, not a fuel producer.
    assert theme_of('NEE') == 'REGULATED_UTILITIES'


# ── the fitted config ───────────────────────────────────────────────────────────────────

def test_power_for_ai_has_a_market_config():
    assert 'POWER_FOR_AI' in MARKET_CONFIGS, "a theme with no config breaks signal generation"


def test_the_config_threshold_is_below_the_measured_cliff():
    """Swept 24/28/30/33/36 on the sleeve's own 10 names: Sharpe 0.688/0.690/0.705 then
    0.545 at 33 and 0.554 at 36, with beats-B&H falling to 0/10 at 33. 33 is the cliff, and
    33 is what BE was using on US_TECH."""
    thr = MARKET_CONFIGS['POWER_FOR_AI']['adx_threshold']
    assert thr < 33, f"threshold {thr} is at or past the cliff"
    assert 24 <= thr <= 30, f"threshold {thr} is outside the measured plateau"


def test_the_config_uses_wide_bands_like_the_volatility_it_holds():
    """BE is 102% annualised vol and OKLO 101% - semis-like, not utility-like."""
    assert MARKET_CONFIGS['POWER_FOR_AI']['mr_num_std'] >= 2.2


def test_the_config_has_every_key_the_strategy_reads():
    required = {'region', 'industry', 'adx_lookback', 'adx_threshold', 'adx_transition_low',
                'mr_lookback', 'mr_num_std', 'trend_ma', 'atr_lookback'}
    for name, cfg in MARKET_CONFIGS.items():
        missing = required - set(cfg)
        assert missing == set(), f"{name} is missing {missing}"


# ── the cross-module invariant that actually broke ──────────────────────────────────────

def test_every_watchlist_config_name_exists():
    """A watchlist entry naming a config that does not exist raises KeyError inside
    generate_signals, so the symbol silently drops out of the scan. This is the failure the
    POWER_FOR_AI work could have introduced."""
    missing = [(sym, cfg) for sym, cfg in _watchlist() if cfg not in MARKET_CONFIGS]
    assert missing == [], f"watchlist names a config that does not exist: {missing}"


def test_the_watchlist_was_actually_parsed():
    """A regex that matches nothing would make the test above vacuously pass."""
    wl = _watchlist()
    assert len(wl) > 20, f"only parsed {len(wl)} watchlist entries - regex has drifted"
    assert any(s == 'BE' for s, _ in wl), "BE is missing from the parsed watchlist"


def test_be_uses_the_power_for_ai_config():
    cfg = dict(_watchlist()).get('BE')
    assert cfg == 'POWER_FOR_AI', f"BE's config is {cfg}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

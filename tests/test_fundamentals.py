"""Tests for the fundamentals gate (src/fundamentals.py).

No network: the registry is a module-level dict.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from src import fundamentals as f


def test_a_strong_record_passes():
    ok, why = f.fundamental_check("MSFT")
    assert ok, why


def test_no_record_is_refused_fail_closed():
    ok, why = f.fundamental_check("ZZZZ")
    assert ok is False
    assert "no verified fundamentals" in why


def test_revenue_floor_blocks_a_weak_name():
    # SWKS has revenue growth -3.1%, below the 3% floor
    ok, why = f.fundamental_check("SWKS")
    assert ok is False
    assert "revenue growth" in why


def test_eps_floor_blocks_a_declining_name():
    # RVTY has EPS growth -3.9% (and revenue below the floor too)
    ok, why = f.fundamental_check("RVTY")
    assert ok is False
    assert "growth" in why


def test_contracting_margin_is_refused():
    # BE passes revenue/EPS but its margin trend is contracting
    ok, why = f.fundamental_check("BE")
    assert ok is False
    assert "margin" in why


def test_guidance_cut_is_refused():
    # NUE guidance was cut
    ok, why = f.fundamental_check("NUE")
    assert ok is False
    assert "guidance" in why


def test_guidance_cut_can_be_allowed():
    ok, why = f.fundamental_check("NUE", refuse_guidance_cut=False)
    assert ok is True, why


def test_thresholds_are_configurable():
    # A low bar lets a weak name through
    ok, why = f.fundamental_check("SWKS", min_revenue_growth=-10.0, min_eps_growth=-50.0,
                                  min_margin_trend="contracting")
    assert ok is True, why


def test_safe_wrapper_never_raises():
    ok, why = f.fundamental_check_safe("MSFT")
    assert ok is True
    # A broken symbol type must not raise
    ok2, why2 = f.fundamental_check_safe(None)
    assert ok2 is False


def test_records_carry_a_source_and_date():
    for sym, rec in f.FUNDAMENTALS.items():
        assert rec.get("source"), f"{sym} has no source"
        assert rec.get("as_of"), f"{sym} has no as_of"
        assert rec.get("guidance") in ("raised", "maintained", "cut"), f"{sym} bad guidance"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

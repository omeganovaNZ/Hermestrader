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


# ── the one-convention rule: GAAP, with a narrow documented adjustment ───────────────────

def test_eps_convention_is_declared_on_every_record():
    """Every entry must say how its EPS was measured - an undeclared basis is a silent
    cherry-pick, which is exactly what the convention rule exists to prevent."""
    allowed = {"gaap", "gaap_adj", "gaap_return_to_profit"}
    for sym, rec in f.FUNDAMENTALS.items():
        assert rec.get("eps_basis", "gaap") in allowed, f"{sym} has an unknown eps_basis"


def test_gaap_return_to_profit_passes_on_the_swing():
    # CRWD and MXL went GAAP loss -> profit; no % change is meaningful, so the gate
    # passes on the documented swing.
    for sym in ("CRWD", "MXL"):
        ok, why = f.fundamental_check(sym)
        assert ok is True, f"{sym} should pass: {why}"


def test_gaap_return_to_profit_requires_corroboration():
    """A name cannot claim 'return to profit' without the raw GAAP figures backing it -
    otherwise 'return to profit' would be a get-out-of-jail card."""
    saved = dict(f.FUNDAMENTALS)
    try:
        f.FUNDAMENTALS["FAKE"] = {
            "revenue_growth": 50.0, "eps_growth": None, "eps_basis": "gaap_return_to_profit",
            "gaap_eps_prior": 0.5, "gaap_eps_current": 0.9,  # both positive: no swing
            "margin_trend": "expanding", "guidance": "raised", "source": "test", "as_of": "2026-01-01"}
        ok, why = f.fundamental_check("FAKE")
        assert ok is False, f"an unverified swing must be refused: {why}"
        assert "corroborate" in why
        # missing figures must also refuse
        f.FUNDAMENTALS["FAKE"]["gaap_eps_prior"] = None
        ok2, why2 = f.fundamental_check("FAKE")
        assert ok2 is False, why2
    finally:
        f.FUNDAMENTALS.clear()
        f.FUNDAMENTALS.update(saved)


def test_one_time_adjustment_is_auditable():
    """LITE's raw GAAP is distorted by a one-time item, so the adjusted growth is used -
    but the raw GAAP figures must remain on the record so the adjustment can be checked."""
    rec = f.FUNDAMENTALS["LITE"]
    assert rec["eps_basis"] == "gaap_adj"
    assert rec["gaap_eps_prior"] == 2.96
    assert rec["gaap_eps_current"] == -84.65  # raw GAAP, still negative
    ok, why = f.fundamental_check("LITE")
    assert ok is True, why


def test_fundamental_score_handles_a_null_eps():
    # CRWD has no numeric eps_growth (return-to-profit), and the score must still compute
    s = f.fundamental_score("CRWD")
    assert s > 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

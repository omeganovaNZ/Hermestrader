"""Tests for portfolio_rules: the theme (sleeve) cap and the thesis review.

The theme cap exists because the playbook declared a 40% ceiling on the AI-hardware sleeve
and NOTHING enforced it, which is how that sleeve reached 75% of long market value. The
thesis review exists because the system had no downside management at all: the profit trim
needs +100%, the cap trim only sells winners, and thesis_break_exit is called by nothing.

Both are pure functions, so these tests need no network and no mocking of Alpaca.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import src.portfolio_rules as pr

EQUITY = 100_000.0


def pos(symbol, qty, entry, price):
    return {'symbol': symbol, 'qty': float(qty), 'avg_entry_price': float(entry),
            'current_price': float(price), 'market_value': float(qty) * float(price),
            'unrealized_pl': float(qty) * (float(price) - float(entry))}


# ── the invariant that keeps the hand-maintained map honest ─────────────────────────────

def test_every_held_symbol_is_classified():
    """Alpaca's free tier gives no sector field, so THEMES is hand-maintained and will drift.
    This forces a new holding to be classified instead of silently escaping the cap."""
    held = ['MRVL', 'MU', 'RKLB', 'DDOG', 'BE', 'LLY', 'AMD', 'PK']
    unclassified = [s for s in held if pr.theme_of(s) is None]
    assert unclassified == [], f"held but unclassified: {unclassified} - add them to THEMES"


def test_themes_do_not_overlap():
    seen = {}
    for name, members in pr.THEMES.items():
        for s in members:
            assert s not in seen, f"{s} is in both {seen.get(s)} and {name}"
            seen[s] = name


# ── theme exposure ──────────────────────────────────────────────────────────────────────

def test_theme_exposure_computes_percentages():
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 50, 400, 400), pos('PK', 1000, 15, 15)]
    exp = pr.theme_exposure(positions, EQUITY)
    assert abs(exp['AI_HARDWARE']['value'] - 40_000) < 1e-6
    assert abs(exp['AI_HARDWARE']['pct'] - 0.40) < 1e-9
    assert exp['AI_HARDWARE']['symbols'] == ['MRVL', 'MU']
    assert abs(exp['REAL_ESTATE']['pct'] - 0.15) < 1e-9


def test_unclassified_exposure_is_visible():
    positions = [pos('MRVL', 100, 200, 200), pos('ZZZZ', 100, 100, 100)]
    un = pr.unclassified_exposure(positions, EQUITY)
    assert un['symbols'] == ['ZZZZ']
    assert abs(un['pct'] - 0.10) < 1e-9


# ── the cap itself ──────────────────────────────────────────────────────────────────────

def test_buy_that_breaches_the_cap_is_refused():
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 37.5, 400, 400)]  # 35% AI_HARDWARE
    ok, why = pr.theme_cap_check('AMD', 6_000, positions, EQUITY)        # -> 41%
    assert ok is False, f"should have been refused: {why}"
    assert '41' in why or '40' in why


def test_buy_within_the_cap_is_allowed():
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 37.5, 400, 400)]  # 35%
    ok, why = pr.theme_cap_check('AMD', 4_000, positions, EQUITY)        # -> 39%
    assert ok is True, why


def test_adding_to_an_already_over_cap_theme_is_refused():
    """The live case: AI-hardware is 75% against a 40% ceiling, so ANY addition is refused."""
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 100, 400, 400),
                 pos('AMD', 100, 100, 100), pos('DDOG', 100, 50, 50)]    # 75%
    ok, why = pr.theme_cap_check('NVDA', 1.0, positions, EQUITY)
    assert ok is False, why


def test_a_buy_in_another_theme_is_allowed_even_when_one_is_over():
    """The cap must constrain the offending theme, not freeze the whole book."""
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 100, 400, 400),
                 pos('AMD', 100, 100, 100), pos('DDOG', 100, 50, 50)]    # 75% AI
    ok, why = pr.theme_cap_check('LLY', 5_000, positions, EQUITY)
    assert ok is True, why
    assert 'BIOTECH_HEALTH' in why


def test_unclassified_symbol_fails_closed():
    ok, why = pr.theme_cap_check('ZZZZ', 50_000, [], EQUITY)
    assert ok is False, "unclassified symbols must be refused (fail CLOSED)"
    assert 'unclassified' in why.lower()


def test_zero_equity_REFUSES_the_buy():
    """This used to return ok=True ('not evaluated'), which quietly disabled the cap -
    the exact opposite of the fail-closed contract the order path relies on."""
    ok, why = pr.theme_cap_check('AMD', 1_000, [], 0.0)
    assert ok is False, "an unusable equity must REFUSE the buy"
    assert 'equity' in why.lower()
    ok, _ = pr.theme_cap_check('AMD', 1_000, [], -5.0)
    assert ok is False, "negative equity must REFUSE the buy"


def test_unreadable_position_value_fails_closed():
    """A risk limit that opens up when it cannot be evaluated is not a limit."""
    broken = [{'symbol': 'MRVL', 'market_value': 'not-a-number'}]
    ok, why = pr.theme_cap_check_safe('NVDA', 5_000, broken, EQUITY)
    assert ok is False, "an unreadable position value must REFUSE the buy"
    assert 'could not be evaluated' in why


def test_safe_wrapper_delegates_when_the_input_is_fine():
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 37.5, 400, 400)]   # 35%
    assert pr.theme_cap_check_safe('AMD', 4_000, positions, EQUITY)[0] is True
    assert pr.theme_cap_check_safe('AMD', 6_000, positions, EQUITY)[0] is False


# ── thesis review ───────────────────────────────────────────────────────────────────────

def test_long_and_down_is_flagged():
    p = [pos('MRVL', 100, 200, 140)]                 # -30%
    revs = pr.thesis_review(p, {'MRVL': 200})
    assert len(revs) == 1 and revs[0]['flag'] == 'LONG_AND_DOWN'
    assert revs[0]['action'] == 'REPORT_ONLY'


def test_long_and_only_slightly_down_is_not_flagged():
    p = [pos('MRVL', 100, 200, 190)]                 # -5%
    assert pr.thesis_review(p, {'MRVL': 200}) == []


def test_deeply_down_but_recent_is_still_flagged():
    """A 30% drawdown is always flagged, even if fresh — a crash deserves attention."""
    p = [pos('MRVL', 100, 200, 140)]
    revs = pr.thesis_review(p, {'MRVL': 21})
    assert len(revs) == 1 and revs[0]['flag'] == 'LONG_AND_DOWN'


def test_stale_wins_over_long_and_down():
    p = [pos('MRVL', 100, 200, 190)]                 # -5% but held 400d
    revs = pr.thesis_review(p, {'MRVL': 400})
    assert len(revs) == 1 and revs[0]['flag'] == 'STALE'


def test_held_a_year_and_up_is_not_flagged():
    p = [pos('MRVL', 100, 100, 200)]
    assert pr.thesis_review(p, {'MRVL': 400}) == []


def test_unknown_holding_period_is_not_flagged():
    """Unknown age must not read as old enough to judge."""
    p = [pos('MRVL', 100, 200, 140)]
    assert pr.thesis_review(p, {'MRVL': None}) == []
    assert pr.thesis_review(p, {}) == []


def test_thesis_review_never_sells():
    p = [pos('MRVL', 100, 200, 140)]
    revs = pr.thesis_review(p, {'MRVL': 200})
    for r in revs:
        assert r['action'] == 'REPORT_ONLY', "the review must never imply a sale"


def test_review_is_sorted_worst_first():
    p = [pos('MRVL', 100, 200, 170), pos('MU', 10, 100, 60), pos('AMD', 10, 100, 70)]
    revs = pr.thesis_review(p, {'MRVL': 200, 'MU': 200, 'AMD': 200})
    pls = [r['pl_pct'] for r in revs]
    assert pls == sorted(pls), f"not worst-first: {pls}"


# ── boundary equality: where off-by-one bugs live ───────────────────────────────────────
# A mutation audit found NONE of these four boundaries was exercised, so changing >= to >
# (or <= to <) at any of them would have survived the entire suite.

def test_cap_boundary_at_exactly_40pct():
    """`after > max_pct` means landing exactly ON the ceiling passes; going past it does not."""
    positions = [pos('MRVL', 100, 200, 200), pos('MU', 50, 400, 400)]     # exactly 40.0%
    ok, why = pr.theme_cap_check('AMD', 0.0, positions, EQUITY)
    assert ok is True, why
    ok, why = pr.theme_cap_check('AMD', 0.01, positions, EQUITY)           # 40.00001%
    assert ok is False, why


def test_review_window_boundary_at_exactly_180_days():
    # With the updated logic, any position down >=25% is flagged regardless of age.
    # The 180-day window only matters for the STALE flag (held a year+ and still down).
    p = [pos('MRVL', 100, 200, 140)]                                       # -30%
    assert len(pr.thesis_review(p, {'MRVL': 180})) == 1, "180d is in-window"
    assert len(pr.thesis_review(p, {'MRVL': 179})) == 1, "179d is also flagged (down >=25%)"


def test_drawdown_boundary_at_exactly_25pct():
    p = [pos('MRVL', 100, 200, 150)]                                       # exactly -25%
    assert len(pr.thesis_review(p, {'MRVL': 200})) == 1, "-25% is 'or more'"
    p = [pos('MRVL', 100, 200, 150.2)]                                     # -24.9%
    assert pr.thesis_review(p, {'MRVL': 200}) == []


def test_stale_boundary_at_exactly_365_days():
    p = [pos('MRVL', 100, 200, 199)]                                       # -0.5%
    assert len(pr.thesis_review(p, {'MRVL': 365})) == 1, "365d is 'a year or more'"
    assert pr.thesis_review(p, {'MRVL': 364}) == []


def test_deep_loss_past_a_year_reports_the_deeper_flag():
    """The elif order used to make LONG_AND_DOWN unreachable past 365 days, so a position
    down 90% after 500 days reported as merely STALE and the severity was lost."""
    revs = pr.thesis_review([pos('MRVL', 100, 200, 20)], {'MRVL': 500})    # -90%
    assert len(revs) == 1
    assert revs[0]['flag'] == 'LONG_AND_DOWN', f"got {revs[0]['flag']}"


# ── robustness: an unreadable row must not crash the scan ───────────────────────────────

def test_unreadable_rows_are_skipped_not_crashed():
    good = pos('MU', 100, 200, 140)
    bad = [{'symbol': 'X', 'qty': None, 'avg_entry_price': 100, 'market_value': 50},
           {'symbol': 'Y', 'qty': 10, 'avg_entry_price': None, 'market_value': 50},
           {'symbol': 'Z'}]
    revs = pr.thesis_review([good] + bad, {'MU': 200, 'X': 200, 'Y': 200, 'Z': 200})
    assert [r['symbol'] for r in revs] == ['MU'], f"got {[r['symbol'] for r in revs]}"


def test_nan_market_value_is_skipped_not_crashed():
    nan = pos('MU', 100, 200, 200)
    nan['market_value'] = float('nan')
    assert pr.thesis_review([nan], {'MU': 500}) == []


def test_zero_cost_position_is_skipped():
    z = {'symbol': 'MU', 'qty': 0, 'avg_entry_price': 200, 'market_value': 0}
    assert pr.thesis_review([z], {'MU': 500}) == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\n  {len(tests)} tests passed")

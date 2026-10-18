"""Portfolio-level rules that used to exist only as prose in TRADING_PLAYBOOK.md.

Two rules live here, both pure functions so they can be tested without a network:

1. THE THEME (SLEEVE) CAP. The playbook declared a 40% ceiling on the AI-hardware sleeve
   and then nothing enforced it, which is exactly how that sleeve reached 75% of long
   market value with a 0.53 mean pairwise correlation inside it and portfolio volatility
   at 3.9x the market. `theme_cap_check` is called by the buy path and refuses any order
   that would push a theme past the ceiling.

2. THE THESIS REVIEW. The system has no downside management at all: the profit trim only
   fires above +100%, the cap trim only sells winners, and `thesis_break_exit` is called by
   nothing. So a position can fall 60% and the system does nothing. That is the owner's
   deliberate rule ("at no other time do I want to trim what has been invested"), so this
   does NOT sell anything - it FLAGS positions for a human decision and reports them.

LIMITATION, stated plainly: Alpaca's free tier provides no sector or industry field, so the
theme map below is HAND-MAINTAINED. A symbol that is not listed is "unclassified" and no
theme cap applies to it, so a new name in an existing theme will slip through until it is
added. `test_portfolio_rules.py` asserts that every currently-held symbol is classified, and
`unclassified_exposure()` reports whatever is unclassified so the gap stays visible.
"""

import math

# ── theme (sleeve) cap ──────────────────────────────────────────────────────────────────

MAX_THEME_PCT = 0.40

# One theme per symbol. The AI_HARDWARE grouping deliberately matches the playbook's own
# "AI-hardware sleeve" (MRVL, RKLB, MU, DDOG, AMD) even though RKLB is space and DDOG is
# software - they were grouped because they MOVE TOGETHER (measured 0.53 mean pairwise
# correlation), and correlation is what makes a sleeve a risk.
THEMES = {
    "AI_HARDWARE": {
        "MRVL", "MU", "AMD", "NVDA", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "KLAC",
        "SNPS", "CDNS", "MXL", "SNDK", "SMCI", "ANET", "ARM", "DELL", "ALAB", "COHU",
        "INTC", "SIMO", "RKLB", "DDOG", "NET", "SNOW", "PLTR",
    },
    "POWER_ENERGY": {
        "BE", "GEV", "VICR", "ENPH", "FSLR", "NEE", "XOM", "CVX", "MPC", "PSX",
        "VLO", "DINO", "CVI", "APA",
    },
    "BIOTECH_HEALTH": {
        "LLY", "MRNA", "IOVA", "KOD", "TXG", "CRSP", "NTLA", "BEAM", "EDIT", "VRTX",
        "RPRX", "TVTX",
    },
    "CYBERSECURITY": {"CRWD", "PANW", "OKTA", "S"},
    "REAL_ESTATE": {"PK", "DRH", "OUT"},
}


def theme_of(symbol):
    """The theme a symbol belongs to, or None when it is unclassified.

    If a symbol appears in more than one theme (a data integrity bug), returns
    'MULTIPLE' to make the conflict visible rather than silently picking one
    based on dict iteration order.
    """
    matches = [name for name, members in THEMES.items() if symbol in members]
    if len(matches) > 1:
        return 'MULTIPLE'
    return matches[0] if matches else None


def theme_exposure(positions, equity):
    """{theme: {'value', 'pct', 'symbols'}} for every theme with a holding."""
    out = {}
    for p in positions:
        th = theme_of(p["symbol"])
        if th is None:
            continue
        b = out.setdefault(th, {"value": 0.0, "symbols": []})
        b["value"] += float(p["market_value"])
        b["symbols"].append(p["symbol"])
    for b in out.values():
        b["pct"] = b["value"] / equity if equity > 0 else 0.0
        b["symbols"].sort()
    return out


def unclassified_exposure(positions, equity):
    """{'value', 'pct', 'symbols'} for held symbols no theme claims. A visible gap, not a
    silent one: these names are subject to no cap."""
    syms, val = [], 0.0
    for p in positions:
        if theme_of(p["symbol"]) is None:
            syms.append(p["symbol"])
            val += float(p["market_value"])
    return {"value": val, "pct": val / equity if equity > 0 else 0.0, "symbols": sorted(syms)}


def theme_cap_check(symbol, added_value, positions, equity, max_pct=MAX_THEME_PCT):
    """(ok, reason) for a proposed buy of `added_value` dollars of `symbol`.

    Refuses when the buy would push the symbol's theme past `max_pct` of equity. A symbol
    in no known theme is REFUSED (fail-closed) - the alternative is a new name buying
    through with no cap, which is exactly how the AI-hardware sleeve reached 75% of
    long market value.
    """
    th = theme_of(symbol)
    if th is None:
        # FAIL CLOSED. An unclassified symbol has no theme cap, so the cap cannot
        # constrain it. Refusing the buy is the safe default — the alternative is
        # a new AI name buying through with no cap, which is exactly how the
        # AI-hardware sleeve reached 75% of long market value.
        return False, (f"{symbol} is unclassified - no theme cap applies, "
                       f"refusing the buy. Add it to THEMES to allow it.")
    if th == 'MULTIPLE':
        return False, f"{symbol} appears in multiple themes - fix the THEMES map"
    if equity <= 0:
        # Fail CLOSED. This used to return True ("not evaluated"), which contradicted the
        # fail-closed contract of the order-path wrapper: a zero or unreadable equity
        # silently disabled the cap. If the denominator is unusable the limit is
        # unverifiable, so the buy is refused.
        return False, ("equity is unavailable or non-positive, so the theme cap cannot be "
                       "evaluated - refusing the buy")
    cur = theme_exposure(positions, equity).get(th, {}).get("value", 0.0)
    after = (cur + float(added_value)) / equity
    cur_pct = cur / equity
    if after > max_pct:
        return False, (f"{th} would be {after:.1%} of equity after this buy "
                       f"(cap {max_pct:.0%}, currently {cur_pct:.1%})")
    return True, f"{th} would be {after:.1%} of equity (cap {max_pct:.0%})"


def theme_cap_check_safe(symbol, added_value, positions, equity, max_pct=MAX_THEME_PCT):
    """Fail-CLOSED wrapper around theme_cap_check, for use on the order path.

    If the check cannot be evaluated the buy is REFUSED, not allowed. A risk limit that
    opens up whenever it fails to evaluate is not a limit - so an unreadable position
    value must block the order, loudly, rather than wave it through.
    """
    try:
        return theme_cap_check(symbol, added_value, positions, equity, max_pct)
    except Exception as e:
        return False, (f"theme cap could not be evaluated ({type(e).__name__}: {e}) "
                       f"- refusing the buy")


# ── thesis review (REPORT ONLY - never sells) ───────────────────────────────────────────

REVIEW_AFTER_DAYS = 180      # long enough to have a view
REVIEW_DRAWDOWN = 0.25       # 25% below cost is a real loss, not noise
STALE_AFTER_DAYS = 365       # a year under water is a stale thesis


def thesis_review(positions, held_days, review_after_days=REVIEW_AFTER_DAYS,
                  review_drawdown=REVIEW_DRAWDOWN, stale_after_days=STALE_AFTER_DAYS):
    """Flag positions for a human decision. Pure - returns a list, sells nothing.

    `held_days` maps symbol -> days held (None/absent means unknown age, which is not
    treated as old enough to judge). Two flags:

      STALE   held a year or more and still below cost
      LONG_AND_DOWN  held past the review window and down `review_drawdown` or more

    Deliberately not a stop loss. The owner's rule is that invested capital is never trimmed
    on weakness; this exists so that weakness is at least SURFACED rather than invisible.
    """
    out = []
    for p in positions:
        try:
            sym = p["symbol"]
        except (KeyError, TypeError):
            continue
        days = held_days.get(sym)
        if days is None:
            continue
        try:
            days = int(days)
            cost = float(p["qty"]) * float(p["avg_entry_price"])
            mv = float(p["market_value"])
        except (KeyError, TypeError, ValueError):
            # An unreadable row must not crash the scan. It is skipped, which does mean a
            # position with a corrupt value goes UNREVIEWED - so this is deliberately quiet
            # rather than pretending it was judged.
            continue
        if not (math.isfinite(cost) and math.isfinite(mv)) or cost <= 0:
            continue
        pl_pct = mv / cost - 1
        if not math.isfinite(pl_pct):
            continue

        # ORDER MATTERS: the deeper flag wins regardless of age. Testing STALE first (as
        # this did) made LONG_AND_DOWN unreachable past 365 days, so a position down 80%
        # after 500 days reported as merely "stale" and the severity was lost.
        # A position down >= review_drawdown is ALWAYS flagged, even if fresh — a 50%
        # crash in 100 days deserves attention even if the 180-day window hasn't passed.
        if pl_pct <= -review_drawdown:
            out.append({
                "symbol": sym, "flag": "LONG_AND_DOWN", "held_days": days,
                "pl_pct": pl_pct, "action": "REPORT_ONLY",
                "reason": (f"held {days}d and down {pl_pct:.1%} (threshold "
                           f"{-review_drawdown:.0%}) - review the thesis"),
            })
        elif days >= stale_after_days and pl_pct < 0:
            out.append({
                "symbol": sym, "flag": "STALE", "held_days": days,
                "pl_pct": pl_pct, "action": "REPORT_ONLY",
                "reason": (f"held {days}d and still {pl_pct:+.1%} - the thesis has had a "
                           f"year and has not worked; review it"),
            })
    out.sort(key=lambda r: r["pl_pct"])
    return out

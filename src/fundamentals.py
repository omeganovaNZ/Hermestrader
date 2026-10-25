"""Fundamentals gate — the missing third layer.

The technical screener has NO forward predictive power: run as of 2026-04-25 on the
500-name universe, its 102 picks returned +3.5% to 2026-10-25 versus +7.0% for SPY and
+8.3% for the average name in the same universe (see docs/ and the fair-test harness).
The names that actually held up were the ones that passed a FUNDAMENTAL check, not the
highest technical scores.

So the buy path now requires a verified fundamentals record. Alpaca's free tier provides
no fundamentals API, so the record is a curated registry: each entry carries the metrics,
the source, and the date it was verified. A symbol with no record is refused — the gate
fails closed, exactly like the theme cap.

HOW TO ADD AN ENTRY. Research the name from a primary source (company IR / SEC filing) or
an established outlet, record the figures and the source, and give it a date. Do not add a
name from a headline, a Reddit thread, or a price move. The registry is only as good as
the discipline of the entries in it.
"""

# symbol -> {revenue_growth, eps_growth, margin_trend, guidance, source, as_of}
# revenue_growth / eps_growth are year-over-year percentages for the latest reported quarter.
# margin_trend: "expanding" | "stable" | "contracting"
# guidance: "raised" | "maintained" | "cut"
FUNDAMENTALS = {
    "MSFT": {"revenue_growth": 18.0, "eps_growth": 23.0, "margin_trend": "expanding",
             "guidance": "raised", "source": "Microsoft IR FY26 Q4 (2026-07-29)", "as_of": "2026-07-29"},
    "ZBRA": {"revenue_growth": 18.0, "eps_growth": 74.0, "margin_trend": "expanding",
             "guidance": "raised", "source": "Zebra SEC 10-Q / Benzinga (2026-08-04)", "as_of": "2026-08-04"},
    "TMO": {"revenue_growth": 9.0, "eps_growth": 15.0, "margin_trend": "expanding",
            "guidance": "raised", "source": "Thermo Fisher IR Q3 2026 (2026-10-21)", "as_of": "2026-10-21"},
    "A": {"revenue_growth": 8.1, "eps_growth": 18.0, "margin_trend": "expanding",
          "guidance": "raised", "source": "Agilent IR Q3 FY26 (2026-08-26)", "as_of": "2026-08-26"},
    "EXPD": {"revenue_growth": 32.1, "eps_growth": 51.5, "margin_trend": "expanding",
             "guidance": "maintained", "source": "Expeditors Q2 2026 / MarketBeat", "as_of": "2026-08-04"},
    "NTAP": {"revenue_growth": 4.4, "eps_growth": 16.0, "margin_trend": "expanding",
             "guidance": "raised", "source": "NetApp IR Q3 FY26", "as_of": "2026-05-28"},
    "TXN": {"revenue_growth": 28.0, "eps_growth": 77.0, "margin_trend": "expanding",
            "guidance": "raised", "source": "TI IR Q3 2026 (2026-10-21)", "as_of": "2026-10-21"},
    "CRM": {"revenue_growth": 10.8, "eps_growth": 102.7, "margin_trend": "expanding",
            "guidance": "raised", "source": "Salesforce IR Q2 FY27 (SEC exhibit)", "as_of": "2026-08-26"},
    "WST": {"revenue_growth": 13.8, "eps_growth": 18.1, "margin_trend": "expanding",
            "guidance": "raised", "source": "West Pharma IR Q2 2026 (SEC exhibit)", "as_of": "2026-07-23"},
    "WAT": {"revenue_growth": 113.3, "eps_growth": 1.0, "margin_trend": "stable",
            "guidance": "maintained", "source": "Waters Q2 2026 / MarketBeat (M&A-inflated)", "as_of": "2026-08-04"},
    "VLO": {"revenue_growth": 0.0, "eps_growth": 518.0, "margin_trend": "expanding",
            "guidance": "maintained", "source": "Valero IR Q3 2026 (8-K)", "as_of": "2026-10-22"},
    "SWKS": {"revenue_growth": -3.1, "eps_growth": -18.4, "margin_trend": "contracting",
             "guidance": "maintained", "source": "Skyworks Q3 FY26 / MarketBeat", "as_of": "2026-07-28"},
    "NUE": {"revenue_growth": 23.6, "eps_growth": 10.0, "margin_trend": "stable",
            "guidance": "cut", "source": "Nucor Q3 2026 guidance / Investing.com", "as_of": "2026-09-17"},
    "HUM": {"revenue_growth": 4.0, "eps_growth": 7.0, "margin_trend": "stable",
            "guidance": "maintained", "source": "Humana Q3 2026 (Star ratings restored)", "as_of": "2026-10-21"},
    "TECH": {"revenue_growth": -2.0, "eps_growth": -2.0, "margin_trend": "contracting",
             "guidance": "cut", "source": "Bio-Techne IR Q3 FY26", "as_of": "2026-05-06"},
    "RVTY": {"revenue_growth": 1.3, "eps_growth": -3.9, "margin_trend": "contracting",
             "guidance": "cut", "source": "Revvity Q2 2026", "as_of": "2026-08-04"},
    "ASML": {"revenue_growth": 36.0, "eps_growth": 20.7, "margin_trend": "expanding",
             "guidance": "raised", "source": "ASML IR Q3 2026", "as_of": "2026-10-14"},
    "BE": {"revenue_growth": 138.0, "eps_growth": 526.7, "margin_trend": "contracting",
           "guidance": "raised", "source": "Bloom Energy Q3 2026 (negative FCF)", "as_of": "2026-10-23"},
}

# Gate thresholds. A name must clear ALL of these to be buyable.
MIN_REVENUE_GROWTH = 3.0     # % YoY, latest quarter
MIN_EPS_GROWTH = 0.0         # % YoY, latest quarter
MIN_MARGIN_TREND = "stable"  # "contracting" is refused
REFUSE_GUIDANCE_CUT = True   # a guidance cut is refused


def _margin_rank(trend):
    return {"expanding": 2, "stable": 1, "contracting": 0}.get(trend, -1)


def fundamental_check(symbol, min_revenue_growth=MIN_REVENUE_GROWTH,
                      min_eps_growth=MIN_EPS_GROWTH,
                      min_margin_trend=MIN_MARGIN_TREND,
                      refuse_guidance_cut=REFUSE_GUIDANCE_CUT):
    """(ok, reason) for buying `symbol` on its verified fundamentals.

    Fails CLOSED: no record, or a record that fails any threshold, is refused. The
    alternative — letting an unverified name through — is how a screen with no forward
    edge gets treated as a signal.
    """
    rec = FUNDAMENTALS.get(symbol)
    if rec is None:
        return False, (f"{symbol} has no verified fundamentals on record - refusing the "
                       f"buy. Research it from a primary source and add it to FUNDAMENTALS.")
    if rec.get("revenue_growth", -999) < min_revenue_growth:
        return False, (f"{symbol} revenue growth {rec.get('revenue_growth')}% is below "
                       f"the {min_revenue_growth}% floor")
    if rec.get("eps_growth", -999) < min_eps_growth:
        return False, (f"{symbol} EPS growth {rec.get('eps_growth')}% is below the "
                       f"{min_eps_growth}% floor")
    if _margin_rank(rec.get("margin_trend")) < _margin_rank(min_margin_trend):
        return False, f"{symbol} margin trend is {rec.get('margin_trend')}"
    if refuse_guidance_cut and rec.get("guidance") == "cut":
        return False, f"{symbol} guidance was cut"
    return True, (f"{symbol}: revenue +{rec['revenue_growth']}%, EPS +{rec['eps_growth']}%, "
                  f"margins {rec['margin_trend']}, guidance {rec['guidance']} "
                  f"[{rec['source']}, {rec['as_of']}]")


def fundamental_check_safe(symbol, **kw):
    """Fail-CLOSED wrapper, for use on the order path."""
    try:
        return fundamental_check(symbol, **kw)
    except Exception as e:
        return False, f"fundamentals gate could not be evaluated ({type(e).__name__}: {e}) - refusing the buy"


def fundamental_score(symbol):
    """A simple ranking score for the verified record (higher = stronger).

    Used to order cash-drag candidates. Returns -1 for a name with no usable record.
    """
    rec = FUNDAMENTALS.get(symbol)
    if rec is None:
        return -1.0
    score = 0.0
    score += max(0.0, float(rec.get("revenue_growth", 0.0))) * 1.0
    score += max(0.0, float(rec.get("eps_growth", 0.0))) * 1.0
    score += {"expanding": 30.0, "stable": 15.0, "contracting": 0.0}.get(rec.get("margin_trend"), 0.0)
    score += {"raised": 20.0, "maintained": 0.0, "cut": -20.0}.get(rec.get("guidance"), 0.0)
    return score

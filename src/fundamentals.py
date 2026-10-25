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

EPS CONVENTION — ONE RULE. Use GAAP diluted EPS growth for every name. `eps_basis` records
how it was applied so the convention stays auditable:
  "gaap"                  GAAP growth % is computable and used as-is.
  "gaap_adj"              GAAP was distorted by a DISCLOSED one-time item; the adjusted
                          growth is used, and the raw GAAP figures stay in
                          gaap_eps_prior / gaap_eps_current so the adjustment can be checked.
  "gaap_return_to_profit" GAAP went loss -> profit (no % change is meaningful); eps_growth
                          is None and the gate passes only if the raw GAAP figures corroborate
                          the swing. Never switch to non-GAAP to make a name pass — non-GAAP
                          is management-defined and systematically excludes SBC, a real cost.
"""

# symbol -> {revenue_growth, eps_growth, eps_basis, gaap_eps_prior, gaap_eps_current,
#            margin_trend, guidance, source, as_of}
# revenue_growth / eps_growth are year-over-year percentages for the latest reported quarter.
# eps_growth may be None when eps_basis is "gaap_return_to_profit".
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

    # ── 2026-10-26 additions (researched from primary sources; spot-verified) ─────────────
    # ONE convention: GAAP diluted EPS. `eps_basis` says how it was applied:
    #   gaap              GAAP growth % is computable and used as-is.
    #   gaap_adj          GAAP was distorted by a DISCLOSED one-time item, so the
    #                     adjusted growth is used; the raw GAAP figures are kept in
    #                     gaap_eps_prior/current so the adjustment is auditable.
    #   gaap_return_to_profit  GAAP went loss -> profit (no % change is meaningful);
    #                     eps_growth is None and the gate passes on the documented swing.
    # Raw GAAP figures (gaap_eps_prior / gaap_eps_current) are recorded for every name so
    # the convention can be checked without re-reading the filing. Two entries below
    # intentionally FAIL the gate (PTC, ILMN) - kept so the refusal is documented.
    "PLTR": {"revenue_growth": 92.8, "eps_growth": 192.9, "eps_basis": "gaap",
             "gaap_eps_prior": 0.14, "gaap_eps_current": 0.41,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "Palantir IR Q2 2026 press release (Business Wire, 2026-08-03)",
             "as_of": "2026-08-03",
             "note": "GAAP diluted EPS $0.14->$0.41; diluted share count +85% Y/Y mutes it (basic +214%). Latest = Q2 2026."},
    "DDOG": {"revenue_growth": 35.6, "eps_growth": 1100.0, "eps_basis": "gaap",
             "gaap_eps_prior": 0.01, "gaap_eps_current": 0.12,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "Datadog Q2 2026 press release / 8-K Ex-99.1 (2026-08-06)",
             "as_of": "2026-08-06",
             "note": "GAAP EPS off a near-zero base ($0.01->$0.12); non-GAAP $0.57->$0.65 (+14%). Latest = Q2 2026."},
    "PTC": {"revenue_growth": -6.8, "eps_growth": -12.0, "eps_basis": "gaap",
            "gaap_eps_prior": 1.17, "gaap_eps_current": 1.03,
            "margin_trend": "contracting",
            "guidance": "raised", "source": "PTC 10-Q Q3 FY2026 (SEC EDGAR accession 0001193125-26-328444)",
            "as_of": "2026-07-29",
            "note": "FAILS gate: revenue -6.8% (Kepware/ThingWorx divestiture), margins contracting. Kept to document the refusal."},
    "AMGN": {"revenue_growth": 9.5, "eps_growth": 64.9, "eps_basis": "gaap",
             "gaap_eps_prior": 2.65, "gaap_eps_current": 4.37,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "Amgen Q2 2026 8-K Ex-99.1 (2026-08-04)",
             "as_of": "2026-08-04",
             "note": "GAAP diluted EPS $2.65->$4.37; non-GAAP $6.02->$6.29 (+4.5%). Latest = Q2 2026."},
    "ILMN": {"revenue_growth": 9.4, "eps_growth": -9.4, "eps_basis": "gaap",
             "gaap_eps_prior": 1.49, "gaap_eps_current": 1.35,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "Illumina Q2 FY2026 8-K Ex-99.1 (2026-07-30)",
             "as_of": "2026-07-30",
             "note": "FAILS gate on GAAP diluted EPS -9.4% ($1.49->$1.35); non-GAAP +10.1% (excludes GRAIL/SomaLogic amortization). Latest = Q2 FY2026."},
    "P": {"revenue_growth": 37.7, "eps_growth": 50.0, "eps_basis": "gaap",
          "gaap_eps_prior": 0.14, "gaap_eps_current": 0.21,
          "margin_trend": "expanding",
          "guidance": "raised", "source": "Everpure (formerly Pure Storage, ticker P) Q2 FY2027 8-K Ex-99.1 (2026-08-26)",
          "as_of": "2026-08-26",
          "note": "GAAP diluted EPS $0.14->$0.21; non-GAAP $0.43->$0.70 (+62.8%). Ticker P = Everpure, renamed from Pure Storage."},
    "CRWD": {"revenue_growth": 26.0, "eps_growth": None, "eps_basis": "gaap_return_to_profit",
             "gaap_eps_prior": -0.07, "gaap_eps_current": 0.01,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "CrowdStrike Q2 FY2027 8-K Ex-99.1 (2026-08-26)",
             "as_of": "2026-08-26",
             "note": "GAAP diluted EPS returned to profit: $(0.07) -> $0.01 (no % change meaningful). Non-GAAP $0.23->$0.31 (+34.8%)."},
    "MXL": {"revenue_growth": 72.0, "eps_growth": None, "eps_basis": "gaap_return_to_profit",
            "gaap_eps_prior": -0.52, "gaap_eps_current": 0.30,
            "margin_trend": "expanding",
            "guidance": "raised", "source": "MaxLinear Q3 2026 8-K Ex-99.1 (accession 0001288469-26-000060, 2026-10-22)",
            "as_of": "2026-10-22",
            "note": "GAAP diluted EPS returned to profit: $(0.52) -> $0.30. Non-GAAP $0.14->$0.62 (+343%). Q3 2026 (ended 2026-09-30) is the latest."},
    "LITE": {"revenue_growth": 109.3, "eps_growth": 267.0, "eps_basis": "gaap_adj",
             "gaap_eps_prior": 2.96, "gaap_eps_current": -84.65,
             "margin_trend": "expanding",
             "guidance": "raised", "source": "Lumentum Q4 FY2026 IR press release / 8-K Ex-99.1 (2026-08-11)",
             "as_of": "2026-08-11",
             "note": "Raw GAAP $(84.65) vs $2.96, distorted by a one-time $7.8B debt-extinguishment loss; adjusted diluted EPS $0.88->$3.23 (+267%) used per the gaap_adj rule. MEDIUM confidence."},
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
    # EPS: one GAAP convention. `eps_basis` records how it was applied:
    #   gaap / gaap_adj  -> eps_growth is a % and is tested against the floor
    #   gaap_return_to_profit -> eps_growth is None; pass only on a verified
    #                       loss -> profit swing (raw GAAP figures must corroborate)
    basis = rec.get("eps_basis", "gaap")
    if basis == "gaap_return_to_profit":
        prior = rec.get("gaap_eps_prior")
        cur = rec.get("gaap_eps_current")
        if prior is None or cur is None or not (prior < 0 < cur):
            return False, (f"{symbol} is marked 'gaap_return_to_profit' but the raw GAAP "
                           f"EPS figures do not corroborate a loss -> profit swing "
                           f"(prior={prior}, current={cur}) - refusing")
    else:
        eps = rec.get("eps_growth")
        if eps is None or float(eps) < min_eps_growth:
            return False, (f"{symbol} EPS growth {eps}% is below the "
                           f"{min_eps_growth}% floor")
    if _margin_rank(rec.get("margin_trend")) < _margin_rank(min_margin_trend):
        return False, f"{symbol} margin trend is {rec.get('margin_trend')}"
    if refuse_guidance_cut and rec.get("guidance") == "cut":
        return False, f"{symbol} guidance was cut"
    eps_txt = ("returned to GAAP profit" if basis == "gaap_return_to_profit"
               else f"EPS +{rec.get('eps_growth')}%")
    return True, (f"{symbol}: revenue +{rec['revenue_growth']}%, {eps_txt}, "
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
    eps = rec.get("eps_growth")
    if eps is not None:
        score += max(0.0, float(eps)) * 1.0
    else:
        # gaap_return_to_profit: a small credit for the return to profitability
        score += 10.0
    score += {"expanding": 30.0, "stable": 15.0, "contracting": 0.0}.get(rec.get("margin_trend"), 0.0)
    score += {"raised": 20.0, "maintained": 0.0, "cut": -20.0}.get(rec.get("guidance"), 0.0)
    return score

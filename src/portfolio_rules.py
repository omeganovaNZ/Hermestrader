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

LIMITATION: Alpaca's free tier provides no sector or industry field, so the theme map
below is maintained by hand from public filings. A symbol that is not listed is
"unclassified" and no theme cap applies to it, so a new name slips through until it is
added. `test_portfolio_rules.py` asserts that every currently-held symbol is classified,
and `unclassified_exposure()` reports whatever is unclassified so the gap stays visible.
"""

import math

# ── theme (sleeve) cap ──────────────────────────────────────────────────────────────────

MAX_THEME_PCT = 0.40

# De-concentration: while the AI-hardware sleeve is over 30% of equity it is being
# worked down, so new AI_HARDWARE buys are frozen at a 30% ceiling (i.e. none can
# land while it is already above 30%). Once it is diluted below 30%, the normal 40%
# cap applies again. This is the hysteresis that stops the sleeve re-inflating
# while we are trying to shrink it.
AI_HARDWARE_DECONCENTRATION_TRIGGER = 0.30
AI_HARDWARE_DECONCENTRATION_CAP = 0.30

# One theme per symbol. The map is a RISK map, not a sector map: a theme is a group of
# names that MOVE TOGETHER, because correlation is what makes a sleeve a risk.
#
# HOW IT WAS BUILT (2026-10-22). Universe: 504 symbols - the screener's 500 plus every
# position held in any of the three paper accounts. Window: 2024-10-01..2026-10-21, 515
# daily returns. Correlation matrix -> average-linkage hierarchical clustering -> clusters
# reviewed and named by industry -> membership assigned by seed-portfolio correlation
# (each theme seeded with names whose industry is unambiguous) -> explicit industry
# corrections where the two disagreed. Tooling: scratch/_themes_v4.py.
#
# 22 themes, 532 symbols, every symbol classified exactly once.
#
# The 504 above came from the screener universe. A further 24 names were carried over
# from the previous map because they are NOT in that universe (VICR, TLN, OKLO, ENPH,
# DINO, CVI, S, DRH, OUT, MXL, SNDK, ARM, ALAB, COHU, SIMO, NET, IOVA, TXG, CRSP,
# NTLA, BEAM, EDIT, RPRX, TVTX). They were assigned by the same method - bars fetched,
# correlated against every theme - and the measurement agreed with the industry reading
# in every case: NET +0.539 and S +0.602 to CYBERSECURITY, DINO +0.485 and CVI +0.375 to
# POWER_ENERGY, COHU +0.516 / ARM +0.472 / SIMO +0.411 / ALAB +0.408 / MXL +0.398 to
# AI_HARDWARE, OKLO +0.361 to POWER_FOR_AI. Where the measurement was weak the industry
# reading was used and the name is flagged: ENPH is the weakest fit on the whole map
# (best measured AI_HARDWARE +0.223, second MATERIALS +0.196, POWER_FOR_AI +0.172 - it is
# a solar microinverter maker, not a data-centre power name) and is kept in POWER_FOR_AI
# only because that is the nearest power-equipment sleeve. DRH and OUT are REITs;
# BEAM/CRSP/EDIT/NTLA/TVTX/IOVA/RPRX are clinical-stage biotechs. Tooling:
# scratch/_add_dropped2.py.
#
# A further four screener symbols were added 2026-10-22 after test_the_whole_screener_universe
# _is_classified caught them: FDXF (FedEx Freight - INDUSTRIALS), HONA (Honeywell Aerospace -
# AEROSPACE_DEFENSE), Q (Qnity Electronics, the DuPont semiconductor-materials spinoff -
# AI_HARDWARE), SKYD (Skydance, the Paramount/Warner Bros. Discovery combine -
# COMMUNICATION_SERVICES). All four are recent listings or spinoffs with NO price history, so
# unlike every other entry they could not be measured - they are assigned by industry alone.
# That is the one place the map rests on a description rather than a correlation, and it is
# worth revisiting once they have a year of bars.
#
# COHERENCE (mean pairwise correlation INSIDE each theme, same window) - the number that
# says whether a sleeve is a real risk factor or just a label:
#   CYBERSECURITY +0.672        FINANCIALS +0.643       REGULATED_UTILITIES +0.599
#   INSURANCE +0.561            POWER_ENERGY +0.535      AI_HARDWARE +0.442
#   REIT +0.441                 POWER_FOR_AI +0.439      INDUSTRIALS +0.389
#   AEROSPACE_DEFENSE +0.383    AI_SOFTWARE +0.365       MEDTECH +0.346
#   MEGA_INTERNET +0.347        CONSUMER_STAPLES +0.339 MATERIALS +0.339
#   BIG_PHARMA +0.328           FINTECH +0.309           CONSUMER_DISCRETIONARY +0.309
#   HIGH_BETA_TECH +0.276       COMMUNICATION_SERVICES +0.260
#   HEALTHCARE_SERVICES +0.256  HEALTHCARE_INSURERS +0.462
# The weak ones are weak honestly: COMMUNICATION_SERVICES and HEALTHCARE_SERVICES are
# closer to "everything in this industry" than to one risk factor. They are kept whole
# because splitting them would create 10-name sleeves the 40% cap could never bind.
#
# THE RKLB CASE - industry and correlation disagree, and the map follows the correlation.
# RKLB is an aerospace/launch/satellite-components business: "space exploration, launch
# services, satellite components", in the aerospace & defense industry. It sat in
# AI_HARDWARE. Measured, its correlation is +0.360 with AI_HARDWARE, +0.378 with
# POWER_FOR_AI, and highest of all with the high-beta tech group (+0.44) - its nearest
# neighbours are PLTR, DDOG, SNOW, COIN, HOOD, TSLA, APP, AXON. Industry says defence;
# price behaviour says high-beta tech. It is in HIGH_BETA_TECH, because the cap exists to
# bound CORRELATED exposure, and correlating RKLB with MRVL/MU/NVDA would understate the
# risk it adds to a book that already holds TSLA and PLTR. Flagged here because the
# industry reading is not wrong - it is simply not the risk axis.
#
# POWER_FOR_AI vs POWER_ENERGY, kept separate although they correlate. POWER_FOR_AI is power
# INFRASTRUCTURE whose demand is driven by AI/data-centre load; POWER_ENERGY is fuel
# PRODUCERS whose driver is the commodity. Measured each name against the mean of both
# sleeves (tools: scratch/power_for_ai_membership.py), corr vs AI_HARDWARE / vs POWER_ENERGY:
#   VRT +0.481/0.122  ETN +0.500/0.177  PWR +0.430/0.167  GEV +0.424/0.118
#   CEG +0.368/0.119  BE +0.363/0.149   NRG +0.338/0.167  VST +0.316/0.147
# ...against the fuel producers, which track energy by a wide margin:
#   MPC 0.149/0.492   PSX 0.139/0.490   VLO 0.140/0.487   CVX 0.020/0.430  XOM -0.019/0.418
# Every member above tracks AI by >= 0.17 and energy by <= 0.18. The split is clean.
# BE (102% annualised vol) and GEV (53%) are semis-like in volatility, not utility-like:
# the oil/gas names run ~29% and AI hardware ~55%.
#
# TICKER COLLISIONS RESOLVED (Alpaca's free tier has no sector field, so names were read
# from filings): P = Everpure, Inc. (formerly Pure Storage) - AI-era data storage hardware,
# hence AI_HARDWARE. KOD = Kodiak Sciences - a clinical-stage eye-disease biotech, hence
# BIG_PHARMA, NOT the lithium junior that shares the ticker on the news feed. MPC = Marathon
# Petroleum. SPR is absent because Spirit AeroSystems was acquired by Boeing and delisted.
THEMES = {
    "AI_HARDWARE": {
        "ADI", "AMAT", "AMD", "ANET", "APH", "ASML", "AVGO", "CDW", "CIEN", "COHR",
        "CSCO", "DELL", "FFIV", "FIX", "FLEX", "GLW", "GNRC", "HPE", "HPQ", "HUBB",
        "INTC", "JBL", "JCI", "KEYS", "KLAC", "LITE", "LRCX", "MCHP", "MPWR", "MRVL",
        "MSI", "MU", "NTAP", "NVDA", "NXPI", "ON", "P", "QCOM", "STX", "SWKS", "TEL",
        "TER", "TSM", "TXN", "WDC", "ALAB", "ARM", "COHU", "MXL", "Q", "SIMO", "SNDK",
    },
    "AI_SOFTWARE": {
        "ACN", "ADBE", "ADP", "ADSK", "AKAM", "APP", "BR", "CDNS", "CPRT", "CRM",
        "CSGP", "CTSH", "DDOG", "GDDY", "GEN", "IBM", "INTU", "IT", "JKHY", "NOW",
        "ORCL", "PAYX", "PLTR", "PTC", "ROP", "SNOW", "SNPS", "TWLO", "TYL", "VEEV",
        "WDAY",
    },
    "CYBERSECURITY": {"CRWD", "FTNT", "NET", "OKTA", "PANW", "S"},
    "POWER_FOR_AI": {
        "AES", "BE", "CEG", "ENPH", "ETN", "FSLR", "GE", "GEV", "NRG", "OKLO", "PWR",
        "TLN", "TT", "VICR", "VRT", "VST",
    },
    "POWER_ENERGY": {
        "APA", "BKR", "COP", "CVX", "DVN", "EOG", "EQT", "EXE", "FANG", "HAL", "KMI",
        "MPC", "OKE", "OXY", "PSX", "SLB", "TPL", "TRGP", "VLO", "WMB", "XOM",
        "CVI", "DINO",
    },
    "REGULATED_UTILITIES": {
        "AEE", "AEP", "ATO", "AWK", "CMS", "CNP", "D", "DTE", "DUK", "ED", "EIX", "ES",
        "ETR", "EVRG", "EXC", "FE", "LNT", "NEE", "NI", "PCG", "PEG", "PNW", "PPL", "SO",
        "SRE", "WEC", "XEL",
    },
    "FINANCIALS": {
        "AMP", "APO", "ARES", "AXP", "BAC", "BEN", "BLK", "BNY", "BX", "C", "CBRE",
        "CFG", "COF", "FITB", "GS", "HBAN", "IVZ", "JPM", "KEY", "KKR", "MET", "MS",
        "MTB", "NTRS", "PFG", "PNC", "PRU", "RF", "RJF", "SCHW", "STT", "SYF", "TFC",
        "TROW", "USB", "WFC",
    },
    "INSURANCE": {
        "ACGL", "AFL", "AIG", "AIZ", "AJG", "ALL", "AON", "BRO", "CB", "CINF", "EG",
        "ERIE", "GL", "HIG", "L", "MRSH", "PGR", "TRV", "WRB", "WTW",
    },
    "FINTECH": {
        "AI", "CBOE", "CME", "COIN", "CPAY", "CVNA", "EFX", "FDS", "FICO", "FIS",
        "FISV", "GPN", "HOOD", "IBKR", "ICE", "MA", "MCO", "MSCI", "NDAQ", "PYPL",
        "RDDT", "SPGI", "V", "VRSK", "VRSN", "XYZ",
    },
    "BIG_PHARMA": {
        "ABBV", "AMGN", "BIIB", "BMY", "GILD", "INCY", "JNJ", "KOD", "LLY", "MRK",
        "MRNA", "PFE", "REGN", "VRTX", "VTRS", "BEAM", "CRSP", "EDIT", "IOVA", "NTLA",
        "RPRX", "TVTX",
    },
    "MEDTECH": {
        "A", "ABT", "ALGN", "BAX", "BDX", "BSX", "COO", "CRL", "DGX", "DHR", "DXCM",
        "EW", "GEHC", "HSIC", "IDXX", "ILMN", "IQV", "ISRG", "LH", "MDT", "MTD", "PODD",
        "RMD", "RVTY", "SOLV", "STE", "SYK", "TECH", "TMO", "TXG", "VLTO", "WAT", "WST",
        "ZBH", "ZTS",
    },
    "HEALTHCARE_INSURERS": {"CI", "CNC", "ELV", "HUM", "UNH"},
    "HEALTHCARE_SERVICES": {"CAH", "COR", "CVS", "DVA", "HCA", "MCK", "UHS"},
    "MEGA_INTERNET": {
        "AAPL", "ABNB", "AMZN", "BKNG", "DASH", "EBAY", "EXPE", "GOOG", "GOOGL",
        "META", "MSFT", "NFLX", "NWS", "NWSA", "UBER",
    },
    "COMMUNICATION_SERVICES": {
        "CHTR", "CMCSA", "DIS", "FOX", "FOXA", "OMC", "SKYD", "T", "TKO", "TMUS", "TTWO", "VZ",
    },
    "HIGH_BETA_TECH": {"AXON", "RKLB", "SMCI", "TSLA"},
    "CONSUMER_STAPLES": {
        "CHD", "CL", "CLX", "COST", "EL", "GIS", "HRL", "HSY", "KDP", "KHC", "KMB", "KO",
        "KR", "KVUE", "MDLZ", "MKC", "MNST", "MO", "PEP", "PG", "PM", "SJM", "STZ", "SYY",
        "TSN", "WMT",
    },
    "CONSUMER_DISCRETIONARY": {
        "APTV", "AZO", "BBY", "CASY", "CCL", "CMG", "DAL", "DECK", "DG", "DHI", "DLTR",
        "DPZ", "DRI", "F", "GM", "GRMN", "HAS", "HD", "HLT", "LEN", "LOW", "LULU", "LUV",
        "LVS", "LYV", "MAR", "MCD", "MGM", "NCLH", "NKE", "NVR", "ORLY", "PHM", "RCL",
        "RL", "ROST", "SBUX", "TGT", "TJX", "TPR", "TSCO", "UAL", "ULTA", "WSM", "WYNN",
        "YUM",
    },
    "INDUSTRIALS": {
        "ALLE", "AME", "CARR", "CAT", "CHRW", "CMI", "CSX", "CTAS", "DE", "DOV", "ECHO",
        "EME", "EMR", "EXPD", "FAST", "FDX", "FERG", "FTV", "GWW", "HON", "IEX", "IR",
        "ITW", "J", "JBHT", "LII", "MMM", "NDSN", "NSC", "ODFL", "OTIS", "PCAR", "PH",
        "PNR", "ROK", "ROL", "RSG", "SNA", "TDY", "TRMB", "UNP", "UPS", "URI", "WAB",
        "WM", "XYL", "ZBRA", "FDXF",
    },
    "AEROSPACE_DEFENSE": {
        "BA", "GD", "HII", "HONA", "HWM", "LDOS", "LHX", "LMT", "NOC", "RTX", "TDG", "TXT",
    },
    "REIT": {
        "AMT", "ARE", "BXP", "CCI", "CPT", "CTRE", "DLR", "DOC", "EQIX", "ESS", "EXR",
        "FRT", "HST", "INVH", "IRM", "KIM", "MAA", "O", "PK", "PLD", "PSA", "REG",
        "SBAC", "SPG", "UDR", "VICI", "VMRK", "VTR", "WELL", "DRH", "OUT",
    },
    "MATERIALS": {
        "ADM", "ALB", "AMCR", "AOS", "APD", "AVY", "BALL", "BG", "CF", "CRH", "DD",
        "DOW", "ECL", "FCX", "GPC", "IFF", "IP", "LIN", "LYB", "MAS", "MLM", "MOS",
        "NEM", "NUE", "PKG", "PPG", "SHW", "STLD", "SW", "SWK", "VMC", "WY",
    },
}

# ── index funds (ETFs) ─────────────────────────────────────────────────────────────
#
# The books are high-beta and concentrated (portfolio vol ~3-4x the market), and the
# lowest-volatility, steadiest growth available is an index fund. But `theme_of()` only
# knew stocks, so an ETF was UNCLASSIFIED and `theme_cap_check` refused it — an ETF was
# not "uncapped", it was UNBUYABLE. These entries make index funds a first-class sleeve
# with its own cap, so diversification can actually be bought.
#
# Verified over the 12 months to 2026-10-25 (see docs/): the steady compounders are
# SCHD (+35%, vol 11%, DD -7%), XLV (+25%, vol 16%), VTV/RSP (+15-22%, vol 10-12%);
# the growth indexes QQQ/VGT/XLK (+15-24%, vol 20-26%). Leveraged funds are listed only
# so they are CLASSIFIED (and capped); they are not recommended for a core holding.
#
# Preferred first destination for idle cash (cash_drag) and redeployed trims: the
# steady compounders above, in priority order. The cap check still applies to each.
ETF_CASH_DRAG_CANDIDATES = ["SCHD", "XLV", "VTV", "RSP", "SPY"]

MAX_ETF_PCT = 0.40

ETF_THEMES = {
    "BROAD_MARKET": {"SPY", "VOO", "IVV", "VTI", "RSP", "QUAL", "MTUM", "VOOG", "VOOV"},
    "GROWTH_INDEX": {"QQQ", "VGT", "XLK", "IYW", "QTEC", "IGV", "IGM", "SKYY", "FNGU", "FNGS"},
    "DIVIDEND_VALUE": {"SCHD", "VYM", "SDY", "NOBL", "DGRO", "JEPI", "VTV", "IVE"},
    "SECTOR": {
        "XLV", "XLE", "VDE", "XLF", "XLI", "IHI", "XLC", "XLU", "SMH", "SOXX",
        "ICLN", "TAN", "QCLN", "PBW", "GLD", "IAU", "SLV",
    },
    "LEVERAGED": {"TQQQ", "QLD", "SSO", "UPRO", "SPXL", "TECL", "SOXL", "LABU", "WEBL"},
}


def etf_theme_of(symbol):
    """The ETF sleeve a symbol belongs to, or None if it is not a known ETF."""
    matches = [name for name, members in ETF_THEMES.items() if symbol in members]
    if len(matches) > 1:
        return "MULTIPLE"
    return matches[0] if matches else None


def etf_exposure(positions, equity):
    """{etf_theme: {'value','pct','symbols'}} for every ETF sleeve with a holding."""
    out = {}
    for p in positions:
        th = etf_theme_of(p["symbol"])
        if th is None:
            continue
        b = out.setdefault(th, {"value": 0.0, "symbols": []})
        b["value"] += float(p["market_value"])
        b["symbols"].append(p["symbol"])
    for b in out.values():
        b["pct"] = b["value"] / equity if equity > 0 else 0.0
        b["symbols"].sort()
    return out


def etf_cap_check_safe(symbol, added_value, positions, equity, max_pct=MAX_ETF_PCT):
    """(ok, reason) for buying an ETF. Fails CLOSED, same contract as the stock cap.

    An unknown symbol (not a stock theme, not an ETF sleeve) is refused: an unclassified
    symbol escapes every cap, which is how a sleeve runs away.
    """
    th = etf_theme_of(symbol)
    if th is None:
        return False, f"{symbol} is neither a known stock theme nor a known ETF sleeve - refusing the buy"
    if th == "MULTIPLE":
        return False, f"{symbol} appears in multiple ETF sleeves - fix the map"
    if equity <= 0:
        return False, "equity is unavailable or non-positive - refusing the buy"
    cur = etf_exposure(positions, equity).get(th, {}).get("value", 0.0)
    after = (cur + float(added_value)) / equity
    if after > max_pct:
        return False, (f"{th} would be {after:.1%} of equity after this buy "
                       f"(ETF cap {max_pct:.0%}, currently {cur/equity:.1%})")
    return True, f"{th} would be {after:.1%} of equity (ETF cap {max_pct:.0%})"


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
    """{theme: {'value', 'pct', 'symbols'}} for every theme with a holding.

    Includes ETF sleeves (see ETF_THEMES) so index funds are visible on every scan
    rather than silently absent from the exposure report.
    """
    out = {}
    for p in positions:
        th = theme_of(p["symbol"]) or etf_theme_of(p["symbol"])
        if th is None or th == "MULTIPLE":
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
        if theme_of(p["symbol"]) is None and etf_theme_of(p["symbol"]) is None:
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
        # Not a stock theme. If it is a known ETF sleeve, route it to the ETF cap;
        # otherwise FAIL CLOSED — an unclassified symbol has no cap at all, which is
        # how the AI-hardware sleeve reached 75% of long market value.
        if etf_theme_of(symbol) is not None:
            return etf_cap_check_safe(symbol, added_value, positions, equity)
        return False, (f"{symbol} is unclassified - no theme or ETF cap applies, "
                       f"refusing the buy. Add it to THEMES or ETF_THEMES to allow it.")
    if th == 'MULTIPLE':
        return False, f"{symbol} appears in multiple themes - fix the THEMES map"
    # De-concentration hysteresis: freeze AI_HARDWARE growth while it is over the
    # trigger, so the sleeve is worked down instead of re-inflating.
    if th == "AI_HARDWARE" and equity and equity > 0:
        try:
            _cur = theme_exposure(positions, equity).get("AI_HARDWARE", {}).get("value", 0.0)
            if (_cur / equity) >= AI_HARDWARE_DECONCENTRATION_TRIGGER:
                max_pct = min(max_pct, AI_HARDWARE_DECONCENTRATION_CAP)
        except Exception:
            pass
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

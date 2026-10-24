# Strategic Theses — Watch Triggers

Two structural theses the owner wants tracked. Neither is a signal to trade today. Both are
event-triggered watchlists: they name WHAT to look at when the event happens, not WHEN it
will happen. Recorded 2026-10-23.

**How to read this file.** Every thesis below carries the measured evidence that supports it
and, where the premise did not survive testing, the measured result that refuted it. A thesis
with a refuted premise stays in this file on purpose — re-proposing it from memory is how a
dead idea gets rebuilt. Do not turn any of these into an automatic buy. Every entry still has
to pass the normal gates: theme cap, 8% entry cap, multiple confirming signals, thesis review.

---

## THESIS 1 — If China moves on Taiwan, own fabs and equipment OUTSIDE Taiwan

**The premise.** TSMC holds ~73% of the global pure-play foundry market (Counterpoint, Q2 2026,
second consecutive quarter at that level). Taiwan holds ~92% of leading-edge (<=7nm) capacity.
A blockade or invasion would constrain advanced chip supply worldwide. The obvious trade is
"buy the foundries that are not in Taiwan" — the capacity that can still ship.

**The premise is directionally right but the trade as stated DOES NOT WORK, and this was
measured rather than assumed.** Two tests, both on 2026 daily SIP bars:

1. **Correlation, not substitution.** An equal-weight basket of 38 non-Taiwan fab and equipment
   names (INTC, GFS, TXN, ON, MCHP, NXPI, ADI, ASML, AMAT, LRCX, KLAC, TER, MU, WDC, STX, NTAP,
   STM, WOLF, and others) against a Taiwan-exposed basket (TSM, UMC, MU) over 2026-01-15 to
   2026-10-22, 193 sessions: **correlation +0.840**. They are the same trade, not opposite ones.

2. **Beta, not alpha.** Regressing the offshore basket's daily return on TSM's daily return:
   **beta +0.790, alpha +0.141%/day, correlation +0.636**. A substitution trade needs beta > 1
   (it moves MORE when TSMC moves) and alpha > 0. Measured beta 0.79 means the offshore basket
   moves 0.79x as much as TSM — it is a smaller version of the same exposure, not a hedge.

3. **On TSM's 10 biggest up/down days, the offshore basket's mean excess return was -0.11pp.**
   No divergence. There is no evidence that a Taiwan shock separates these names.

**Why the naive version fails.** "A fab outside Taiwan" is not the unit of diversification the
market prices. ASML, LRCX, AMAT and KLAC are Dutch/American *equipment* makers whose leading-edge
tools are themselves part of TSMC's supply chain — they sell into the same bottleneck. INTC and
GFS run mature nodes that cannot substitute for a 3nm AI accelerator. The only name that would
genuinely benefit from a Taiwan outage is one with advanced-node capacity outside the island, and
that is TSMC's own Arizona fab — which is TSM, the thing being disrupted.

**What to actually watch for, if the event happens:**

| What | Why | Status |
|---|---|---|
| TSMC Arizona Fab 2 / Fab 3 ramp | TSMC's own non-Taiwan leading-edge capacity. Fab 1 ramping ~30k wpm, Fab 2 tool move-in Q4 2026 with N3 in Q3 2027, Fab 3 move-in Sep 2027 | TSM already held in Pattern Match |
| Samsung Taylor, Texas | The only non-Taiwan 2nm line with volume ambitions; 20k wpm targeted 2H2027, Fab 2 groundbreaking Nov 2026 for 2030 | Not in the theme map — see buyability note |
| Intel Foundry external customers | First named external customer (Fortinet, Intel 4) landed Jul 2026, three years after the node entered HVM. External revenue $174M in Q1 2026 — real but immaterial | INTC classified AI_HARDWARE |
| GlobalFoundries Malta NY | Chosen 14 Oct 2026 to operate two 300mm fabs under a US-Japan initiative worth up to $21B; first fab targets 900k wafers/yr from 2029 | GFS unclassified — see buyability note |
| Mature-node IDMs with Western fabs | TXN (Lehi LFAB2), ON, MCHP, NXPI, ADI — the layer most exposed to Taiwan price hikes | All classified AI_HARDWARE |

**The honest read.** The thesis is a real structural risk, but "buy fabs elsewhere" is not the
expression of it. The trade that would work is a *supply-chain reallocation* trade — the names
that win share of the constrained demand — and that is a fundamentals question about which
fab can actually run the node, not a geographic screen. If this event occurs, it is a
**research task**, not a screen: establish which non-Taiwan line can run which node, then
check it against the theme cap. Do not buy the geographic screen on its own.

---

## THESIS 2 — When the Iran war ends and oil normalises, own the beneficiaries of cheap energy

**The premise.** Oil is the dominant macro driver of 2026. Brent was ~$71 the day before the
US-Israel strikes began on 28 Feb 2026, spiked to ~$118 by 31 Mar, fell back to ~$71 by 1 Jul,
rebounded above $100 in late July, and is now >$115 — up ~60% since the war began, highest since
May. The Strait of Hormuz has been largely blocked since 28 Feb. The Fed has responded with its
first hikes since 2023 (to 3.75–4.00%, with one more projected), and PCE inflation hit 4.1% in
May against a 2.5% pace a year earlier.

**When the war ends, oil falls, and that transmits through three channels — in this order of
confidence.** Measured on 2026-01-16 to 2026-10-22 daily bars (193 sessions), oil proxy
(average of USO and BNO) +128% over the window. Beta is the daily return sensitivity to the oil
proxy; "oil coef" is the oil sensitivity after removing the market factor.

### Channel 1 — Airlines and cruise lines. STRONG, and it is the single cleanest effect.

    sym    oil beta   oil coef (market-adj)   perf vs 27-Feb
    JBLU      -0.68         -0.49                -52.2%
    CCL       -0.63         -0.48                -13.2%
    ALK       -0.63           —                  -31.4%
    UAL       -0.59         -0.41                 -4.0%
    AAL       -0.58         -0.45                 -3.6%
    NCLH      -0.58         -0.44                -37.3%
    LUV       -0.48         -0.37                -13.5%
    DAL       -0.42         -0.28                +21.6%
    RCL       -0.41           —                   -6.5%

Airlines are the cleanest beneficiary because fuel is roughly 25% of operating costs and
tickets are sold weeks or months before fuel is bought — a genuine margin squeeze when oil
rises, and a genuine margin release when it falls. IATA cut its global airline profit forecast
nearly in half on a jet-fuel price shock of ~70% year over year. Delta is the outlier: it is
flat-to-up (+21.6% vs pre-war) while every other major fell, because it owns the Trainer
refinery (Monroe Energy) — a physical fuel hedge no other US major has. **That means DAL is the
worst expression of this thesis, not the best: it is already hedged.** UAL, AAL and JBLU do not
hedge and show the strongest negative oil beta.

### Channel 2 — Consumer real incomes and retail. WEAK, and it needs its own justification.

    sym    oil beta   perf vs 27-Feb
    KSS       -0.37         +55.2%
    RL        -0.27          +6.2%
    M         -0.26         +25.6%
    TPR       -0.26         -26.0%
    ABNB      -0.26         +30.1%
    HD        -0.25         -12.0%
    LOW       -0.25         -21.4%
    WMT       -0.03          -4.7%
    COST      +0.01          +1.0%
    CZR       -0.00         +16.0%

The oil beta here is an order of magnitude weaker than airlines', and the performance column
scatters all over the place. The mechanism (cheaper petrol → more disposable income → more
discretionary spend) is real in theory, but WMT at -0.03 and COST at +0.01 show it is not
measurable in this window. Retail is driven by its own cycle, tariffs and inventory position.
**Do not present retail as an oil thesis.** It is a rate-cut thesis at best, and it needs a
separate test.

### Channel 3 — Freight and shipping. WRONG DIRECTION — the surcharge is a pass-through.

    FDX       -0.13    UPS    -0.13    XPO    -0.19    ODFL   -0.18    JBHT   -0.12    CHRW   +0.02

Near-zero betas, and the reason is structural: FedEx and UPS fuel surcharges are indexed to
published diesel benchmarks and move weekly, so the cost passes through to the shipper rather
than being absorbed as margin. Parcel surcharges have become a structural ~9% of total invoice
cost (15%+ for many shippers). A fall in diesel lowers the *invoiced* price, not the carrier's
profit. **The owner's intuition that shipping benefits is not supported.** The beneficiary of
cheaper freight is the *shipper* — the retailers and manufacturers in Channel 2.

### What loses when oil falls (the mirror image, useful as a hedge or an exit trigger)

    APA   +0.66    OXY  +0.57    FANG +0.57    DVN  +0.55    EOG  +0.46    COP  +0.45
    XOM   +0.40    CVX  +0.37    MPC  +0.32    VLO  +0.31    PSX  +0.30    XLE  +0.34

Note MPC +83.1% and VLO +70.9% over the window — refiners have been the best performers in the
whole market while oil was high. They are the most exposed to the normalisation, and they are
the names the owner already holds (CVX in Pattern Match, 18.6% of equity).

### The transmission channel that matters most for the whole book

The Fed hiked in Sep 2026 for the first time since 2023, to 3.75–4.00%, and projects one more
by year-end (~4.1%). **That is a rate-cut thesis, not just a fuel-cost thesis.** If oil
normalises, inflation falls, the hiking cycle ends, and that is a broad multiple tailwind —
which is a bigger deal for a long-duration growth book than any single name's fuel line.
Saying "buy airlines when oil falls" understates it. The correct framing is: **oil normalisation
ends a rate-hike cycle, and the beneficiaries are high-beta, high-fixed-cost, rate-sensitive
names — airlines, cruise, homebuilders, small caps — with energy producers the obvious losers.**

---

## BUYABILITY — the constraint that will block both of these

**This is the part that will stop either thesis being actionable, and it must be fixed before
any of these names can be bought.** `theme_of()` returns None for an unclassified symbol and
`theme_cap_check` REFUSES that buy. An unclassified name is not "uncapped" — it is **unbuyable**.
The current map covers all 500 screener names (0% unclassified), so this is not a live bug on the
existing universe. It is a live blocker on both theses:

**Thesis 1 — 33 of the fab names are unclassified.** Including the single most on-thesis name,
**GFS (GlobalFoundries)**, which is the only pure-play Western foundry operator with a funded,
announced, large-scale new fab. Also unclassified: STM (STMicroelectronics — the European
silicon-carbide champion, Catania 200mm), UMC (Taiwan, but the mature-node comparator), WOLF
(Wolfspeed — US SiC, post-bankruptcy), and 29 smaller semi names (SLAB, POWI, AMKR, PLAB, SITM,
AZTA, AEIS, CRUS, LSCC, AOSL, DIOD, VSH, and others).

**Thesis 2 — the three strongest airline beneficiaries are unclassified.** JBLU (-0.68, the
strongest oil beta in the whole test), AAL (-0.58) and ALK (-0.63) cannot currently be bought.
Also unclassified: TRIP, XPO, FIVE, KSS, M, PVH.

**Before acting on either thesis, run the theme-map extension procedure** (see
`references/theme-map-construction.md`): fetch 2 years of SIP bars for the unclassified names,
cluster by correlation, assign by the same method as the rest of the map, and **union the old
map in** so no covered name goes from capped to unbuyable. Then pin it with the test that walks
the whole screener output and asserts every ticker is classified.

**Do not classify these by hand from the business description.** The map is a correlation map
and the BE/POWER_ENERGY failure is what happens when a name is assigned from its industry rather
than its measured co-movement.

---

## TRIGGERS — what would make each thesis actionable

These are conditions to check, not predictions. Nothing here should fire an order.

**Thesis 1 triggers:** any of — a blockade, a quarantine, an explicit threat of invasion, a
Taiwan Strait closure, or a US/EU/Japan export-control escalation on advanced-node tools. On any
of these, run the research task in the table above (which non-Taiwan line can run which node)
before proposing anything.

**Thesis 2 triggers:** any of — a signed ceasefire or armistice, reopening of the Strait of
Hormuz, restoration of Persian Gulf refining/export capacity, Brent sustainably back below
~$80, or a Fed pause/rate-cut signal. Note the war already produced one false dawn: Trump said
the war was "very complete" and Brent fell to $88.80 before rebounding. **A single headline is
not a trigger; look for the price to hold.**

## What this file is NOT

Not a buy list. Not a signal generator. Both theses were tested before being written down, one
was partly refuted (the fab trade), and one was found to be weaker than the owner's intuition in
two of its three channels (retail and freight). The screener and the theme map have both been
measured and shown to have no forward predictive power — see
`references/validating-strategy-claims.md`. The genuine edge is the owner's own thesis, and
these two are now on the record so they can be checked rather than remembered.

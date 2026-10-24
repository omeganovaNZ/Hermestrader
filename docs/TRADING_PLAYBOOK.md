# Alpaca Trading System — Complete Playbook
# Last updated: 2026-10-25 (revised)

> **Live rules live in code.** The current rules are enforced in `src/position_manager.py`
> (trim + cap + redeploy), `src/portfolio_rules.py` (theme cap, thesis review) and
> `src/alpaca_trader.py` (entry sizing). This file keeps the full reasoning, the backtests that
> justify each rule, and the refutations of ideas that were tried and rejected. Where a section
> below describes an older mechanism (the trim ladder, the adaptive gate), it is kept as
> historical evidence — the section heading says so.

## Current Portfolio

**Do not hardcode positions here — they rot.** Read the live state instead:

- Positions, cash, equity: `GET /v2/account` and `/v2/positions` (see `alpaca_config.txt` for credentials)
- Every fill, as Alpaca recorded it: `alpaca_trades_log.json` → `fills`
- Orders that never filled: `alpaca_trades_log.json` → `cancelled_or_expired`

Snapshot as of the last review (2026-10-17, paper account):

| Symbol | Shares | Avg entry | Weight of long MV | Thesis |
|---|---|---|---|---|
| MRVL | 98 | $235.29 | 24.5% | Custom AI silicon. **Over the 15% cap — the 395-share order that would have made this a deliberate full-portfolio bet was cancelled; 98 shares is what actually filled.** |
| RKLB | 258 | $53.90 | 14.5% | Space/Neutron. Binary on first flight (slipped 4x, now 2027). Screener rates it AVOID. |
| MU | 15 | $901.07 | 14.5% | Memory supercycle, sold out into CY2027. Peak-cycle risk. |
| DDOG | 45 | $269.18 | 12.3% | **No thesis — bought to "fill the portfolio".** Worst performer. |
| LLY | 7 | $1,259.81 | 9.7% | GLP-1 franchise. Originally a 1-month event trade. |
| BE | 40 | $230.23 | 9.7% | Fuel cells, Oracle 2.8GW / AEP 702MW. **Over the 5% cap.** |
| AMD | 16 | $548.41 | 9.3% | Originally a 1-month earnings trade (3 Nov print). |
| PK | 317 | $15.96 | 5.6% | Hospitality REIT. "Defensive" label contradicts the hiking-rate macro view. |

**Cap trims were CANCELLED on 2026-10-17** (MRVL 55.61 sh, RKLB 69.20 sh, MU 4.02 sh,
DDOG 5.89 sh). They had been placed to bring positions back to the 10% cap, but all four
symbols were in LOSS and the rule is now *trim winners only* — enforcing the cap on a loser
would have sold it at a loss and realised about -$846. Consequence: **cash stays at ~$5,543,
not the ~$21,110 previously projected here, and the AI-hardware sleeve stays at ~75% rather
than falling to ~37.9%.** All four positions remain over the cap until they turn green.

**Portfolio risk (measured, not assumed):** annualised vol **49.0%** vs SPY 12.7% —
3.9x the market. AI-hardware sleeve is ~75% of long market value against this
playbook's own 40% ceiling. The ceiling is now **enforced in code** (`portfolio_rules`); it
was prose only before, which is precisely how it reached 75%.

*Correction (2026-10-18):* the figure previously quoted here — "mean pairwise correlation 0.53
inside the sleeve" — is **wrong**. 0.53 is the MRVL–MU pair, not the sleeve average.
Recomputed over 1 year of daily closes, the 5x5 mean pairwise correlation is **0.33**, and
DDOG is nearly uncorrelated with the rest (0.07–0.11). The concentration risk is real; the
number originally given for it was overstated.

*Measured value of the cap:* scaling the sleeve from 70.7% to 40% of equity (freed weight
held as cash) cuts annualised volatility from **46.4% to 29.6% (−36%)** and max drawdown from
**−28.7% to −18.9% (−34%)**. The cap earns its place on concentration grounds — just not on
the correlation figure that was originally offered as its justification.

**Current state (2026-10-25).** The snapshot above is a historical record of 2026-10-17. The
live book has since moved: cap trims were PLACED (not cancelled) on the winners — Core DDOG,
Pattern Match VRTX/CVX, Container Test 1 PLTR/LLY/OKTA/DDOG/AI — and the freed cash plus
parked cash was redeployed into BE (Core), ASML (Pattern Match) and MRVL (Container Test 1).
The three paper accounts are Core (PA3JY31PP), Pattern Match (PA3JNJZ0X) and Container Test 1
(PA3HV7XBX); read `accounts.json` for the registry. The AI_SOFTWARE sleeve in Container Test 1
was over the 40% cap (53.7%) before the trims and is being worked down.

## Strategy Summary

### Ensemble Signals (5 layers)
1. Technical (30%): ADX + Bollinger Bands + regime detection
2. ML Prediction (25%): LightGBM 5-day forward return prediction
3. Sentiment (20%): News sentiment scoring
4. Momentum (15%): 12-month return
5. Volatility (10%): Low volatility preference

### Trimming Rules — Tom Nash framework

**Trimming is risk management on winners, not a reaction to weakness.** In his words:
"Selling is what you do when the business is broken. Trimming is what you do when the
winner has grown." So there are no weakness or overbought trim triggers at all.

**The Trim Ladder** — gain measured from each symbol's own ladder base price:

| gain from base | trim |
|---|---|
| +50% | sell 10% of shares held |
| +100% | sell 20% |
| +150% | sell 30%, then **re-base** to the current price and climb again |

One rung fires per scan, lowest unfired first, so a position that gaps up climbs the
ladder over successive scans rather than dumping every rung at once. Rung state persists in
`trim_ladder_state.json`; a rung is marked fired as soon as its order is *placed* so it
cannot re-fire while pending. A saturated ladder self-heals by re-basing.

Sizing is `round(qty * pct, 4)` — fractional, so the trim is exactly the stated share of the
position. (The old `int(qty * 0.20)` truncated: 20% of 7 shares became 1 = 14.3%, and any
position under 5 shares rounded to zero and failed silently.)

**Position cap: 10% of equity.** No satellite position above `max_position_pct`. (Nash's own
range is 5-10%.)

**Cap trims are WINNERS ONLY.** A cap trim is risk management on a position that has grown,
never a reaction to weakness. An over-cap position that is DOWN is left alone — even though
that leaves the cap breached — because enforcing the cap on a loser would sell it at a loss.
A flat position (`unrealized_pl == 0`) is not a winner either, so it is left alone too. An
over-cap loser remains an ADD candidate. Same principle as the trim ladder: *selling is what
you do when the business is broken; trimming is what you do when the winner has grown.*

**The consequence, which is why ENTRY SIZING matters.** Because the cap is now only enforced on
winners, an over-cap LOSER can stay over-cap indefinitely — the cap can never correct it while
it is down. So a position bought above the cap is a position the cap cannot fix. Buys must be
sized at or below the cap. On 2026-10-17 all four over-cap positions were bought over the cap
and all four were down (MRVL 23.2% of equity, MU 13.7%, RKLB 13.6%, DDOG 11.5%), so all four
cap-trim orders were cancelled rather than sold at a loss.

A cap trim is also placed with **no ladder rung**, so the ladder's fired-rung guard does not
cover it — and while a cap-trim sell order is still pending, the position still looks over-cap
on the next scan, so a second identical order would be placed. `position_cap_signals()` therefore
skips any symbol that already has an open sell order. If the open-orders query fails it trims
anyway (fail open): silently refusing to trim would disable the cap entirely. Pinned by
`test_cap_trim_guard.py` (10 tests).

**Add candidates.** A position 20% or more below its 52-week high is reported as an ADD
candidate — weakness is a buying opportunity, not a trim. Report only; never auto-bought.

**Outright exits are never automatic.** `thesis_break_exit(symbol, reason)` is an explicit
call. A broken business is a judgement no price can compute, so the scan only surfaces
candidates.

**There is no blanket cooldown.** The earlier 30-day per-symbol cooldown was dropped: the
ladder is self-limiting because each rung fires once, and a blanket cooldown would block
legitimate successive rungs.

**This job places real orders.** Despite the name "Trim Signal Alert",
`run_position_management` calls `execute_trim` → `place_sell_order`. It is not an alert.

**Fill state is recorded, not assumed.** `execute_trim` stores the real `order_id` and
`order_status` and marks a trim `FILLED` only when Alpaca says so. An earlier version logged
every trim as sold — including two LLY trims that never filled.

---

### Cross-validation of the trim ladder (2026-10-17)

Tested on 20 names over one uniform window, every strategy **armed at the same price on the
same day** — for the 10 highest-growth stocks, entered at the 2025-10-15 close; for the
Sharesies holdings, at the first close that reached each one's own cost basis. $1,000
notional per name. Entry price, not calendar date, is what makes the comparison fair.

**Panel A — the 10 highest-growth stocks** (AXTI, SNDK, MRNA, IOVA, TXG, KOD, LITE, MU, MXL,
VICR; +234% to +1021% over the window):

| strategy | median | mean | worst | best | beats HOLD |
|---|---|---|---|---|---|
| HOLD | 5.819 | 6.309 | 3.341 | 11.214 | 0% |
| LADDER | 4.049 | 4.212 | 3.307 | 5.999 | 0% |
| ADAPT-1.20 | 4.110 | 4.396 | 3.342 | 6.162 | 10% |
| TREND (gate +100%) | 4.595 | 5.120 | 3.406 | 9.324 | 20% |
| TRAIL-20% | 3.498 | 4.290 | 2.783 | 9.248 | 10% |

**Panel B — the Sharesies holdings** (10 usable; CO2/GFI/USH skipped — price never reached
their inferred basis):

| strategy | median | mean | worst | best | beats HOLD |
|---|---|---|---|---|---|
| HOLD | 1.000 | 1.101 | 0.598 | 1.998 | 0% |
| LADDER | 1.100 | 1.261 | 0.707 | 2.477 | 60% |
| ADAPT-1.20 | 1.077 | 1.255 | 0.707 | 2.499 | 50% |
| TREND (gate +100%) | 1.044 | 1.206 | 0.598 | 2.820 | 20% |
| TRAIL-20% | 1.074 | 1.197 | 0.835 | 2.328 | 60% |

**What the evidence supports**

1. **Nothing beat holding on the highest-growth stocks.** Holding turned $1,000 into a median
   $5,819. Every active strategy gave up a fifth to a third of that. Caveat: this panel is
   survivorship-biased *by construction* — those names were selected for having the highest
   gains, so holding is structurally guaranteed to win. It prices the cost of trimming in the
   best case for holding; it cannot validate or invalidate trimming.
2. **On the actual holdings the original ladder is the strongest mechanism tested** — it beat
   holding on 6 of 10, including three names that fell (DTIL -20% became 1.115, RGTI -3% became
   1.586, DXYZ -40% became 0.707). The low rung is what lets it sell into a rally; that is the
   mechanism working, not a bug.
3. **The rung is a regime parameter.** Performance on Panel A rises monotonically as the rung
   is raised; on Panel B it falls monotonically. Opposite directions is the strongest evidence
   there is that no single fixed setting is correct.
4. **The trailing stop is NOT dominated — it is roughly level with the ladder.** It beats the
   ladder on the winners panel (4.29x vs 4.21x mean) and trails it on the holdings (1.20x vs
   1.26x). An earlier version of this playbook claimed it was dominated on both panels; that
   was wrong, and it was wrong because of a cash-accounting bug (credited 80% of the position,
   removed 20%). Do not add one — but because it is not better where it matters, not because
   it is broadly bad.
5. **The "gate" is the essential ingredient.** A trend rule without the "after a long gain"
   condition liquidated positions early and lost $501 on the growth names.

**The adaptive gate (implemented 2026-10-17; pinned by `test_adaptive_gate.py`):** the ladder's first trim is skipped when the move is already
parabolic. When the price first reaches +50% of the ladder base, compute
`extension = close / 50-day SMA`; if `extension >= 1.20` skip the 10% trim and let it run,
otherwise take it as normal. Only the first rung is gated.

- It is the **first variant that improved Panel A without damaging Panel B**: +0.184 mean on
  the growth names, -0.006 on the holdings (noise).
- **The threshold is not knife-edge** — 1.10 / 1.20 / 1.30 land within 0.025 of each other.
- It beats the ladder on 10 of 10 growth stocks.
- It is a modest improvement (+4.4% Panel A, -0.5% Panel B), not a breakthrough, and it does
  not beat holding on the growth names.

---

## THE TRIM RULE (current, 2026-10-17)

Everything above this line describes the trim **ladder**, which was replaced. The user's rule,
in their words: *"I only want to trim stocks which I've held longer than 6 months, have had an
over 100% ROI — at which point, if they continue to grow in value, don't trim them. Only trim
them when they've had 2-3 days of a decrease in shareprice (which doesn't match the trend) and
then issue a 20% trim of the total stock holding of that particular stock. At no other time do I
want to trim what has been invested."*

A position is trimmed ONLY when ALL FOUR hold:

| condition | test | parameter |
|---|---|---|
| held long enough | days since the first filled buy **> 183** | `min_hold_days` |
| a real winner | ROI from the reference price **>= +100%** | `profit_trim_pct` |
| a pullback | last **2** daily closes each lower than the prior | `pullback_days` |
| still in the trend | price **above** its 200-day average | `trend_ma` |

...and then it sells **20% of the shares held** (`profit_trim_size`).

**Growth alone never trims.** A position that keeps rising is left to run — the trigger is a
pullback, never a gain. That is the opposite of the ladder, which sold into strength at +50%.

**The reference price re-bases to the trim price.** After a 20% trim the ROI reference becomes
the price at which that trim was placed, so the next trim needs another +100% *from there*. That
is what makes this one trim event per doubling rather than a cascade — without it, a position
that had already doubled would re-trigger on every 2-day dip and be chewed away.

**An unknown holding period never trims.** Alpaca's position object carries no open date, so the
holding period is derived from the earliest filled BUY in order history
(`alpaca.get_first_buy_date`). When that cannot be determined the rule refuses to trim, because
"unknown" must not read as "old enough". Limitation: it is the earliest buy *ever* for that
symbol, so a position that was fully sold and re-bought looks older than it is — that errs
toward trimming too early rather than too late.

**On the current book this means nothing trims for months.** Every position was bought
2026-10-16, so the earliest any can be trimmed is ~2027-04-17, and only if it has also doubled
and is pulling back while still above its 200-day average.

Pinned by `test_profit_trim.py` (11 tests: each of the four conditions broken individually, the
re-base behaviour, and the down-day counter).

### Entry sizing (aligned 2026-10-17)

Three different position caps existed and none of them agreed: `alpaca_trader.max_position_pct`
said **0.20 but was never read**, `calculate_position_size` hardcoded **0.15**, and the trimmer
enforced **0.10**. Any position sized between 10% and 15% was therefore over-cap from the moment
it was bought — and because the cap trim only ever sells WINNERS, an over-cap position that then
fell could not be corrected by anything. MRVL (23.2% of equity, down 3.2%), MU (13.7%), RKLB
(13.6%) and DDOG (11.5%) all arrived that way, which is why all four cap-trim orders had to be
cancelled rather than sold at a loss.

Now: **entry cap 8%, deliberately below the 10% trim cap**, and the attribute that was dead is
the one that is read. Below the cap on purpose — sizing exactly AT the cap means the first good
day makes the position over-cap and triggers a trim. Pinned by `test_position_sizing.py`
(6 tests), which includes the cross-module invariant `entry cap < trim cap`.

Note the risk-based term is now inert: risking 2% against a 10% stop implies a 20% position,
which the 8% cap always overrides. Effective risk per new position is 8% x 10% = **0.8% of the
account**.

### Redeploy — recycling trimmed cash (2026-10-25)

A cap trim sells a winner and parks the proceeds. Over a 2-year replay on the Core book's own
names, leaving that cash idle cost the cap its entire point: **+173% leaving it idle vs +246%
redeployed** (Sharpe 2.12 → 2.26). Easing the cap to 25% instead reached +288% but at Sharpe
1.86 and a deeper drawdown, so redeployment dominates easing.

`redeploy_signals()` tops up **underweight holdings** (below the 8% entry target) using parked
cash, then `execute_redeploy()` places the buy. Guards, all enforced and tested:

- **Target below the trim cap** — `redeploy_target_pct` (0.08) is deliberately below
  `max_position_pct` (0.10), so a top-up never lands a position on the trim boundary.
- **Minimum gap** — a top-up only fires when the gap is at least `max($1,000, equity x 1%)`, so
  a near-target position is not churned.
- **Per-scan throttle** — no more than `redeploy_max_pct` (10%) of equity is deployed in one
  scan, widest gap first.
- **Cash reserve** — `redeploy_reserve_pct` (1%) of equity is kept in cash; negative or
  below-reserve cash deploys nothing.
- **Theme cap still binds** — a top-up into an over-cap theme is refused, and an unclassified
  symbol is refused (fail-closed, same as the buy path).
- **No stacking** — a symbol with a pending buy is skipped; a pending sell does not block it.
- **Fails closed on account/positions, open on orders** — an unreadable account returns no
  redeploys; a failed open-orders query does not stop the scan.

Pinned by `test_redeploy.py` (29 tests). Runs inside `run_position_management`, after the cap
trims, and writes `data/redeploy_log{account}.json`.

### Portfolio-level rules, now in code (2026-10-17)

Three things that existed only as prose are now enforced or surfaced.

**1. The theme (sleeve) cap is enforced on the buy path.** `portfolio_rules.theme_cap_check_safe`
runs before every buy and refuses any order that would push a theme past `MAX_THEME_PCT` (40%).
The 40% AI-hardware ceiling was a sentence in this file that nothing read, which is exactly how
that sleeve reached ~75% of long market value with 0.53 mean pairwise correlation inside it.
Live: a $5,000 NVDA or TSM buy is **BLOCKED** (AI_HARDWARE is already 70.7% of equity); a
$5,000 LLY buy is **ALLOWED** (BIOTECH_HEALTH would be 14.3%). It **fails closed** — if the
check cannot be evaluated the buy is refused, because a limit that opens up whenever it fails
is not a limit. Pinned by `test_portfolio_rules.py` (20 tests).

*Limitation, stated plainly:* Alpaca's free tier provides no sector field, so `THEMES` is
hand-maintained and **an unclassified symbol escapes the cap entirely**. A test asserts every
currently-held symbol is classified, and unclassified exposure is printed on every scan so the
gap stays visible rather than silent.

**2. The thesis review surfaces weakness without acting on it.** `thesis_review()` flags
positions held past 180 days and down 25%+ (`LONG_AND_DOWN`), and positions held a year or more
and still below cost (`STALE`). It **never sells** — the owner's rule is that invested capital
is not trimmed on weakness, so this closes the *visibility* gap, not the position. Before it,
the system had no downside management at all: the profit trim needs +100%, the cap trim only
sells winners, and `thesis_break_exit` is called by nothing. A position could fall 60% with
zero response and zero comment.

**3. Every cron job now delivers to a channel.** All seven were `deliver=local`, so output was
written to disk and never surfaced — including two jobs that place real orders unattended. The
only way to learn that anything had happened was to ask.

### Restoring the ladder's rungs — TESTED AND REFUTED (2026-10-17)

The ladder was replaced by the profit-trim rule above, and the open question was whether its
levels should be restored in combination with the new pullback trigger. The harness was rebuilt
and **validated against the documented Panel A numbers** (HOLD median 5.819 vs 5.819 documented;
LADDER 4.046 vs 4.049), so that panel is trustworthy.

Panel A — the 10 highest-growth names, per $1,000 notional, 0.1% commission per trade:

| strategy | median | mean | worst | beats HOLD |
|---|---|---|---|---|
| HOLD | 5.819 | 6.309 | 3.341 | 0% |
| LADDER (the old ladder) | 4.046 | 4.209 | 3.305 | 0% |
| USER (the rule, no min hold) | 5.211 | 5.684 | 3.556 | 20% |
| **USER + 6-month hold** | **5.307** | **6.029** | 3.552 | **40%** |
| SYNTH (rungs + pullback trigger) | 4.347 | 4.760 | 3.110 | 10% |
| SYNTH + 6-month hold | 4.679 | 5.708 | 3.655 | 40% |
| SYNTH + parabolic gate + hold | 4.723 | 5.757 | 3.655 | 40% |

1. **The pullback trigger is a large improvement over firing into strength.** LADDER mean 4.209
   -> USER+hold 6.029, **+43%**. The ladder's +50% rung sold into vertical moves; waiting for a
   2-day dip does not. This is the single clearest result of the exercise.
2. **The 6-month hold helps consistently on growth names** (5.684 -> 6.029, and beats-HOLD
   20% -> 40%). The user's instinct is supported by the data.
3. **Restoring the rungs does NOT help, even gated.** SYNTH+hold 5.708 and SYNTH+gate+hold
   5.757 both trail USER+hold 6.029. The +50% rung is still too eager. The only thing the rungs
   buy is a marginally better worst case (3.655 vs 3.552, about +2.9% on the single worst name)
   against a lower mean on the best names. Not worth the complexity — **the rungs were not
   restored.**
4. **The "still above the 200-day average" condition is INERT.** Variants with and without it
   produced identical results on all 23 names, because a position up +50% or +100% is
   essentially always above a 200-day average. It costs nothing and does nothing.
5. **Panel B did not reproduce** (HOLD median 0.754 vs the documented 1.000), so its numbers
   are indicative only and no decision rests on them. Directionally it repeats the earlier
   finding that early harvesting helps flat/down names and that the 6-month hold hurts them.

Two harness bugs were found and fixed while doing this, both of which produced confident wrong
output: `a is True` is always False for a numpy comparison (which silently disabled every
pullback variant, leaving them identical to HOLD), and slicing Panel A's series to start at the
entry date destroyed the 200-day warm-up, blocking the pullback variants for their first 199
bars while LADDER could act from bar 1.

**A recommendation that was tested and REFUTED.** Raising the first rung outright to +100%
(LADDER-100) was proposed and then tested. It gained more on Panel A (+0.596) but cost -0.074
on Panel B, and cut "beats HOLD" on the holdings from 60% to 30%. On the evidence the change
was **rejected** — it would have made the actual book worse. Recorded here so the reasoning is
on record rather than silently dropped.

**Bugs found during this work** (all fixed; each would have produced confident, wrong output):

- The first two cross-validation runs discarded every sale's cash proceeds, reporting only the
  remaining share count — making successful strategies look like failures.
- `trail()` credited cash for 80% of the position while removing only 20%, a 4x over-credit that
  made a sell-only strategy appear to amplify VICR 13-fold. (It actually peaked at $379.78 and
  fell back to $191.50, so a trailing stop did well there — 3.59x, not 13.29x.)
- `gain_loss == -100.0` in `sharesies_portfolio_analysis.json` zeroes the cost-basis
  denominator; that holding is now skipped rather than crashing the run.

**Standing caveats.** The Sharesies cost basis is *inferred* (read from `gain_loss` as a
percentage — AIR and BAP are the discriminator) and unconfirmed against the Sharesies site. The
yfinance closes do not reproduce the documented headline prices for every name (AXTI $51.47 vs
a documented $84.83), so absolute gains won't match the source document — the *comparison*
between strategies is unaffected since all use the same data. One 12-month window, and Panel B
is effectively decided by five names.

---

### How the strategy evolves — a standing principle

The trim ladder is not a fixed artefact. It is a hypothesis that is re-tested against data and
revised when the evidence is good enough. Four rules govern any change:

1. **A change must be tested, not asserted.** Every modification recorded above was backtested
   on the same 20 names under the same arms before it was adopted. The "+100% rung" change was
   tested and *rejected* on its numbers.
2. **A change must improve one regime without damaging another.** The rung is a regime
   parameter — explosive winners want it high, flat/choppy names want it low. A variant that
   helps only one panel is a trade, not an improvement, and is adopted only when the cost on
   the other panel is measurably zero. That is why the adaptive gate was accepted (Panel A
   +0.184, Panel B -0.006) and the outright rung raise was not (+0.596 / -0.074).
3. **Refutations are kept, not discarded.** When a hypothesis fails, the failure is recorded
   with its numbers so the same mistake is not re-made.
4. **Code follows evidence, not the reverse.** A change is implemented in
   `position_manager.py` only after it survives rules 1-3, and the implementation is then
   pinned by tests (`test_adaptive_gate.py`) so a later refactor cannot silently undo it.

Going forward the scan keeps collecting data, and any proposed change runs through this same
gate before it touches live orders. This is the mechanism by which the strategy is expected to
get better and more robust over time rather than being set once and left to rot.

### Pattern-matching against historical setups — a standing footnote

When a stock in the portfolio (or on the watchlist) shows a technical setup that resembles a
known historical setup — e.g. MRVL's Oct 2024 bullish breakout (RSI ~72, ADX ~31, +15% above
200DMA) — use that resemblance as a **flag to investigate, not a signal to buy**. The process:

1. **Identify the reference setup.** What did the stock's technical profile look like at a
   comparable point in a prior cycle? (Use `two_year_comparison.py` or equivalent.)
2. **Find current matches.** Screen the universe for stocks showing the same profile today.
3. **Demand fundamental evidence before any entry.** A matching chart pattern is not enough.
   For each candidate, verify: What is the industry? What is the balance sheet (debt, liquid
   cash, runway)? What structural tailwind or catalyst supports the setup? Is the valuation
   extreme relative to peers? Only if the fundamentals corroborate the pattern does the stock
   become an entry candidate.
4. **Size accordingly.** A pattern-match entry is a satellite position (3-5%), not a core
   hold. It is a hypothesis informed by history, not a certainty.

This is a **back-of-mind discipline**, not a screener replacement. It surfaces candidates that
the hand-picked universe would miss, but every candidate must still pass the existing gates:
theme cap, entry cap, multiple confirming signals, and the thesis review. The pattern match is
the spark; the fundamentals are the fuel.

**Fractional positions are handled.** `get_positions()` returns `qty` as a float; it used to
cast to `int`, which would truncate a fractional position (5.6 shares -> 5) and corrupt
every downstream calculation.


### Risk Management
- Entry cap: max 8% of equity per position (deliberately below the trim cap)
- Trim cap: max 10% of equity per position (winners only)
- Profit trim: +100% ROI, held >6 months, 2 down days, still above the 200-day → sell 20%
- Trimmed cash is redeployed into underweight holdings (see Redeploy above)
- Theme (sleeve) cap: 40% of equity, enforced fail-closed at the buy path
- No stop loss; weakness is an ADD candidate, not a trim

## Screener Criteria

### Universe (36 stocks)
- Semiconductors: MRVL, AVGO, TSM, ASML, LRCX, AMAT, KLAC, SNPS, CDNS, MXL
- AI/Cloud: CRWD, PANW, OKTA, DDOG, SNOW, MDB, NET, PLTR, AI, SMCI
- Biotech/Healthcare: LLY, MRNA, IOVA, KOD, TXG, CRSP, NTLA, BEAM, EDIT, VRTX
- Power/Energy: GEV, VICR, BE, ENPH, FSLR
- Space: RKLB, ASTS, LUNR
- Memory: MU, SNDK, LITE, COHR

### Entry Criteria (Score 0-100)
- Bullish trend (price > 50 & 200 DMA): 25 points
- ADX > 30: 20 points
- RSI 40-60: 15 points
- 10-40% above 200 DMA: 15 points
- Strong momentum (3M return > 20%): 15 points
- Low volatility (< 30%): 10 points

### Ratings
- STRONG BUY: Score >= 70
- BUY: Score 55-69
- WATCH: Score 40-54
- AVOID: Score < 40

## Cron Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| Daily Trading News Brief | 8am weekdays | News scan for watched stocks |
| Daily Stock Screener | 8am weekdays | Identify new entry candidates |
| Daily Alpaca Paper Trading Scan | 8am weekdays | Ensemble signals + position management |
| Trim Signal Alert | 8am weekdays | Alert when trim signals trigger |
| Weekly Structural Trends Brief | 8am Mondays | Multi-year trend analysis |
| Weekly Trading Performance Report | 8am Mondays | Performance summary |
| 1-Month Trade Exit (AMD/LLY) | 16 Nov 9am (one-shot, self-checking) | Job `55c95f224300d`. Refuses to act if fired early. Replaces the old DEAD job that misfired on 17 Oct. |

**Cron warning (2026-10-17):** all seven trading jobs fired off-schedule in one burst
(Saturday, no scheduled instant). The old 16 Nov one-shot fired and placed sell orders;
it has been replaced by job `55c95f224300d` (self-checking, correctly scheduled). Both
order-placing jobs (Trim Signal Alert, Daily Alpaca Paper Trading Scan) have been hardened
with STEP 0 precondition checks: weekend → refuse, market closed → refuse, no positions →
refuse. The root cause of the misfire itself is unresolved, but the jobs now refuse to act
when the premise does not hold.

## Key Files

All files live in `C:\Users\Omega\Repo\Hermes Trader\` (moved from `C:\Users\Omega\`,
which still holds stale duplicate copies — ignore anything there).

- `alpaca_config.txt` — API credentials (gitignored; NEVER SHARE, never hardcode)
- `alpaca_trades_log.json` — fills + cancelled orders, derived from Alpaca order history
- `trim_log.json` — all trims
- `screener_results.json` — screener output
- `ensemble_signals.json` — ensemble signals (check `layers_used` before trusting)
- `weekly_performance_report.md` — weekly report
- `one_month_trades.json` — 1-month trade tracking

## User Preferences

- Risk tolerance: higher risk OK, but only with multiple confirming signals
- Investment horizon: long-term (1-2 years) with active profit-taking
- Position sizing: 8% entry cap per position, 10% trim cap (winners only)
- Trim strategy: +100% ROI, held >6 months, 2 down days against the trend → sell 20%
- No stop loss; an outright exit requires a broken thesis (`thesis_break_exit`), not a drawdown
- Reentry: only when research stack confirms near-term rise
- Research approach: must have multiple independent signals confirming near-term rise

## Strategy Performance History

### Backtesting Results (5-Year)
- Market-aware vs Buy & Hold:
  - RKLB: +1156% vs +345% (MA wins big)
  - NVDA: +209% vs +882% (B&H wins)
  - MU: +843% vs +1318% (B&H wins, but MA has better Sharpe)
  - AMD: +48% vs +383% (B&H wins)
  - GOOGL: -20% vs +147% (B&H wins)
  - XOM: +27% vs +233% (B&H wins)

### Key Insights
- MA beats B&H on high-volatility stocks and cyclical recoveries
- MA underperforms on steady uptrends
- Edge is drawdown control, not absolute returns
- ADX threshold 30-33 works better than 25 for US stocks

## Watchlist (40+ stocks)

### High-conviction (MA beats B&H)
- RKLB, MU, BE, PK, HD

### Screener STRONG BUY (Score >= 75)
- MRVL (95), DDOG (90), PLTR (90), CRWD (85), MXL (85)
- SNOW (80), LLY (80), TXG (80), OKTA (75), LITE (75)

### Screener BUY (Score 60-74)
- SNPS (70), ANET (70), NET (70), MRNA (70)
- TSM (65), SMCI (65), VRTX (65)
- ASML (60), PANW (60), IOVA (60), KOD (60), SNDK (60), CDNS (55)

### Monitor
- NVDA, AMD, GOOGL, XOM, CVX, NEE, CAT, GEV, RTX

## How to Continue This Strategy in Future Sessions

1. **Load the skill**: `skill_view(name='alpaca-trading-strategy')`
2. **Check cron jobs**: `cronjob_manage(action='list')`
3. **Review portfolio**: read `alpaca_trades_log.json`, then confirm against Alpaca's
   `/v2/positions` — never trust the log alone
4. **Run daily scan**: `python ensemble_trader.py`
5. **Run screener**: `python stock_screener.py`
6. **Run position management**: `python position_manager.py`
7. **Review weekly report**: read `weekly_performance_report.md`

## Emergency Procedures

### If MRVL drops significantly
- Check ensemble signals daily
- If ensemble score < -0.1, consider trimming 20%
- If RSI < 30 and trend turns bearish, consider full exit
- If customer concentration risk materializes (Amazon/Microsoft insourcing), exit

### If market crashes
- Reduce all positions by 50% if portfolio drawdown exceeds 15%
- Move to cash and wait for stabilization
- Re-enter when ensemble signals confirm recovery

### If trim signals trigger
- Sell 20% of the position
- Log the trim in trim_log.json
- Reinvest proceeds into highest-conviction screener candidate

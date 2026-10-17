# Alpaca Trading System — Complete Playbook
# Last updated: 2026-10-17 (revised)

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

**Pending cap trims (orders placed 2026-10-17, not yet filled):** MRVL 55.61 sh,
RKLB 69.20 sh, MU 4.02 sh, DDOG 5.89 sh — all to bring positions back to the 10% cap.
Once filled, cash will rise by ~$21,110 and AI-hardware sleeve will drop to ~37.9% of long MV.

**Portfolio risk (measured, not assumed):** annualised vol **49.0%** vs SPY 12.7% —
3.9x the market. AI-hardware sleeve is ~75% of long market value against this
playbook's own 40% ceiling, with mean pairwise correlation 0.53 inside it.

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

**Position cap: 10% of equity.** No satellite position above `max_position_pct`. An over-cap
position is trimmed back to the cap. (Nash's own range is 5-10%.)

A cap trim is placed with **no ladder rung**, so the ladder's fired-rung guard does not cover
it — and while a cap-trim sell order is still pending, the position still looks over-cap on
the next scan, so a second identical order would be placed. `position_cap_signals()` therefore
skips any symbol that already has an open sell order. If the open-orders query fails it trims
anyway (fail open): silently refusing to trim would disable the cap entirely. Pinned by
`test_cap_trim_guard.py` (7 tests).

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

**Fractional positions are handled.** `get_positions()` returns `qty` as a float; it used to
cast to `int`, which would truncate a fractional position (5.6 shares -> 5) and corrupt
every downstream calculation.


### Risk Management
- Max 20% per position
- 3% risk per trade
- Trim at milestones to free up capital
- Reinvest trimmed capital into highest-conviction signals

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

- Risk tolerance: Higher risk OK with multiple confirming signals
- Investment horizon: Long-term (1-2 years) with active profit-taking
- Position sizing: Up to 20% per position, 3% risk per trade
- Trim strategy: Sell 20% at milestones (100% return), RSI>70, overextension
- Reentry: Only when research stack confirms near-term rise
- Research approach: Must have multiple independent signals confirming near-term rise

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

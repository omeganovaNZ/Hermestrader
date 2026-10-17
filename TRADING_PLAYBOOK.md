# Alpaca Trading System — Complete Playbook
# Last updated: 2026-10-17

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

Queued at the last review, filling Monday 19 Oct: XOM 27 sh, GEV 5 sh, GLD 10 sh
(~5/5/4%, funded partly on margin).

**Portfolio risk (measured, not assumed):** annualised vol **49.0%** vs SPY 12.7% —
3.9x the market. AI-hardware sleeve is ~58% of long market value against this
playbook's own 40% ceiling, with mean pairwise correlation 0.53 inside it.

## Strategy Summary

### Ensemble Signals (5 layers)
1. Technical (30%): ADX + Bollinger Bands + regime detection
2. ML Prediction (25%): LightGBM 5-day forward return prediction
3. Sentiment (20%): News sentiment scoring
4. Momentum (15%): 12-month return
5. Volatility (10%): Low volatility preference

### Trimming Rules (sell 20% of the SHARES HELD when triggered)

Any ONE of these fires a trim:
- Return reaches 100% (milestone)
- RSI(14) > 70 (overbought)
- >50% above 200 DMA (overextension) — **cannot fire; see below**
- Ensemble score < -0.1 (weakness)

Sizing: `round(qty * 0.20, 4)` — fractional, so it is a true 20% of shares held.
(The old `int(qty * 0.20)` truncated: 20% of 7 shares became 1 share = 14.3%, and any
position under 5 shares rounded to zero and silently failed.)

**Cooldown: 30 days per symbol.** After a trim is placed, that symbol cannot be trimmed
again for 30 days even if the conditions still hold. Conditions are still evaluated and
reported during the window, so the position is revisited the moment it elapses. This
replaced unbounded re-trimming, which would have compounded daily — five straight days of
RSI > 70 would have removed 67% of a position (1 − 0.8^5).

**Known dead rule:** the overextension check can never fire. `position_manager.py` fetches
only `"6mo"` (~126 bars) but computes `rolling(200).mean()`, which yields NaN, so `dist_200`
falls through to 0 and `0 > 0.50` is always False. Fixing it means fetching `"1y"` or more —
but that ENABLES a rule that has never traded, so treat it as a strategy decision, not a
bug fix.

**This job places real orders.** Despite the name "Trim Signal Alert",
`run_position_management` calls `execute_trim` → `place_sell_order`. It is not an alert.

**Fill state is recorded, not assumed.** `execute_trim` now stores the real `order_id` and
`order_status` and marks a trim `FILLED` only when Alpaca says so. The previous version
logged every trim as sold — including two LLY trims that never filled.

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
| 1-Month Trade Sell Reminder | **DEAD — fired 30 days early on 17 Oct** | Was: sell AMD/LLY on 16 Nov. Needs re-creating with a self-check. |

**Cron warning:** on 2026-10-17 all seven trading jobs fired off-schedule in one burst
(Saturday, no scheduled instant) — including the 16 Nov one-shot, which then placed sell
orders. Root cause unresolved. Any job that can place an order MUST verify its own
preconditions (date, market open, position present) before acting, and must refuse rather
than comply when the premise does not hold.

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

# Alpaca Trading System — Complete Playbook
# Last updated: 2026-10-17

## Current Portfolio

### Active Positions
- **MRVL (Marvell Technology)**: 395 shares @ $252.59 = $99,773.05
  - Strategy: Full investment — highest conviction pick
  - Rationale: AI custom ASIC duopoly, 42 Buy/0 Sell analysts, +40% upside target
  - Expected return: +30-40% over 1-2 years
  - Key catalyst: Potential Google TPU win
  - Key risk: Customer concentration (Amazon + Microsoft = 50%+)

### Pending Orders (fill when market opens)
- RKLB: 258 shares @ $58.06 = $14,979.48
- MU: 15 shares @ $969.47 = $14,542.05
- BE: 40 shares @ $248.90 = $9,956.00
- PK: 317 shares @ $15.76 = $4,995.92

### Cash: $226.95 (fractional share remainder)

## Strategy Summary

### Ensemble Signals (5 layers)
1. Technical (30%): ADX + Bollinger Bands + regime detection
2. ML Prediction (25%): LightGBM 5-day forward return prediction
3. Sentiment (20%): News sentiment scoring
4. Momentum (15%): 12-month return
5. Volatility (10%): Low volatility preference

### Trimming Rules (sell 20% when triggered)
- Return reaches 100% (milestone)
- RSI > 70 (overbought)
- >50% above 200 DMA (overextension)
- Ensemble score < -0.1 (weakness)

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
| 1-Month Trade Sell Reminder | Nov 16 (one-time) | Sell AMD/LLY positions |

## Key Files

- `C:\Users\Omega\alpaca_config.txt` — API credentials (NEVER SHARE)
- `C:\Users\Omega\alpaca_trades_log.json` — All trades
- `C:\Users\Omega\trim_log.json` — All trims
- `C:\Users\Omega\screener_results.json` — Screener output
- `C:\Users\Omega\ensemble_signals.json` — Ensemble signals
- `C:\Users\Omega\weekly_performance_report.md` — Weekly report
- `C:\Users\Omega\one_month_trades.json` — 1-month trade tracking

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
3. **Review portfolio**: Read `C:\Users\Omega\alpaca_trades_log.json`
4. **Run daily scan**: `python C:\Users\Omega\ensemble_trader.py`
5. **Run screener**: `python C:\Users\Omega\stock_screener.py`
6. **Run position management**: `python C:\Users\Omega\position_manager.py`
7. **Review weekly report**: Read `C:\Users\Omega\weekly_performance_report.md`

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

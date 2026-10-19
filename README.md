# Hermestrader — Alpaca Paper Trading Bot

An automated paper-trading system for Alpaca Markets with a 5-layer ensemble signal
engine, 2-container strategy framework, position manager, stock screener, and
pattern-match watchlist generator.

**This is NOT investment advice. Past performance does not guarantee future results.**

## What this is

This is a personal trading system that:

- Screens the S&P 500 + Nasdaq-100 (~500 stocks) using technical entry scoring
- Generates entry/exit signals with regime-adaptive logic (ADX + Bollinger + trend-strength override)
- Manages positions with profit-taking and cap-trimming rules (Tom Nash framework)
- Tracks portfolio themes/sleeves with enforced caps
- Runs 10 cron jobs (daily scans, weekly reports, price alerts, pattern-match watchlist)
- Places real orders in Alpaca paper trading (3 paper accounts, each $100k)

## Architecture

### Signal pipeline

1. **Technical layer** (30%) — Round-4 regime-aware ADX + Bollinger strategy with graduated trend override
2. **ML layer** (25%) — LightGBM 5-day forward return prediction (per-symbol cached)
3. **Sentiment layer** (20%) — Binary veto only (blocks trades when strongly negative, < 0.3)
4. **Momentum layer** (15%) — 12-month return
5. **Volatility layer** (10%) — Low volatility preference (symmetric scoring)

Signals require 3+ live layers (`MIN_LIVE_LAYERS`). Fewer forces HOLD.

### Stock screener

`src/stock_screener.py` dynamically loads S&P 500 + Nasdaq-100 constituents from Wikipedia
(`src/index_constituents.py`, cached locally with 7-day refresh). Each stock gets a
technical entry score (0-100) based on trend, ADX, RSI, distance from 200-DMA, and momentum.
Runs daily at 08:00 NZT. Parallelized with 5 workers.

### 2-Container framework

| Container | Strategy | Classification | Rationale |
|-----------|----------|---------------|-----------|
| **C1 — Core holdings** | Buy & Hold + trim rules | RSIavg > 52 AND positive months > 60% | Steady uptrends where active trading gives back return |
| **C2 — Active trading** | Round-4 regime-adaptive | RSIavg < 52 AND positive months < 60% | Choppy/mean-reverting names where Round-4 has a verified edge |

Stocks that don't match either container default to C1 (B&H — the safer option).

**Verified backtest results (Oct 2026):**

| Stock | Round-4 | Buy & Hold | Winner |
|-------|---------|------------|--------|
| BE | +1432% | +867% | Round-4 (+565pp) |
| TSLA | +78% | +15% | Round-4 (+63pp) |
| PLTR | +1300% | +1543% | B&H (-243pp) |
| NVDA | +274% | +868% | B&H (-594pp) |

### Regime-adaptive rules (Round-4)

- **Exit persistence**: 5 days in trends (ADX > 33), 4 days in ranging (ADX < 20), linear between
- **Entry persistence**: 2 days in trends, 3 days in ranging
- **Trend-strength override**: No sells when 12m momentum > +50% AND price > 200-day MA
- **Graduated trend override**: ADX > 40 allows all sells; ADX 33-40 requires confirmation
- **Volatility-scaled momentum bypass**: 20-day momentum > 12% (high-vol) or 15% (low-vol)
- **Frequency cap**: 2-4 trades/week depending on regime

### What doesn't work (tested and refuted)

- **External regime classification** — no improvement over Round-4's own ADX detection
- **Trend-riding overlay** — made choppy stocks worse without helping uptrends
- **Pre-filters on entries** — RSI<50 vetoes 87% of entries; ADX>25 near-neutral
- **4-container system** — Containers 3-4 have no verified strategy to route to
- **Trim ladder (+50/+100/+150)** — replaced by +100%-on-pullback rule

## Safety first

- **Dry-run default**: `position_manager.py` places real orders. Always test with `--dry-run` first.
- **No credential commits**: `alpaca_config.txt` is gitignored. Verified clean.
- **Public repo warning**: This repo is public. No secrets should ever be committed.
- **Theme cap enforced**: AI-hardware sleeve capped at 40% of equity (fail-closed).
- **Position cap**: Max 10% of equity per position (entry cap 8%).
- **Winners-only trims**: Never sells a position at a loss.

## Quick start

```bash
pip install -r requirements.txt
cp alpaca_config.example.txt alpaca_config.txt  # then edit
python run_tests.py
python src/position_manager.py --dry-run
python src/stock_screener.py
```

## Project structure

```
Hermestrader/
├── README.md
├── requirements.txt
├── run_tests.py
├── alpaca_config.example.txt
├── src/
│   ├── alpaca_trader.py
│   ├── ensemble_trader.py
│   ├── market_aware_strategy.py
│   ├── position_manager.py
│   ├── portfolio_rules.py
│   ├── stock_screener.py      # Parallelized technical scoring
│   ├── index_constituents.py  # S&P 500 + Nasdaq-100 loader
│   ├── pattern_match_screen.py
│   └── trading_strategy_engine.py
├── tests/
│   ├── test_cap_trim_guard.py
│   ├── test_ensemble_fixes.py
│   ├── test_ladder_state_persistence.py
│   ├── test_portfolio_rules.py
│   ├── test_position_sizing.py
│   ├── test_profit_trim.py
│   └── test_trim_rules.py
├── docs/
│   ├── TRADING_PLAYBOOK.md
│   ├── HANDOFF_2026-10-17.md
│   ├── HANDOFF_2026-10-18.md
│   ├── NZ_AUS_Market_Research.md
│   └── top10_growth_stocks_oct2025_oct2026.md
├── data/                      # Generated JSON (gitignored)
└── assets/                    # Charts (gitignored)
```

## Running tests

```bash
python run_tests.py
```

## Cron jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Trading News Brief | Weekdays 08:00 | News scan |
| Daily Stock Screener | Every day 08:00 | S&P 500 + Nasdaq-100 scoring |
| Daily Alpaca Paper Trading Scan | Weekdays 08:00 | Portfolio scan (places orders) |
| Trim Signal Alert | Weekdays 08:00 | Trim check (places orders) |
| Weekly Structural Trends Brief | Mondays 08:00 | Trend analysis |
| Weekly Trading Performance Report | Mondays 08:00 | Performance summary |
| Weekly Pattern-Match Watchlist | Mondays 08:00 | Pattern-match screener |
| Price Watch — ASML | Weekdays 08:00 | Alerts when ASML < $1,600 |
| Price Watch — STX | Weekdays 08:00 | Alerts when STX < $600 |
| 1-Month Trade Exit (AMD/LLY) | 16 Nov 09:00 | One-time exit check |

## Configuration

All configuration is in `alpaca_config.txt` (gitignored). Multiple accounts supported:
`alpaca_config.txt`, `alpaca_config_test1.txt`, `alpaca_config_test3.txt`.

## Pattern-match watchlist

`src/pattern_match_screen.py` compares holdings' technical profiles from 2 years ago
against today's market. Pattern match is the spark, fundamentals are the fuel.

## License

Personal use only. Not for distribution.

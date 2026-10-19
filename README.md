# Hermestrader — Alpaca Paper Trading Bot

An automated paper-trading system for Alpaca Markets with a 5-layer ensemble signal
engine, 2-container strategy framework, position manager, and pattern-match watchlist generator.

**This is NOT investment advice. Past performance does not guarantee future results.**

## What this is

This is a personal trading system that:

- Screens a watchlist of ~40 stocks using a 5-layer ensemble (technical, ML, sentiment, momentum, volatility)
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

### 2-Container framework

The system classifies each stock into one of two containers based on its technical profile:

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

Round-4 dominates on choppy/mean-reverting names (BE, TSLA). B&H dominates on steady uptrends
(NVDA, LLY, VRTX). The container framework prevents catastrophic mismatches — it won't use
Round-4 on a strong trend, and won't actively trade a steady uptrend.

**Key finding from 50-stock analysis:** Sector is the strongest differentiator. Consumer
Discretionary and Materials work best for active trading. Healthcare and Real Estate are toxic.
Low-volatility stocks (< 30%) outperform on a relative basis. Moderate trade counts (5-15)
produce the best absolute returns.

### Regime-adaptive rules (Round-4)

- **Exit persistence**: 5 days in trends (ADX > 33), 4 days in ranging (ADX < 20), linear between
- **Entry persistence**: 2 days in trends, 3 days in ranging
- **Trend-strength override**: No sells when 12m momentum > +50% AND price > 200-day MA
- **Graduated trend override**: ADX > 40 allows all sells; ADX 33-40 requires confirmation (RSI < 40 or price < 20d MA)
- **Volatility-scaled momentum bypass**: 20-day momentum > 12% (high-vol) or 15% (low-vol) with rising slope bypasses entry persistence
- **Frequency cap**: 2-4 trades/week depending on regime

### Backtest results (Round-4, verified Oct 2026)

| Stock  | Round-4 | Buy & Hold | Sharpe |
|--------|---------|------------|--------|
| BE     | +1432%  | +867%      | 1.21   |
| TSLA   | +78%    | +15%       | 0.54   |
| RKLB   | +665%   | +833%      | 1.02   |
| PLTR   | +1300%  | +1543%     | 1.42   |

Round-4 dominates in choppy/mean-reverting markets (BE, TSLA) and roughly matches Buy & Hold
on strong trends (RKLB, PLTR) with better risk-adjusted returns.

### What doesn't work (tested and refuted)

- **External regime classification for strategy selection** — rolling/online test showed no improvement (+231% vs +231% B&H, worse than pure Round-4 +291%). Round-4's own ADX-based detection is sufficient.
- **Trend-riding overlay for uptrends** — tested and reverted. Made choppy stocks worse (BE: +1432% → +723%) without helping uptrends.
- **Pre-filters on entries** — RSI<50 is actively destructive (vetoes 87% of entries). ADX>25, momentum>0, and vol>40% are all near-neutral to negative.
- **4-container system** — Containers 3 (momentum) and 4 (bear defense) have no verified strategy to route to. Gold (GLD) is the best bear-market hedge (+20.6% during bear periods) but no implementation exists yet.

## Safety first

- **Dry-run default**: `position_manager.py` places real orders. Always test with `--dry-run` first.
- **No credential commits**: `alpaca_config.txt` is gitignored. Verified clean — no leaks.
- **Public repo warning**: This repo is public. No secrets should ever be committed.
- **Theme cap enforced**: AI-hardware sleeve capped at 40% of equity (fail-closed).
- **Position cap**: Max 10% of equity per position (entry cap 8%).

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials (copy template, fill in your keys)
cp alpaca_config.example.txt alpaca_config.txt  # then edit

# 3. Run tests (no network, no orders)
python run_tests.py

# 4. Run a dry-run scan (no orders placed)
python src/position_manager.py --dry-run

# 5. Run the stock screener
python src/stock_screener.py
```

## Project structure

```
Hermestrader/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── run_tests.py           # Test runner (discovers tests/test_*.py)
├── alpaca_config.example.txt  # Credential template (copy to alpaca_config.txt)
│
├── src/                   # Core modules
│   ├── alpaca_trader.py       # Alpaca API client, order placement
│   ├── ensemble_trader.py     # 5-layer ensemble signal generator (Round-4 integrated)
│   ├── market_aware_strategy.py  # Round-4 regime-adaptive ADX + Bollinger strategy
│   ├── position_manager.py    # Profit/cap trim rules, thesis review
│   ├── portfolio_rules.py     # Theme cap, thesis review (pure functions)
│   ├── stock_screener.py      # Technical entry scoring (0-100)
│   ├── pattern_match_screen.py # Two-year pattern-match watchlist generator
│   └── trading_strategy_engine.py  # Backtesting engine, data fetching
│
├── tests/                 # Test suites (plain scripts, run directly)
│   ├── test_cap_trim_guard.py
│   ├── test_ensemble_fixes.py
│   ├── test_ladder_state_persistence.py
│   ├── test_portfolio_rules.py
│   ├── test_position_sizing.py
│   ├── test_profit_trim.py
│   └── test_trim_rules.py
│
├── docs/                  # Human-readable documentation
│   ├── TRADING_PLAYBOOK.md    # Strategy, rules, architecture
│   ├── HANDOFF_2026-10-17.md
│   ├── HANDOFF_2026-10-18.md
│   ├── NZ_AUS_Market_Research.md
│   └── top10_growth_stocks_oct2025_oct2026.md
│
├── data/                  # Generated JSON artefacts (gitignored)
│   ├── alpaca_trades_log.json
│   ├── trim_log.json
│   ├── screener_results.json
│   ├── ensemble_signals.json
│   ├── pattern_match_results.json
│   └── ...
│
└── assets/                # Generated chart images (gitignored)
    └── *.png
```

## Running tests

```bash
python run_tests.py
```

Discovers all `tests/test_*.py` files, runs each in a subprocess, and prints a summary.
Current: 7 suites, 67 tests, 0 failures.

## Cron jobs

The system uses local cron jobs (NZT) for automated scans. These are machine-local and
not part of the repo. Current schedule:

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Trading News Brief | Weekdays 08:00 | News scan for watched stocks |
| Daily Stock Screener | Weekdays 08:00 | Technical entry scoring |
| Daily Alpaca Paper Trading Scan | Weekdays 08:00 | Full portfolio scan (places orders) |
| Trim Signal Alert | Weekdays 08:00 | Check for trim signals (places orders) |
| Weekly Structural Trends Brief | Mondays 08:00 | Multi-year trend analysis |
| Weekly Trading Performance Report | Mondays 08:00 | Portfolio performance summary |
| Weekly Pattern-Match Watchlist | Mondays 08:00 | Two-year pattern-match screener |
| Price Watch — ASML Entry | Weekdays 08:00 | Alerts when ASML < $1,600 |
| Price Watch — STX Entry | Weekdays 08:00 | Alerts when STX < $600 |
| 1-Month Trade Exit (AMD/LLY) | 16 Nov 09:00 | One-time exit check |

All jobs deliver to connected channels via the Hermes gateway.

## Live trading

**Only run live via explicit user invocation.** Never cron `position_manager.py`
without `--dry-run` unless you intend to place real orders.

```bash
# Dry run (no orders)
python src/position_manager.py --dry-run

# Live scan (PLACES REAL ORDERS)
python src/position_manager.py
```

## Configuration

All configuration is in `alpaca_config.txt` (gitignored):

```
API_KEY=your_key_here
API_SECRET=your_secret_here
```

Copy `alpaca_config.example.txt` and fill in your Alpaca paper-trading credentials.
Multiple accounts are supported: `alpaca_config.txt`, `alpaca_config_test1.txt`,
`alpaca_config_test3.txt` (all gitignored).

## Current accounts

| Account | ID | Status | Notes |
|---------|-----|--------|-------|
| Original | PA3JY31PP | 8 positions | Core portfolio, -0.97% P&L |
| Test 1 | PA3JNJZ0X | 10 orders pending | Pattern-match picks (Oct 19) |
| Test 3 | — | 10 orders pending | Screener top-10, score-weighted (Oct 19) |

## Pattern-match watchlist

`src/pattern_match_screen.py` compares current holdings' technical profiles from exactly
2 years ago against today's market to find stocks with similar setups. Output saved to
`data/pattern_match_results.json`. Runs weekly via cron.

The discipline: pattern match is the spark, fundamentals are the fuel. Every candidate
must still pass the existing gates (theme cap, entry cap, multiple confirming signals).

## License

Personal use only. Not for distribution.

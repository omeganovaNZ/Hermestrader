# Hermestrader — Alpaca Paper Trading Bot

An automated paper-trading system for Alpaca Markets with a rule-based strategy engine,
position manager, and research/backtest toolkit.

## What this is

This is a personal trading system that:
- Screens a watchlist of ~40 stocks using a 5-layer ensemble (technical, ML, sentiment, momentum, volatility)
- Manages positions with profit-taking and cap-trimming rules (Tom Nash framework)
- Tracks portfolio themes/sleeves with enforced caps
- Runs daily scans via cron jobs
- Places real orders in Alpaca paper trading ($100k account)

**This is NOT investment advice. Past performance does not guarantee future results.**

## Safety first

- **Dry-run default**: `position_manager.py` places real orders. Always test with `--dry-run` first.
- **No credential commits**: `alpaca_config.txt` is gitignored. Never commit it.
- **Public repo warning**: This repo is public. No secrets should ever be committed.
- **Theme cap enforced**: AI-hardware sleeve capped at 40% of equity (fail-closed).
- **Position cap**: Max 10% of equity per position (entry cap 8%).

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials (copy template, fill in your keys)
cp alpaca_config.example.txt alpaca_config.txt  # then edit

# 3. Run read-only tests (no network, no orders)
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
│   ├── ensemble_trader.py     # 5-layer ensemble signal generator
│   ├── market_aware_strategy.py  # ADX + Bollinger regime strategy
│   ├── position_manager.py    # Profit/cap trim rules, thesis review
│   ├── portfolio_rules.py     # Theme cap, thesis review (pure functions)
│   ├── stock_screener.py      # Technical entry scoring (0-100)
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
│   └── ...
│
└── assets/                # Generated chart images (gitignored)
    └── *.png
```

## Running tests

```bash
python run_tests.py
```

This discovers all `tests/test_*.py` files, runs each in a subprocess, and prints a summary.

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

## Cron jobs

The system uses local cron jobs (NZT) for daily scans. These are machine-local and
not part of the repo. See `docs/TRADING_PLAYBOOK.md` for the full schedule.

## License

Personal use only. Not for distribution.

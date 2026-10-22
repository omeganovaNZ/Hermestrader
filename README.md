# Hermestrader — Alpaca Paper Trading Bot

An automated paper-trading system for Alpaca Markets with a five-layer ensemble
signal engine, a position manager, a stock screener, and a pattern-match watchlist
generator.

**This is NOT investment advice. Past performance does not guarantee future results.**

## What this is

This is a personal trading system that:

- Screens the Standard & Poor's 500 (S&P 500) and Nasdaq-100 constituents (roughly
  500 to 600 unique tickers) using a technical entry score
- Generates entry and exit signals with regime-adaptive logic (Average Directional
  Index (ADX) plus Bollinger Bands plus a trend-strength override)
- Manages positions with profit-taking and cap-trimming rules (the Tom Nash
  framework)
- Tracks portfolio themes (sleeves) with enforced caps
- Runs ten scheduled jobs (daily scans, weekly reports, price alerts, and a
  pattern-match watchlist)
- Places real orders in Alpaca paper trading across three paper accounts

The code is written for one operator on one machine. It is public, so no secret
ever belongs in the repository.

## Key features

- **Ensemble signals.** Five independent layers are scored and combined, with a
  minimum live-layer gate before any action.
- **Regime awareness.** Trending versus ranging detection changes entry and exit
  persistence, frequency caps, and override behaviour.
- **Fail-closed risk limits.** The artificial intelligence (AI)-hardware sleeve
  is capped at 40 percent of equity and an unclassified symbol is refused rather
  than allowed through.
- **Winners-only trims.** No position is sold at a loss by the automated trim
  path; weakness is surfaced for a human decision instead.
- **Fractional, auditable orders.** Trim sizes are exact fractions of shares held,
  and fill state is recorded from the broker response rather than assumed.
- **Pure, testable rules.** Portfolio rules are pure functions with no network
  access, so they can be unit-tested in isolation.

## Architecture

### Signal pipeline (five layers)

1. **Technical layer** (30 percent) — Round-4 regime-aware ADX plus Bollinger
   Bands strategy with a graduated trend override
2. **Machine learning (ML) layer** (25 percent) — LightGBM prediction of the
   five-day forward return, trained per symbol and cached for the run
3. **Sentiment layer** (20 percent) — binary veto only (blocks trades when
   strongly negative, below 0.3)
4. **Momentum layer** (15 percent) — twelve-month return
5. **Volatility layer** (10 percent) — low-volatility preference (symmetric
   scoring)

Signals require three or more live layers (the constant `MIN_LIVE_LAYERS`). Fewer
forces a HOLD decision. Renormalisation over the live layers keeps the score on
its original scale when a layer is unavailable.

### Stock screener

`src/stock_screener.py` loads S&P 500 plus Nasdaq-100 constituents from
Wikipedia via `src/index_constituents.py` (cached locally with a seven-day
refresh). Each stock receives a technical entry score from 0 to 100 based on
trend, ADX, Relative Strength Index (RSI), distance from the 200-day moving
average, and momentum. The screener runs daily and is parallelised with five
workers.

### Regime-adaptive rules (Round-4)

- **Exit persistence:** five days in trends (ADX above 33), four days in ranging
  (ADX below 20), linear between
- **Entry persistence:** two days in trends, three days in ranging
- **Trend-strength override:** no sells when twelve-month momentum is above
  plus 50 percent and price is above the 200-day moving average
- **Graduated trend override:** ADX above 40 allows all sells; ADX 33 to 40
  requires confirmation
- **Volatility-scaled momentum bypass:** twenty-day momentum above 12 percent
  (high-volatility) or 15 percent (low-volatility)
- **Frequency cap:** two to four trades per week depending on regime

### Position management (Tom Nash framework)

Trimming is risk management on winners, not a reaction to weakness: "Selling is
what you do when the business is broken. Trimming is what you do when the winner
has grown."

A position is trimmed only when all four of these hold:

1. held longer than six months (more than 183 days)
2. return on investment (ROI) from the reference price of plus 100 percent or
   more
3. the last two daily closes both down
4. still above the 200-day moving average, so the pullback is against the trend
   rather than a trend break

...and then it sells 20 percent of the shares held. Growth alone never trims. After
a trim the reference price re-bases to the trim price, so the next trim needs
another plus 100 percent from there — one trim event per doubling, never a
cascade.

Also enforced:

- **Position cap:** 10 percent of equity per position, winners only. An over-cap
  position that is down is left alone (it becomes an add candidate).
- **Entry cap:** 8 percent, deliberately below the trim cap so a position has room
  to rise before the cap binds.
- **Add candidates:** a position 20 percent or more below its 52-week high is
  reported as an add candidate (report only, never auto-bought).
- **Thesis review:** positions held past 180 days and down 25 percent or more, or
  held a year or more and still below cost, are flagged for a human decision. It
  never sells.

### Portfolio rules (sleeves)

`src/portfolio_rules.py` defines the theme (sleeve) map and two pure functions:

- `theme_cap_check_safe` — refuses a buy that would push a theme past 40 percent
  of equity. Fails closed: an unclassified symbol, a non-positive equity value,
  or an evaluation error all refuse the order.
- `thesis_review` — flags weak positions for review (report only).

The AI-hardware sleeve groups symbols that move together (measured correlation),
not symbols that share a sector label.

### Pattern-match watchlist

`src/pattern_match_screen.py` compares the technical profiles of current holdings
from exactly two years ago against today's market to find stocks with similar
setups. A matching chart pattern is a flag to investigate, not a signal to buy:
fundamentals must corroborate before any entry, and any entry is a satellite
position (three to five percent).

### What does not work (tested and refuted)

- **External regime classification** — no improvement over Round-4's own ADX
  detection
- **Trend-riding overlay** — made choppy stocks worse without helping uptrends
- **Pre-filters on entries** — an RSI below 50 vetoed 87 percent of entries; ADX
  above 25 was near-neutral
- **Container system (two- and four-container)** — routing stocks to a strategy by
  an external regime classifier did not work as intended; the classifier and its
  output are removed
- **Trim ladder (+50 / +100 / +150 percent)** — replaced by the plus 100 percent
  on pullback rule
- **Restoring the ladder rungs** — tested and refuted; the pullback trigger alone
  is the improvement

## Safety first

- **Dry-run default.** `src/position_manager.py` places real orders. Always test
  with `--dry-run` first.
- **No credential commits.** `alpaca_config*.txt` is gitignored by glob. Verified
  clean. Only `alpaca_config.example.txt` belongs in version control.
- **Public repository warning.** This repository is public. No secret should ever
  be committed.
- **Theme cap enforced.** The AI-hardware sleeve is capped at 40 percent of
  equity, fail-closed.
- **Position cap.** Maximum 10 percent of equity per position (entry cap 8
  percent).
- **Winners-only trims.** Never sells a position at a loss on the automated trim
  path.
- **Real orders, real consequences.** Despite job names like "Trim Signal Alert",
  `run_position_management` calls `execute_trim`, which calls `place_sell_order`.
  It is not an alert.

## Quick start

```bash
pip install -r requirements.txt
cp alpaca_config.example.txt alpaca_config.txt   # then edit with your keys
python run_tests.py
python src/position_manager.py --dry-run
python src/stock_screener.py
```

`python src/portfolio_rules.py` exercises the pure rules with no network access.

## Project layout

```
Hermestrader/
├── README.md
├── requirements.txt
├── run_tests.py
├── accounts.json                 # canonical account registry (no secrets)
├── alpaca_config.example.txt     # credential template (committed)
├── watchlist.json                # trading watchlist (editable; built-in default fallback)
├── src/
│   ├── alpaca_trader.py          # Alpaca client, watchlist, order helpers
│   ├── ensemble_trader.py        # five-layer ensemble + ML + sentiment
│   ├── market_aware_strategy.py  # regime-aware ADX + Bollinger strategy
│   ├── position_manager.py       # profit trim, cap trim, add candidates
│   ├── portfolio_rules.py        # theme cap + thesis review (pure functions)
│   ├── stock_screener.py         # parallel technical scoring
│   ├── index_constituents.py     # S&P 500 + Nasdaq-100 loader (cached)
│   ├── pattern_match_screen.py   # historical-setup matcher
│   └── trading_strategy_engine.py # backtest engine + data fetch
├── tests/
│   ├── test_account_registry.py
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
│   ├── top10_growth_stocks_oct2025_oct2026.md
│   ├── alpaca_investment_research_report.txt
│   └── suggestions.md
├── data/                         # generated JSON (gitignored)
└── assets/                       # charts (gitignored)
```

## Configuration

All configuration lives in `alpaca_config.txt` (gitignored). Multiple accounts are
supported, one config file per account, each named after the account rather than
by position:

### Obtaining credentials

1. Create an account at https://alpaca.markets and open the paper-trading
   dashboard.
2. Generate an API key pair (key and secret) for paper trading.
3. Copy `alpaca_config.example.txt` to `alpaca_config.txt` and paste the key and
   secret:

   ```
   API_KEY=your_key_here
   API_SECRET=your_secret_here
   ```

4. Repeat for each additional account, naming the file after the account (see the
   table below). Never commit any `alpaca_config*.txt` file.

### Accounts

| Account | Number | Config file |
|---|---|---|
| Core | PA3JY31PP | `alpaca_config.txt` |
| Pattern Match | PA3JNJZ0X | `alpaca_config_pattern_match.txt` |
| Container Test 1 | PA3HV7XBX | `alpaca_config_container_test1.txt` |

`accounts.json` is the canonical registry binding account name to number to config
file. Read it rather than guessing which file holds which account. `.gitignore`
excludes `alpaca_config*.txt` by glob, so a newly added account config is never
committable. The "Container Test 1" name is historical: it was created to test a
two-container framework that was retired on 2026-10-21; the account kept its
name.

Credentials format:

```
API_KEY=your_key_here
API_SECRET=your_secret_here
```

## Running the system

```bash
# Daily paper-trading scan (places orders on buy signals)
python src/alpaca_trader.py

# Five-layer ensemble scan (writes data/ensemble_signals.json)
python src/ensemble_trader.py

# Position management: profit trims, cap trims, add candidates (dry run first)
python src/position_manager.py --dry-run

# Stock screener (writes data/screener_results.json)
python src/stock_screener.py

# Pattern-match watchlist (writes data/pattern_match_results.json)
python src/pattern_match_screen.py

# Market-aware backtest
python src/market_aware_strategy.py

# Multi-strategy backtest on one ticker
python src/trading_strategy_engine.py
```

### Turning screener results into a watchlist

Two steps:

```bash
# 1. Run the screener (writes data/screener_results.json)
python src/stock_screener.py

# 2. Convert top candidates to watchlist.json (read by alpaca_trader.py)
python src/screener_to_watchlist.py
```

The converter keeps `STRONG BUY` and `BUY` candidates (entry score 55 or
higher), de-duplicates by ticker, maps sectors to market configs, and writes
`watchlist.json`. Edit `watchlist.json` afterwards to add, remove, or re-classify
symbols. `src/alpaca_trader.py` keeps its built-in list as a fallback when
`watchlist.json` is absent.

### After the dry run

Once `position_manager.py --dry-run` completes, the natural progression is:

1. **Stock screener** — `python src/stock_screener.py` (writes
   `data/screener_results.json`).
2. **Daily scan** — `python src/alpaca_trader.py` (places paper orders on buy
   signals; uses the Core account by default).
3. **Ensemble scan** — `python src/ensemble_trader.py` for the five-layer view
   (slower: trains the machine learning (ML) model per symbol).
4. **Pattern-match watchlist** — `python src/pattern_match_screen.py`.
5. **Backtests** — `python src/market_aware_strategy.py` or
   `python src/trading_strategy_engine.py`.

Market orders placed by the daily scan fill at the next market open; re-run
`position_manager.py --dry-run` afterwards to review the new positions. Never run
`position_manager.py` without `--dry-run` unless you intend real paper orders.

## Running tests

```bash
python run_tests.py
```

The runner discovers `tests/test_*.py`, runs each in a subprocess, and prints a
summary. It exits non-zero if any test fails. Eight test files cover the account
registry, cap-trim guards, ensemble fixes, ladder-state persistence, portfolio
rules, position sizing, profit trim, and trim rules.

Tests that touch the network or a live Alpaca account require valid credentials
and are environment-dependent; the pure-rule tests
(`test_portfolio_rules.py`, `test_position_sizing.py`, `test_profit_trim.py`)
need no network.

## Scheduled jobs

| Job | Schedule | Description |
|---|---|---|
| Daily Trading News Brief | Weekdays 08:00 | News scan |
| Daily Stock Screener | Every day 08:00 | S&P 500 + Nasdaq-100 scoring |
| Daily Alpaca Paper Trading Scan | Weekdays 08:00 | Portfolio scan (places orders) |
| Trim Signal Alert | Weekdays 08:00 | Trim check (places orders) |
| Weekly Structural Trends Brief | Mondays 08:00 | Trend analysis |
| Weekly Trading Performance Report | Mondays 08:00 | Performance summary |
| Weekly Pattern-Match Watchlist | Mondays 08:00 | Pattern-match screener |
| Price Watch — ASML | Weekdays 08:00 | Alerts when ASML is below 1,600 US dollars |
| Price Watch — STX | Weekdays 08:00 | Alerts when STX is below 600 US dollars |
| 1-Month Trade Exit (AMD/LLY) | 16 Nov 09:00 | One-time exit check |

Times are New Zealand Time (NZT). All ten jobs deliver to a channel; previously
they wrote to disk and were never surfaced.

## Data files

Generated artefacts (gitignored, under `data/`):

- `alpaca_trades_log.json` — fills and cancelled orders, derived from Alpaca
  order history
- `trim_log.json` — all trims placed
- `trim_ladder_state.json` — per-symbol trim reference prices and fired rungs
- `screener_results.json` — screener output
- `ensemble_signals.json` — ensemble signals (check `layers_used` before
  trusting)
- `pattern_match_results.json` — pattern-match candidates
- `index_constituents.json` — cached S&P 500 + Nasdaq-100 list (seven-day
  refresh)

## Known limitations

- **No sector field from Alpaca's free tier.** The theme map in
  `src/portfolio_rules.py` is hand-maintained; an unclassified symbol escapes
  the cap entirely until it is added.
- **Pattern-match holdings are hardcoded** in `src/pattern_match_screen.py` and
  can drift from the live Alpaca book.
- **Watchlists and thresholds are scattered** across modules as literals; a
  different operator must edit source to change them.
- **Position age is inferred** from the earliest filled buy in order history, so
  a fully sold and re-bought position looks older than it is.
- **The ensemble ML layer needs scikit-learn** (a LightGBM dependency) in
  addition to LightGBM itself.
- **Dependencies.** `requirements.txt` must list `alpaca-py` (the `alpaca.*`
  import path used by the code), not the legacy `alpaca-trade-api`, plus
  `scikit-learn`.

## Proposed changes

The following are proposed, not yet applied. See `docs/suggestions.md` for the
full list.

1. Correct `requirements.txt` to depend on `alpaca-py` and `scikit-learn`
   (the code already imports the new SDK).
2. Add a setup script that verifies the environment, copies the credential
   template, and runs the pure-rule tests.
3. Mock the Alpaca client in `tests/test_trim_rules.py` (or gate it behind a
   live flag) so it does not require real credentials.
4. Make `test_account_registry.py` tolerate missing, gitignored secret files or
   document their creation in onboarding.
5. Rename the historically named "Container Test 1" account to something that
   reflects its current role.
6. Externalise watchlists, thresholds, theme maps, and paths into one config
   file, keeping secrets separate.
7. Add a licence file (currently "personal use only" in prose only).
8. Add continuous integration that runs the pure-rule tests on every change.

## Glossary

- **ADX** — Average Directional Index, a trend-strength indicator.
- **RSI** — Relative Strength Index, a momentum oscillator.
- **DMA** — day moving average (for example, 200-DMA is the 200-day moving
  average).
- **MA** — moving average.
- **ML** — machine learning.
- **ROI** — return on investment.
- **API** — application programming interface.
- **NZT** — New Zealand Time.
- **AI** — artificial intelligence.

## Licence

Personal use only. Not for distribution.

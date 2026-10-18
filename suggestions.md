# Suggested Repo Improvements

**Audience:** Another AI agent (or human) tasked with modernising this repo for sharing.
**Scope:** Non-breaking improvements only — do not refactor trading logic, change strategy rules, or touch live credentials.
**Repo:** `Hermestrader` — an Alpaca paper-trading system with a rule-based strategy engine, position manager, and research tooling.

---

## 1. Add a `README.md` (highest priority)

The repo has **no README**. A newcomer has no idea what this is, how to run it, or what the safety rules are.

### What to include

| Section | Content |
|---|---|
| **What this is** | One-paragraph summary: Alpaca paper-trading bot with theme-cap rules, profit/cap trims, thesis review, and a research/backtest toolkit. |
| **Safety first** | Bullet list from `HANDOFF_2026-10-18.md` §1 — dry-run default, no credential commits, public-repo warning. |
| **Quick start** | `pip install -r requirements.txt` → `cp alpaca_config.example.txt alpaca_config.txt` → `python portfolio_rules.py` (pure functions, no network). |
| **Project structure** | See §2 below. |
| **Running tests** | `python run_tests.py` (after implementing suggestion #3). |
| **Live trading** | Only via explicit user invocation. Never cron `position_manager.py` without `--dry-run`. |

### Source material to draw from

- `HANDOFF_2026-10-18.md` §1 (safety rules) and §2 (environment)
- `TRADING_PLAYBOOK.md` (strategy overview)
- `portfolio_rules.py` module docstring

---

## 2. Tidy the repo home — move files into subdirectories

The root has **74 files**, mixing durable code, one-off tests, dated handoff notes, backtest artefacts, and research reports. This is disorienting for a newcomer and makes it hard to tell what's load-bearing.

### Proposed structure

```
Hermestrader/
├── README.md                  # NEW — see §1
├── requirements.txt           # NEW — see §4
├── run_tests.py               # NEW — see §3
├── setup_repo.py              # NEW — onboarding script, see §5
│
├── src/                       # Durable, runnable modules
│   ├── alpaca_trader.py
│   ├── ensemble_trader.py
│   ├── trading_strategy_engine.py
│   ├── position_manager.py
│   ├── portfolio_rules.py
│   ├── portfolio_allocation.py
│   ├── stock_screener.py
│   ├── news_monitor.py
│   ├── earnings_scanner.py
│   ├── structural_trends_tracker.py
│   ├── fetch_stock_metrics.py
│   ├── hybrid_strategy_backtest.py
│   ├── multi_stock_backtest.py
│   ├── market_aware_strategy.py
│   ├── verify_data.py
│   ├── initial_portfolio_entry.py
│   ├── compare_results.py
│   └── trim_crossval.py
│
├── tests/                     # All test_*.py files
│   ├── test_alpaca.py
│   ├── test_alpaca_api.py
│   ├── test_alpaca_api2.py
│   ├── test_cap_trim_guard.py
│   ├── test_ensemble_fixes.py
│   ├── test_ladder_state_persistence.py
│   ├── test_portfolio_rules.py
│   ├── test_position_sizing.py
│   ├── test_profit_trim.py
│   └── test_trim_rules.py
│
├── docs/                      # Human-facing prose
│   ├── TRADING_PLAYBOOK.md
│   ├── NZ_AUS_Market_Research.md
│   ├── HANDOFF_2026-10-17.md
│   └── HANDOFF_2026-10-18.md
│
├── data/                      # Generated JSON artefacts (gitignored)
│   ├── *_backtest_results.json
│   ├── *_comparison.json
│   ├── screener_results.json
│   ├── ensemble_signals.json
│   ├── structural_trends*.json
│   ├── news_events_log.json
│   ├── alpaca_trades_log.json
│   ├── trim_log.json
│   └── …etc
│
├── research/                  # One-off analysis & reports
│   ├── alpaca_investment_research_report.txt
│   ├── top10_growth_stocks_oct2025_oct2026.md
│   ├── top10_growth_current_analysis.json
│   └── AAPL_backtest_results.json
│
└── assets/                    # Generated chart images (gitignored)
    ├── *.png
    └── *.pyc / __pycache__/
```

### Files that can be deleted (disused / redundant)

| File | Reason |
|---|---|
| `test_alpaca.py` | Superseded by `test_alpaca_api.py` and `test_alpaca_api2.py` — appears to be the earliest throwaway iteration. |
| `market_conditions_analysis.json` | 276 bytes — trivial snapshot, superseded by later analysis. |
| `one_month_trades.json` | 756 bytes — stale; covered by `alpaca_trades_log.json`. |
| `paper_trading_simulation.json` | 426 bytes — superseded by live Alpaca data. |
| `paper_trading_simulation.py` | 4 KB — early prototype; the real system is `alpaca_trader.py`. |

**Before deleting anything:** grep for imports of these files across the repo. If nothing references them, they are safe to remove.

---

## 3. Add a test runner

Tests are plain scripts that print `PASS <name>`. There is no way to run them all at once or get a summary.

### Proposal: `run_tests.py`

```python
# run_tests.py — discovers and runs all test_*.py files in tests/, prints summary.
# Usage: python run_tests.py
```

- Discovers `tests/test_*.py`
- Runs each in a subprocess (so a crash in one doesn't stop the rest)
- Prints a summary line: `11 passed, 0 failed` or `9 passed, 2 failed`
- Exits non-zero if any failed

---

## 4. Add `requirements.txt`

The repo has no dependency manifest. A newcomer has to guess.

### Known imports (from reading the source)

```
requests>=2.28
pandas>=2.0
```

Add a comment noting that `alpaca-trade-api` may also be needed if any module imports it (check before committing).

---

## 5. Add an onboarding script (`setup_repo.py`)

A single script a newcomer runs once to verify their environment works without touching live trading.

### What it should do

1. **Check Python version** — require 3.10+.
2. **Install dependencies** — `pip install -r requirements.txt`.
3. **Create `alpaca_config.txt`** from `alpaca_config.example.txt` if it doesn't exist (copy template, warn user to fill in).
4. **Run read-only smoke tests** — call `portfolio_rules.py` pure functions, `verify_data.py` with `dry_run` mode if available.
5. **Run all tests** — delegate to `run_tests.py`.
6. **Print next steps** — point to README, explain dry-run vs live mode.

### `alpaca_config.example.txt`

```
API_KEY=your_key_here
API_SECRET=your_secret_here
BASE_URL=https://paper-api.alpaca.markets
```

---

## 6. Code-quality observations (lower priority)

These are non-blocking notes for future work. Do **not** fix these in the same PR as the above.

| Area | Observation |
|---|---|
| **Secrets hygiene** | `verify_data.py` reads `alpaca_config.txt` at module load (line 23). If this file is ever accidentally committed, credentials leak. Consider a lazy loader. |
| **Test naming** | `test_alpaca.py`, `test_alpaca_api.py`, `test_alpaca_api2.py` — the `_api2` suffix suggests trial-and-error. Consider renaming to describe what each tests. |
| **Hardcoded paths** | `HANDOFF_2026-10-18.md` references `C:\Users\Omega\...` — stale paths from the original author. Not a code issue but confusing in docs. |
| **Type hints** | `portfolio_rules.py` uses `dict` and `list` bare. Could upgrade to `dict[str, Any]` etc. for clarity, but not urgent. |
| **Docstring coverage** | Most modules lack module-level docstrings. The ones that have them (`portfolio_rules.py`) are excellent — that's the standard to match. |

---

## 7. Suggested PR sequence

If you are implementing these as PRs, this order minimises risk:

| PR | Contents | Risk |
|---|---|---|
| **PR 1** | Add `README.md`, `requirements.txt`, `run_tests.py`, `setup_repo.py` | None — additive only |
| **PR 2** | Move files into `src/`, `tests/`, `docs/`, `data/`, `research/`, `assets/`; update imports | Low — mechanical, but test everything still runs |
| **PR 3** | Delete disused files (table in §2) | Low — only after import check confirms nothing references them |
| **PR 4** | Code-quality fixes (§6) | Separate — don't bundle with restructuring |

---

## 8. Separate out configuration

Values that a different operator would need to change are currently scattered across the
source as literals and module-level constants. Nothing here is broken — it works for one
person on one machine — but "prepare for sharing" means the next person should be able to
point this at their own account, watchlist and risk appetite without editing Python.

### Categories worth externalising

| Category | What it looks like today | Why it should move |
|---|---|---|
| **Credentials** | Read from `alpaca_config.txt` — already good, but each module re-implements its own loader. | One shared loader; one place to change. |
| **Watchlists / ticker universes** | Ticker lists hardcoded in several scripts. | A newcomer trades different names. |
| **Strategy thresholds** | Caps, trim rungs, review windows and drawdown triggers live as constants inside modules. | These are risk appetite — the owner's, not the code's. |
| **Theme / sector map** | Hand-maintained map inside the rules module (already flagged as a limitation in its docstring). | Should be data, editable without touching logic. |
| **Dates & lookback windows** | Fixed dates and `timedelta` windows pinned to the author's analysis period. | Rot for anyone else; should be relative or configured. |
| **File paths** | Absolute paths to one specific user's home directory appear in a few scripts. | Breaks instantly on any other machine. |
| **API endpoints / URLs** | Base URLs duplicated across modules. | Single source of truth; easier to point at a mock or paper endpoint. |
| **Run mode (dry-run vs live)** | Defaults live in code and are easy to get wrong. | Should be an explicit, visible setting — safety-critical. |

### Suggested approach

- **One config file** (e.g. `config.yaml` or `config.toml`) for everything non-secret:
  thresholds, watchlists, theme map, endpoints, paths.
- **Keep secrets separate** — credentials stay in the gitignored file, referenced by the config, never merged into it.
- **Ship a committed example/template** with safe placeholder values so a newcomer has something to copy.
- **Sane defaults in code, overrides from config** — the system should still run with no config present, using conservative defaults.
- **Do this last.** Configuration extraction touches nearly every module and is the riskiest change here. It deserves its own PR, after the structure is settled and tests can catch regressions.

### Why this matters for sharing

The goal isn't tidiness for its own sake — it's that someone else can clone the repo, fill in
one file, and have a working system that reflects *their* risk rules rather than inheriting
the original owner's. Right now that isn't possible without reading and editing the source.

---

## What NOT touch

- **`alpaca_config.txt`** — live paper credentials, gitignored, never commit.
- **`portfolio_rules.py` logic** — the theme cap and thesis review rules are the system's core. Refactoring them risks breaking live trading.
- **`TRADING_PLAYBOOK.md`** — this is the human's strategy doc. Only move it; don't rewrite.
- **Cron configuration** — any existing cron jobs reference specific file paths. Moving files without updating cron will break scheduled tasks.

---

*Suggestions compiled 2026-10-18 by reviewing the repo at commit `4b67c35`.*

"""Rebuild of the trim-strategy cross-validation harness.

Why this exists: the original harness was not kept, so the documented numbers in
TRADING_PLAYBOOK.md could not be reproduced. This rebuilds it and is validated by checking
it reproduces the documented Panel A results (HOLD median 5.819, LADDER 4.049).

Method (from references/trim-strategy-cross-validation.md):
  - every strategy armed at the SAME price on the same day
  - valued as cash + remaining_shares * last_close, normalised by the entry value,
    so $1,000 notional is comparable across names
  - panels reported separately (a single median across both hides a sign flip)

Invariants this harness must satisfy (from the trading-backtesting skill):
  - cash credit and share removal use the SAME quantity
  - a sell-only strategy CANNOT beat buy-and-hold on the same instrument
  - when a result looks wrong, print the trades rather than reason about it
"""
import json
import sys

import numpy as np
import pandas as pd
import yfinance as yf

PANEL_A = ["AXTI", "SNDK", "MRNA", "IOVA", "TXG", "KOD", "LITE", "MU", "MXL", "VICR"]
PANEL_A_START = "2025-10-15"

# Sharesies holdings with a usable gain/loss. NZX/ASX names need a suffix.
PANEL_B_RAW = [
    ("AIR", -33.16, "AIR.NZ"), ("GOOG", 1.52, "GOOG"), ("ASML", 24.09, "ASML"),
    ("BAP", -11.40, "BAP.AX"), ("QBTS", -45.75, "QBTS"), ("DXYZ", -17.35, "DXYZ"),
    ("IREN", -40.56, "IREN"), ("NOK", -12.65, "NOK"), ("PEB", -84.20, "PEB.NZ"),
    ("DTIL", -15.79, "DTIL"), ("RGTI", -39.57, "RGTI"), ("RKLB", 118.06, "RKLB"),
    ("TSLA", 81.31, "TSLA"), ("TTT", -99.88, "TTT.AX"), ("VOOG", 11.94, "VOOG"),
]
# Skipped in the original run: CO2 and USH (INSUFFICIENT_DATA), GFI (-100% zeroes the basis)
PANEL_B_SKIP = {"CO2", "GFI", "USH"}

RUNGS = [(0.50, 0.10), (1.00, 0.20), (1.50, 0.30)]
TOP_RUNG = 1.50
COMMISSION = 0.001     # 0.1% per trade


def fetch(symbol, start="2024-01-01"):
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Close"]].dropna()          # drop trailing partial bars (NaN OHLC)
    df.index = df.index.tz_localize(None)
    return df["Close"] if len(df) else None


def down_days(closes, i, n=2):
    if i < n:
        return False
    for k in range(n):
        if not closes[i - k] < closes[i - k - 1]:
            return False
    return True


def above_sma(closes, i, window=200):
    if i + 1 < window:
        return None
    return closes[i] > float(np.mean(closes[i - window + 1:i + 1]))


def extension(closes, i, window=50):
    """How extended the move is: close / N-day SMA. None when it cannot be computed."""
    if i + 1 < window:
        return None
    sma = float(np.mean(closes[i - window + 1:i + 1]))
    return closes[i] / sma if sma > 0 else None


class Hold:
    name = "HOLD"

    def init(self, px):
        return {}

    def signal(self, st, closes, i):
        return 0.0


class Ladder:
    """The old ladder: fires the moment a rung is crossed, i.e. into strength."""
    name = "LADDER"

    def init(self, px):
        return {'base': px, 'fired': set()}

    def signal(self, st, closes, i):
        px = closes[i]
        gain = px / st['base'] - 1
        for rung, size in RUNGS:
            if rung not in st['fired'] and gain >= rung:
                st['fired'].add(rung)
                if rung == TOP_RUNG:
                    st['base'] = px
                    st['fired'] = set()
                return size
        return 0.0


class PullbackMixin:
    """Fires only on a 2-day pullback while still above the 200-day average."""

    def gated(self, st, closes, i):
        if not down_days(closes, i, 2):
            return False
        a = above_sma(closes, i)
        # NB: `a is True` is always False here - a numpy comparison returns np.bool_, and
        # np.True_ is not the Python singleton True. That silently disabled every variant
        # using this gate, leaving them identical to HOLD.
        return a is not None and bool(a)


class UserRule(PullbackMixin):
    """The user's rule: one rung at +100%, on a pullback, then re-base to the trim price."""
    base_name = "USER"

    def __init__(self, min_hold=0):
        self.min_hold = min_hold
        self.name = self.base_name + (f"+{min_hold}d" if min_hold else "")

    def init(self, px):
        return {'base': px, 'armed_at': None}

    def signal(self, st, closes, i):
        if st['armed_at'] is None:
            st['armed_at'] = i
        if i - st['armed_at'] < self.min_hold:
            return 0.0
        px = closes[i]
        if px / st['base'] - 1 < 1.00:
            return 0.0
        if not self.gated(st, closes, i):
            return 0.0
        st['base'] = px                      # re-base to the trim price
        return 0.20


class Synth(PullbackMixin):
    """Ladder LEVELS + the user's pullback TRIGGER.

    The pullback condition does the job the adaptive parabolic gate used to do: a stock
    that is rocketing never posts 2 consecutive down days, so the +50% rung cannot fire
    into a vertical move. That is what makes the low rung safe to restore.
    """
    base_name = "SYNTH"

    def __init__(self, min_hold=0):
        self.min_hold = min_hold
        self.name = self.base_name + (f"+{min_hold}d" if min_hold else "")

    def init(self, px):
        return {'base': px, 'fired': set(), 'armed_at': None}

    def signal(self, st, closes, i):
        if st['armed_at'] is None:
            st['armed_at'] = i
        if i - st['armed_at'] < self.min_hold:
            return 0.0
        px = closes[i]
        gain = px / st['base'] - 1
        if not self.gated(st, closes, i):
            return 0.0
        for rung, size in RUNGS:
            if rung not in st['fired'] and gain >= rung:
                st['fired'].add(rung)
                if rung == TOP_RUNG:
                    st['base'] = px
                    st['fired'] = set()
                return size
        return 0.0


class UserNoMA(UserRule):
    """The user's rule WITHOUT the 200-day condition. Isolates what that condition costs:
    a name that tops out and rolls below its average can then never be trimmed at all."""
    base_name = "USER-noma"

    def gated(self, st, closes, i):
        return down_days(closes, i, 2)


class SynthNoMA(Synth):
    """Ladder levels + pullback, without the 200-day condition."""
    base_name = "SYNTH-noma"

    def gated(self, st, closes, i):
        return down_days(closes, i, 2)


class SynthGated(Synth):
    """Ladder levels + pullback trigger + the ADAPTIVE PARABOLIC GATE.

    The gate is the one mechanism the earlier research showed improves the winners panel
    without damaging the holdings panel (+0.184 / -0.006). It skips the +50% rung when the
    move is already extended (`close / 50-day SMA >= 1.20`), which is precisely the case
    where a low rung cuts a multi-bagger short. Combined with the pullback trigger it means
    the low rung only harvests CHOPPY winners - the flat names where the ladder's edge lives.
    """
    base_name = "SYNTH-gate"

    def signal(self, st, closes, i):
        if st['armed_at'] is None:
            st['armed_at'] = i
        if i - st['armed_at'] < self.min_hold:
            return 0.0
        px = closes[i]
        gain = px / st['base'] - 1
        if not self.gated(st, closes, i):
            return 0.0
        for rung, size in RUNGS:
            if rung in st['fired']:
                continue
            if gain < rung:
                break
            if rung == RUNGS[0][0]:                     # only the first rung is gated
                ext = extension(closes, i, 50)
                if ext is not None and ext >= 1.20:
                    st['fired'].add(rung)               # passed without selling
                    continue
            st['fired'].add(rung)
            if rung == TOP_RUNG:
                st['base'] = px
                st['fired'] = set()
            return size
        return 0.0


def simulate(closes, entry_idx, strategy, commission=COMMISSION):
    """Bar-by-bar. `sold` is computed ONCE and used for both the cash credit and the
    share removal - crediting one quantity while removing another is the bug that made
    an earlier version of this harness report a 13x return on a stock that rose 3.3x."""
    px0 = float(closes[entry_idx])
    shares = 1000.0 / px0
    cash = 0.0
    st = strategy.init(px0)
    trades = []
    for i in range(entry_idx, len(closes)):
        px = float(closes[i])
        frac = strategy.signal(st, closes, i)
        if frac and frac > 0:
            sold = shares * frac
            if sold > 1e-12:
                cash += sold * px * (1 - commission)
                shares -= sold
                trades.append((i, px, sold))
    final = cash + shares * float(closes[-1])
    return final / 1000.0, trades


def run_panel(name, entries, strategies, commission=COMMISSION):
    """entries: list of (label, series, entry_idx)"""
    results = {s.name: [] for s in strategies}
    detail = {}
    for label, closes, idx in entries:
        row = {}
        for s in strategies:
            v, trades = simulate(closes, idx, s, commission)
            results[s.name].append(v)
            row[s.name] = v
        detail[label] = row
    print(f"\n=== {name} ({len(entries)} names) ===")
    print(f"{'strategy':<14}{'median':>9}{'mean':>9}{'worst':>9}{'best':>9}{'beats HOLD':>12}")
    hold = results["HOLD"]
    for s in strategies:
        v = np.array(results[s.name])
        beats = np.mean(v > np.array(hold) + 1e-12) * 100
        print(f"{s.name:<14}{np.median(v):>9.3f}{v.mean():>9.3f}{v.min():>9.3f}"
              f"{v.max():>9.3f}{beats:>11.0f}%")
    return results, detail


def main():
    print("=" * 78)
    print("  TRIM-STRATEGY CROSS-VALIDATION (rebuilt)")
    print(f"  commission {COMMISSION:.1%} per trade")
    print("=" * 78)

    # The -noma variants proved IDENTICAL to their gated twins on every name (see the
    # "200-day condition never binds" note in the report), so they are dropped here to keep
    # the tables readable.
    strategies = [Hold(), Ladder(),
                  UserRule(), UserRule(min_hold=183),
                  Synth(), Synth(min_hold=183),
                  SynthGated(), SynthGated(min_hold=183)]

    # ---- Panel A: armed at the 2025-10-15 close
    # NB: keep the FULL series and point at the entry index. Slicing the series to start at
    # the entry date destroys the 200-day SMA warm-up, which blocks every pullback variant
    # for its first 199 bars while LADDER - which needs no average - can act from bar 1.
    # That is a property of the test, not of the strategies.
    a_entries = []
    for sym in PANEL_A:
        c = fetch(sym)
        if c is None:
            print(f"  Panel A: no data for {sym}"); continue
        idx = int(np.argmax(c.index >= pd.Timestamp(PANEL_A_START)))
        if c.index[idx] < pd.Timestamp(PANEL_A_START):
            print(f"  Panel A: {sym} has no data on/after {PANEL_A_START}"); continue
        if len(c) - idx < 30:
            print(f"  Panel A: too little data after entry for {sym}"); continue
        a_entries.append((sym, c.to_numpy(dtype=float), idx))

    # ---- Panel B: armed at the first close that reached the inferred basis
    # The playbook says both panels share ONE UNIFORM WINDOW, so the arming search is
    # confined to it. Searching the whole history instead arms names at the very start of
    # the data - for DXYZ that is a close of $59.20 against a $33.77 basis, i.e. 75% above
    # cost, where no rung is reachable and the strategy looks inert. That artefact is what
    # made an earlier version of this run disagree with the documented Panel B.
    b_entries = []
    for ticker, gain, yf_sym in PANEL_B_RAW:
        if ticker in PANEL_B_SKIP:
            continue
        if abs(1 + gain / 100.0) < 1e-9:
            print(f"  Panel B: {ticker} skipped (-100% gain zeroes the basis)"); continue
        c = fetch(yf_sym)
        if c is None or len(c) < 60:
            print(f"  Panel B: no data for {ticker} ({yf_sym})"); continue
        arr = c.to_numpy(dtype=float)
        basis = arr[-1] / (1 + gain / 100.0)     # unit-safe: ratio against the last close
        w0 = int(np.argmax(c.index >= pd.Timestamp(PANEL_A_START)))
        hit = next((i for i in range(w0, len(arr)) if arr[i] >= basis), None)
        if hit is None:
            print(f"  Panel B: {ticker} skipped (price never reached its basis in the window)")
            continue
        b_entries.append((ticker, arr, hit))

    res_a, det_a = run_panel("PANEL A - highest-growth stocks", a_entries, strategies)
    res_b, det_b = run_panel("PANEL B - Sharesies holdings", b_entries, strategies)

    print("\n=== per-name, Panel B (the actual book) ===")
    print(f"{'name':<7}" + "".join(f"{s.name:>13}" for s in strategies))
    for label, row in det_b.items():
        print(f"{label:<7}" + "".join(f"{row[s.name]:>13.3f}" for s in strategies))

    print("\n=== HARNESS VALIDATION ===")
    print("  Documented Panel A: HOLD median 5.819, LADDER median 4.049")
    print(f"  Reproduced:         HOLD median {np.median(res_a['HOLD']):.3f}, "
          f"LADDER median {np.median(res_a['LADDER']):.3f}")
    ok = abs(np.median(res_a['HOLD']) - 5.819) < 0.6 and abs(np.median(res_a['LADDER']) - 4.049) < 0.6
    print(f"  -> {'MATCHES (harness reproduces the documented result)' if ok else 'DOES NOT MATCH - treat all numbers as suspect'}")

    json.dump({'panel_a': res_a, 'panel_b': res_b, 'detail_b': det_b},
              open(r"C:\Users\Omega\AppData\Local\hermes\cache\scratch\trim_crossval.json", "w"),
              indent=1, default=str)
    print("\n  saved -> trim_crossval.json")


if __name__ == "__main__":
    main()

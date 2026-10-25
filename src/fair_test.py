"""Out-of-sample (fair) test harness — the gate every proposed rule must pass.

WHY THIS EXISTS. The screener's technical score has no forward predictive power. Run as
of 2026-04-25 on the 500-name universe, its 102 picks returned +3.5% to 2026-10-25
versus +7.0% for SPY and +8.3% for the average name in the same universe. A screen that
is scored on the same window it selects from is guaranteed to look good; this harness
scores on a PAST date and measures the return FORWARD, with no hindsight.

THE DISCIPLINE (from the playbook's standing principle):
  1. A change must be tested, not asserted.
  2. It must improve one regime without damaging another.
  3. Refutations are kept, not discarded.
  4. Code follows evidence, not the reverse.

USAGE:
    python src/fair_test.py --as-of 2026-04-25 --end 2026-10-25

It scores the universe on bars up to --as-of, applies the entry criteria, then measures
the forward return to --end. It writes the picks to data/fair_test_picks.json.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.stock_screener import calculate_technical_score

CRIT = dict(score=70, rsi_lo=40, rsi_hi=75, max_3m=80.0)


def load_universe():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "screener_results.json")
    if not os.path.exists(path):
        return []
    return [r["ticker"] for r in json.load(open(path))]


def run(as_of, end, universe=None):
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    as_of = pd.Timestamp(as_of)
    end = pd.Timestamp(end)
    start = as_of - pd.DateOffset(years=2)
    if universe is None:
        universe = load_universe()
    print(f"Universe: {len(universe)}. Scoring as of {as_of.date()}, forward to {end.date()}")

    def work(sym):
        try:
            d = yf.download(sym, start=start, end=end + pd.Timedelta(days=1),
                            progress=False, auto_adjust=True)
            if d is None or d.empty:
                return None
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            if 'Close' not in d.columns:
                return None
            d = d[d['Close'].notna()]
            d.index = pd.to_datetime(d.index).tz_localize(None)
            hist = d[d.index <= as_of]
            fwd = d[d.index <= end]
            if len(hist) < 260 or len(fwd) < 60:
                return None
            tech = calculate_technical_score(hist)
            if tech is None:
                return None
            entry_px = float(hist['Close'].iloc[-1])
            cur_px = float(fwd['Close'].iloc[-1])
            return dict(sym=sym, score=tech['entry_score'], rsi=tech['rsi'],
                        ret_3m=tech['return_3m'], entry=entry_px, cur=cur_px,
                        fwd_ret=(cur_px / entry_px - 1) * 100)
        except Exception:
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in as_completed([ex.submit(work, s) for s in universe]):
            r = f.result()
            if r:
                rows.append(r)

    picks = [r for r in rows if r['score'] >= CRIT['score']
             and CRIT['rsi_lo'] <= r['rsi'] <= CRIT['rsi_hi']
             and r['ret_3m'] < CRIT['max_3m']]
    picks.sort(key=lambda x: -x['score'])

    print(f"\nUsable: {len(rows)}   Passing criteria as of {as_of.date()}: {len(picks)}")
    if picks:
        print(f"  mean forward return: {np.mean([r['fwd_ret'] for r in picks]):+.1f}%")
        print(f"  median: {np.median([r['fwd_ret'] for r in picks]):+.1f}%")
    if rows:
        print(f"  all usable names mean: {np.mean([r['fwd_ret'] for r in rows]):+.1f}%")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "data", "fair_test_picks.json")
    json.dump(picks, open(out, "w"), indent=2)
    print(f"\nPicks saved to {out}")
    return picks, rows


def main():
    ap = argparse.ArgumentParser(description="Out-of-sample fair test of the screener")
    ap.add_argument("--as-of", default="2026-04-25")
    ap.add_argument("--end", default="2026-10-25")
    args = ap.parse_args()
    run(args.as_of, args.end)


if __name__ == "__main__":
    main()

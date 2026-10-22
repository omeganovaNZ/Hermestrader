"""Convert screener results into the watchlist.json format.

Usage:
    python src/stock_screener.py          # step 1: produce data/screener_results.json
    python src/screener_to_watchlist.py  # step 2: produce watchlist.json

The converter reads data/screener_results.json, keeps the candidates that meet
the rating/score thresholds, maps each sector to a market config, and writes
watchlist.json (which src/alpaca_trader.py picks up automatically).
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENER = os.path.join(REPO, "data", "screener_results.json")
OUTPUT = os.path.join(REPO, "watchlist.json")

# Best-effort sector -> market config. Unknown sectors default to US_TECH, which
# is what the built-in watchlist already does for biotech, energy-adjacent and
# space names.
SECTOR_CONFIG = {
    "semiconductor": "SEMICONDUCTOR_LOGIC",
    "semiconductor memory": "SEMICONDUCTOR_MEMORY",
    "semiconductors": "SEMICONDUCTOR_LOGIC",
    "power": "POWER_ENERGY",
    "energy": "POWER_ENERGY",
    "utilities": "POWER_ENERGY",
}


def config_for(sector):
    key = (sector or "").strip().lower()
    if key in SECTOR_CONFIG:
        return SECTOR_CONFIG[key]
    for hint, cfg in SECTOR_CONFIG.items():
        if hint in key:
            return cfg
    return "US_TECH"


def main():
    ap = argparse.ArgumentParser(description="Convert screener results to watchlist.json")
    ap.add_argument("--input", default=SCREENER, help="screener_results.json path")
    ap.add_argument("--output", default=OUTPUT, help="watchlist.json path")
    ap.add_argument("--ratings", nargs="+", default=["STRONG BUY", "BUY"],
                    help="ratings to include (default: STRONG BUY BUY)")
    ap.add_argument("--min-score", type=int, default=55,
                    help="minimum entry_score (default: 55)")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}")
        print("Run 'python src/stock_screener.py' first.")
        return 1

    with open(args.input) as f:
        results = json.load(f)

    allowed = {r.upper() for r in args.ratings}
    picked = [
        r for r in results
        if r.get("rating", "").upper() in allowed
        and (r.get("entry_score") or 0) >= args.min_score
    ]

    watchlist = [
        {"ticker": r["ticker"], "name": r["name"], "config": config_for(r.get("sector"))}
        for r in picked
    ]

    # De-duplicate by ticker, keeping the first (highest score, results are sorted).
    seen = set()
    unique = []
    for item in watchlist:
        if item["ticker"] in seen:
            continue
        seen.add(item["ticker"])
        unique.append(item)
    watchlist = unique

    with open(args.output, "w") as f:
        json.dump(watchlist, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(watchlist)} symbols to {args.output}")
    for item in watchlist[:10]:
        print(f"  {item['ticker']:<6} {item['name']:<28} {item['config']}")
    if len(watchlist) > 10:
        print(f"  ... and {len(watchlist) - 10} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())

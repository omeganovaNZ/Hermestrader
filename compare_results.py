import json, os, shutil

prev_path = r"C:\Users\Omega\Repo\Hermes Trader\screener_results_prev.json"
curr_path = r"C:\Users\Omega\Repo\Hermes Trader\screener_results.json"

with open(curr_path) as f:
    curr = json.load(f)

if os.path.exists(prev_path):
    with open(prev_path) as f:
        prev = json.load(f)
    prev_scores = {r['ticker']: r for r in prev['results']}
    curr_scores = {r['ticker']: r for r in curr['results']}
    new_tickers = set(curr_scores.keys()) - set(prev_scores.keys())
    changes = []
    for ticker in curr_scores:
        if ticker in prev_scores:
            old_rating = prev_scores[ticker]['rating']
            new_rating = curr_scores[ticker]['rating']
            if old_rating != new_rating:
                changes.append({
                    'ticker': ticker,
                    'old': old_rating,
                    'new': new_rating,
                    'old_score': prev_scores[ticker]['score'],
                    'new_score': curr_scores[ticker]['score']
                })
    print("=== NEW CANDIDATES ===")
    for t in sorted(new_tickers):
        r = curr_scores[t]
        print(f"  {t}: Score {r['score']} — {r['rating']}")
    print("\n=== RATING CHANGES ===")
    for c in changes:
        print(f"  {c['ticker']}: {c['old']} ({c['old_score']}) -> {c['new']} ({c['new_score']})")
    if not new_tickers:
        print("  (none)")
    if not changes:
        print("  (none)")
else:
    print("No previous results file found — first run.")
    print("All candidates are 'new' by definition.")

shutil.copy(curr_path, prev_path)
print(f"\nBaseline saved to {prev_path}")

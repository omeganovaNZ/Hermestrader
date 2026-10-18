"""Focused verification of the two ensemble fixes (sentiment source, ML training)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys

from src.ensemble_trader import SentimentFilter, LightGBMPredictor

print("=== SENTIMENT LAYER (was: always NEUTRAL 0.5) ===")
sf = SentimentFilter()
for t in ("XOM", "GEV", "MU"):
    r = sf.get_sentiment(t, t)
    print(f"  {t:4} score={r['score']:.3f}  sentiment={r['sentiment']:9} "
          f"available={r.get('available')}  source={r.get('source')}  "
          f"(+{r['positive_mentions']}/-{r['negative_mentions']} keyword hits)")

print()
print("=== ML LAYER (was: model never trained -> predict() None -> 0.5) ===")
mp = LightGBMPredictor()
for t in ("XOM", "GEV"):
    ok = mp.train(t, "2y")
    p = mp.predict(t)
    print(f"  {t:4} train={ok}  predict={'None (still broken)' if p is None else f'{p:.4f}'}")

print()
print("=== verdict ===")
ok_sent = any(sf.get_sentiment(t, t).get("available") for t in ("XOM", "GEV"))
mp2 = LightGBMPredictor()
ok_ml = mp2.train("XOM", "2y") and mp2.predict("XOM") is not None
print(f"  sentiment produces real scores : {ok_sent}")
print(f"  ML produces real probabilities : {ok_ml}")
sys.exit(0 if (ok_sent and ok_ml) else 1)

"""
ML Ensemble Trading System
Combines: LightGBM prediction + meta-labeling + sentiment filter + volatility targeting
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.alpaca_trader import AlpacaTrader
from src.market_aware_strategy import MarketAwareHybridStrategy, MARKET_CONFIGS
from src.trading_strategy_engine import fetch_data


class LightGBMPredictor:
    """LightGBM classifier for 5-day forward return prediction."""
    
    def __init__(self):
        self.model = None
        self.feature_columns = [
            'return_1d', 'return_3d', 'return_5d',
            'vol_ratio', 'volume_ratio', 'dist_ma21', 'dist_ma63',
            'rsi', 'bb_pct', 'adx'
        ]
    
    def _calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate features for ML model."""
        df = df.copy()
        
        # Returns
        df['return_1d'] = df['Close'].pct_change(1)
        df['return_3d'] = df['Close'].pct_change(3)
        df['return_5d'] = df['Close'].pct_change(5)
        
        # Volatility ratio
        df['vol_ratio'] = df['Close'].pct_change().rolling(5).std() / df['Close'].pct_change().rolling(20).std()
        
        # Volume ratio
        df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
        
        # Distance from moving averages
        df['dist_ma21'] = (df['Close'] / df['Close'].rolling(21).mean()) - 1
        df['dist_ma63'] = (df['Close'] / df['Close'].rolling(63).mean()) - 1
        
        # RSI (guard against division by zero when loss == 0)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(100.0)  # no down days → RSI 100
        
        # Bollinger Band %B (guard against division by zero when std == 0)
        df['bb_middle'] = df['Close'].rolling(20).mean()
        df['bb_std'] = df['Close'].rolling(20).std()
        bb_denom = 4 * df['bb_std']
        df['bb_pct'] = (df['Close'] - (df['bb_middle'] - 2 * df['bb_std'])) / bb_denom.replace(0, np.nan)
        df['bb_pct'] = df['bb_pct'].fillna(0.5)  # flat prices → 0.5
        
        # ADX (simplified, with division-by-zero guards)
        plus_dm = df['High'].diff()
        minus_dm = -df['Low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        tr = pd.concat([df['High'] - df['Low'], abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr_safe = atr.replace(0, np.nan)
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_safe)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_safe)
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = 100 * abs(plus_di - minus_di) / di_sum
        df['adx'] = dx.rolling(14).mean()
        df['adx'] = df['adx'].fillna(0.0)  # no movement → ADX 0
        
        return df
    
    def train(self, ticker: str, period: str = "2y") -> bool:
        """Train LightGBM model on historical data."""
        try:
            import lightgbm as lgb
            
            data = fetch_data(ticker, period)
            if data is None or len(data) < 250:
                return False
            
            df = self._calculate_features(data)
            df['target'] = (df['Close'].shift(-5) > df['Close']).astype(int)
            
            # Remove NaN rows
            df = df.dropna()
            
            if len(df) < 100:
                return False
            
            X = df[self.feature_columns].values
            y = df['target'].values
            
            # Walk-forward validation: train on first 70%, test on last 30%
            split = int(len(X) * 0.7)
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            
            self.model = lgb.LGBMClassifier(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.8,
                colsample_bytree=0.8,
                verbose=-1,
            )
            self.model.fit(X_train, y_train)
            
            return True
            
        except Exception as e:
            print(f"  Training failed: {e}")
            return False
    
    def predict(self, ticker: str) -> Optional[float]:
        """Predict probability of positive 5-day return."""
        if self.model is None:
            return None
        
        try:
            data = fetch_data(ticker, "6mo")  # yfinance rejects "6m"
            if data is None or len(data) < 50:
                return None
            
            df = self._calculate_features(data)
            df = df.dropna()
            
            if len(df) == 0:
                return None
            
            X = df[self.feature_columns].values[-1:]
            prob = self.model.predict_proba(X)[0][1]
            return float(prob)
            
        except Exception as e:
            return None


class SentimentFilter:
    """Web-based sentiment scoring (proxy for FinBERT)."""
    
    POSITIVE_KEYWORDS = [
        'beat', 'surge', 'soar', 'jump', 'rally', 'upgrade', 'strong', 'growth',
        'record', 'partnership', 'launch', 'approval', 'expansion', 'profit',
        'bullish', 'outperform', 'buy', 'raise', 'boost', 'gain'
    ]
    
    NEGATIVE_KEYWORDS = [
        'miss', 'plunge', 'tumble', 'crash', 'downgrade', 'weak', 'loss',
        'decline', 'concern', 'investigation', 'layoff', 'cut', 'bearish',
        'underperform', 'sell', 'lower', 'drop', 'fall', 'warning'
    ]
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
    
    def _fetch_headlines(self, ticker: str, name: str) -> Tuple[list, str]:
        """Return (headlines, source). hermes_tools resolves only inside execute_code,
        so a plain terminal/cron run falls back to Google News RSS (no API key needed)."""
        try:
            from hermes_tools import web_search
            res = web_search(f"{name} {ticker} stock news", limit=5)
            arts = res.get("data", {}).get("web", [])
            if arts:
                return [f"{a.get('title', '')} {a.get('description', '')}" for a in arts], "hermes_tools"
        except Exception:
            pass

        try:
            import urllib.parse
            import urllib.request
            import xml.etree.ElementTree as ET
            query = urllib.parse.quote(f"{name} {ticker} stock")
            url = (f"https://news.google.com/rss/search?q={query}"
                   f"&hl=en-US&gl=US&ceid=US:en")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                root = ET.fromstring(resp.read())
            titles = [(item.findtext("title") or "") for item in root.findall(".//item")]
            if titles:
                return titles, "google_news_rss"
        except Exception:
            pass

        return [], "unavailable"

    def get_sentiment(self, ticker: str, name: str) -> Dict:
        """Get sentiment score for a stock."""
        # Check cache (refresh every 4 hours)
        now = datetime.now()
        if ticker in self.cache:
            if (now - self.cache_time[ticker]).total_seconds() < 14400:
                return self.cache[ticker]
        
        try:
            # hermes_tools resolves only inside execute_code, so fall back to Google
            # News RSS to keep this layer working in a plain terminal/cron process.
            articles, source = self._fetch_headlines(ticker, name)
            
            positive_count = 0
            negative_count = 0
            total_articles = 0
            
            for article in articles:
                text = article.lower()
                pos = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
                neg = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
                positive_count += pos
                negative_count += neg
                total_articles += 1
            
            if total_articles == 0:
                sentiment = "NEUTRAL"
                score = 0.5
            else:
                score = positive_count / (positive_count + negative_count + 1)
                if positive_count == 0 and negative_count == 0:
                    # No keyword matches — not negative, just no signal
                    sentiment = "NEUTRAL"
                    score = 0.5
                elif score > 0.6:
                    sentiment = "POSITIVE"
                elif score < 0.4:
                    sentiment = "NEGATIVE"
                else:
                    sentiment = "NEUTRAL"
            
            result = {
                'ticker': ticker,
                'sentiment': sentiment,
                'score': score,
                'positive_mentions': positive_count,
                'negative_mentions': negative_count,
                'available': total_articles > 0,
                'source': source,
            }
            
            self.cache[ticker] = result
            self.cache_time[ticker] = now
            return result
            
        except ImportError:
            # hermes_tools not available in terminal - use neutral sentiment
            return {
                'ticker': ticker,
                'sentiment': 'NEUTRAL',
                'score': 0.5,
                'positive_mentions': 0,
                'negative_mentions': 0,
                'available': False,
                'source': 'unavailable',
            }
        except Exception as e:
            return {
                'ticker': ticker,
                'sentiment': 'NEUTRAL',
                'score': 0.5,
                'positive_mentions': 0,
                'negative_mentions': 0,
                'available': False,
                'source': 'unavailable',
            }





class EnsembleTrader:
    """Combines all signals: technical + ML + sentiment + volatility targeting."""
    
    def __init__(self):
        self.alpaca = AlpacaTrader()
        self.ml_predictor = LightGBMPredictor()
        self._ml_trained = {}          # symbol -> bool; train once per run
        self._ml_models = {}           # symbol -> trained model; per-symbol cache
        self.sentiment_filter = SentimentFilter()

        
        # Signal weights (from research)
        self.MIN_LIVE_LAYERS = 3   # refuse to act on fewer live signal layers than this
        self.signal_weights = {
            'technical': 0.30,    # ADX + Bollinger
            'ml_prediction': 0.25, # LightGBM
            'sentiment': 0.20,    # News sentiment
            'momentum': 0.15,     # 12-month return
            'volatility': 0.10,   # Low vol preference
        }
    
    def generate_ensemble_signal(self, symbol: str, config_name: str, name: str = None) -> Dict:
        """Generate ensemble signal combining all methods."""
        
        signals = {}
        
        # 1. Technical signal (Round-4 regime-aware ADX + Bollinger)
        try:
            data = fetch_data(symbol, "6mo")
            if data is not None and len(data) > 50:
                config = MARKET_CONFIGS.get(config_name, MARKET_CONFIGS["US_TECH"])
                strategy = MarketAwareHybridStrategy(config)
                signals_df = strategy.generate_signals(data)
                # Use the signal from 2 bars ago to avoid look-ahead bias
                # (the strategy's signal at bar i uses data up to bar i)
                latest_signal = int(signals_df['signal'].iloc[-2]) if len(signals_df) >= 2 else int(signals_df['signal'].iloc[-1])
                regime = signals_df['regime'].iloc[-1]
                signals['technical'] = latest_signal
                signals['regime'] = regime
                # Round-4: expose regime for veto/override logic
                signals['adx'] = float(signals_df['adx'].iloc[-1]) if not pd.isna(signals_df['adx'].iloc[-1]) else 0.0
            else:
                signals['technical'] = 0
                signals['regime'] = 'unknown'
                signals['adx'] = 0.0
        except Exception:
            signals['technical'] = 0
            signals['regime'] = 'unknown'
            signals['adx'] = 0.0
        
        # 2. ML prediction - train on demand. Per-symbol model cache: training symbol B
        # must NOT overwrite symbol A's model. Each symbol gets its own trained model.
        if symbol not in self._ml_trained:
            try:
                predictor = LightGBMPredictor()
                self._ml_trained[symbol] = bool(predictor.train(symbol, "2y"))
                self._ml_models[symbol] = predictor
            except Exception as exc:
                print(f"  ML train failed for {symbol}: {exc}")
                self._ml_trained[symbol] = False
        if self._ml_trained.get(symbol) and symbol in self._ml_models:
            ml_prob = self._ml_models[symbol].predict(symbol)
        else:
            ml_prob = None
        signals['ml_probability'] = ml_prob if ml_prob is not None else 0.5
        signals['ml_available'] = ml_prob is not None
        
        # 3. Sentiment
        sentiment = self.sentiment_filter.get_sentiment(symbol, name or symbol)
        signals['sentiment_score'] = sentiment['score']
        signals['sentiment'] = sentiment['sentiment']
        signals['sentiment_available'] = sentiment.get('available', False)
        signals['sentiment_source'] = sentiment.get('source', 'unknown')
        
        # 4. Momentum (12-month return)
        signals['momentum_available'] = False
        try:
            data = fetch_data(symbol, "1y")
            if data is not None and len(data) > 0:
                first_close = data['Close'].iloc[0]
                if first_close > 0 and first_close == first_close:  # not NaN
                    momentum = (data['Close'].iloc[-1] / first_close) - 1
                    signals['momentum'] = momentum
                    signals['momentum_available'] = True
                else:
                    signals['momentum'] = 0
            else:
                signals['momentum'] = 0
        except Exception:
            signals['momentum'] = 0

        # 5. Volatility
        signals['vol_available'] = False
        try:
            data = fetch_data(symbol, "6mo")
            if data is not None and len(data) > 20:
                daily_returns = data['Close'].pct_change().dropna()
                vol = daily_returns.std() * np.sqrt(252)
                # Guard against NaN (empty daily_returns after dropna)
                if vol == vol and vol > 0:  # not NaN and positive
                    signals['volatility'] = vol
                    signals['vol_available'] = True
                else:
                    signals['volatility'] = 0.25  # fallback: neutral (maps to vol_score=0)
            else:
                signals['volatility'] = 0.25  # fallback: neutral (maps to vol_score=0)
        except Exception:
            signals['volatility'] = 0.25  # fallback: neutral (maps to vol_score=0)
        
        # Calculate ensemble score
        ensemble_score = 0
        
        # Technical contribution
        if signals['technical'] == 1:
            ensemble_score += self.signal_weights['technical'] * 1.0
        elif signals['technical'] == -1:
            ensemble_score += self.signal_weights['technical'] * -1.0
        
        # ML contribution
        ensemble_score += self.signal_weights['ml_prediction'] * (signals['ml_probability'] - 0.5) * 2
        
        # Sentiment as binary veto (Round-4): only veto when strongly negative,
        # not a linear contributor. A missing/neutral sentiment adds nothing.
        sentiment_veto = False
        if signals.get('sentiment_available', False) and signals['sentiment_score'] < 0.3:
            sentiment_veto = True
        
        # Momentum contribution
        ensemble_score += self.signal_weights['momentum'] * np.sign(signals['momentum']) * min(abs(signals['momentum']), 1.0)
        
        # Volatility contribution (prefer lower vol). Centred on zero so the term is
        # symmetric like every other layer. As originally written it ranged 0..1 and so
        # always added a POSITIVE amount, giving every score a permanent long bias - once
        # renormalised that produced STRONG_BUY for 8 of 11 names, which is a bias, not a
        # signal.
        vol_score = 1.0 - 2.0 * min(signals['volatility'] / 0.5, 1.0)
        ensemble_score += self.signal_weights['volatility'] * vol_score
        
        # A layer that produced only its neutral placeholder contributed 0 to the numerator
        # while still counting in the denominator, silently diluting the score toward zero.
        # Renormalise over the layers that actually produced a value so the score is an
        # unbiased estimate on the original scale.
        # A layer is "live" only if it produced a real value, not a fallback.
        # Volatility uses 0.25 as a fallback (maps to vol_score=0, neutral), so
        # check if the computed vol is the fallback value.
        _vol_is_fallback = not signals.get('vol_available', False)
        # Sentiment is a veto, not a contributing layer — exclude from live weight
        _live = {
            'technical': signals['technical'] != 0,
            'ml_prediction': signals.get('ml_available', False),
            'momentum': signals.get('momentum_available', False),
            'volatility': not _vol_is_fallback,
        }
        signals['layers_used'] = sorted(layer for layer, ok in _live.items() if ok)
        _live_weight = sum(w for k, w in self.signal_weights.items() if _live.get(k))
        signals['layers_live_weight'] = round(_live_weight, 3)
        if _live_weight > 0:
            ensemble_score = ensemble_score / _live_weight
        signals['ensemble_score'] = ensemble_score

        # Round-4 trend-strength override: don't SELL when 12m momentum > +50% AND
        # price > 200-day MA. This prevents premature exits in strong trends.
        trend_override = False
        try:
            data = fetch_data(symbol, "1y")
            if data is not None and len(data) > 200:
                ma200 = data['Close'].rolling(200).mean().iloc[-1]
                mom_12m = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
                if mom_12m > 0.50 and data['Close'].iloc[-1] > ma200:
                    trend_override = True
                    signals['trend_override'] = True
        except Exception:
            pass
        if not trend_override:
            signals['trend_override'] = False
        
        # Final decision. Require a minimum number of live layers before acting: the standing
        # rule is to act only on multiple independent confirming signals, so a score built
        # from one or two layers must not produce a trade.
        if ensemble_score != ensemble_score or ensemble_score in (float('inf'), float('-inf')):
            # NaN or Inf score: a component returned a bad value. Without this the threshold
            # comparisons all evaluate False and every name silently becomes HOLD, which is
            # indistinguishable from a genuine no-signal.
            signals['decision'] = 'HOLD'
            signals['decision_note'] = 'held - ensemble score is invalid (NaN or Inf); a signal component is broken'
        elif len(signals['layers_used']) < self.MIN_LIVE_LAYERS:
            signals['decision'] = 'HOLD'
            signals['decision_note'] = (
                f"held - only {len(signals['layers_used'])} live layer(s), "
                f"need {self.MIN_LIVE_LAYERS}")
        elif sentiment_veto:
            signals['decision'] = 'HOLD'
            signals['decision_note'] = 'vetoed - strongly negative sentiment'
        elif signals.get('trend_override', False) and ensemble_score < -0.1:
            signals['decision'] = 'HOLD'
            signals['decision_note'] = 'held - trend-strength override (strong uptrend, no sells)'
        elif ensemble_score > 0.3:
            signals['decision'] = 'STRONG_BUY'
        elif ensemble_score > 0.1:
            signals['decision'] = 'BUY'
        elif ensemble_score < -0.3:
            signals['decision'] = 'STRONG_SELL'
        elif ensemble_score < -0.1:
            signals['decision'] = 'SELL'
        else:
            signals['decision'] = 'HOLD'
        
        return signals
    
    def run_ensemble_scan(self):
        """Run ensemble scan on all watched stocks."""
        print("=" * 80)
        print("  ENSEMBLE TRADING SYSTEM — Daily Scan")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("  Signals: Technical(30%) + ML(25%) + Sentiment(20%) + Momentum(15%) + Volatility(10%)")
        print("=" * 80)
        
        account = self.alpaca.get_account()
        print(f"\n  Cash: ${account['cash']:,.2f} | Portfolio Value: ${account['portfolio_value']:,.2f}")
        
        print(f"\n{'─'*80}")
        print(f"  ENSEMBLE SIGNALS")
        print(f"{'─'*80}")
        
        results = []
        for ticker, name, config_name in self.alpaca.watchlist:
            try:
                signals = self.generate_ensemble_signal(ticker, config_name, name)
                signals['ticker'] = ticker
                signals['name'] = name
                results.append(signals)
                
                decision = signals.get('decision', 'HOLD')
                score = signals.get('ensemble_score', 0)
                ml_prob = signals.get('ml_probability', 0.5)
                sentiment = signals.get('sentiment', 'NEUTRAL')
                regime = signals.get('regime', 'unknown')
                
                print(f"\n  {name} ({ticker})")
                print(f"    Decision: {decision} (score: {score:+.3f})")
                print(f"    Regime: {regime} | ML prob: {ml_prob:.2f} | Sentiment: {sentiment}")
                
            except Exception as e:
                print(f"\n  {name} ({ticker}): Error - {e}")
        
        # Summary
        print(f"\n{'─'*80}")
        print(f"  SUMMARY")
        print(f"{'─'*80}")
        
        strong_buys = [r for r in results if r.get('decision') == 'STRONG_BUY']
        buys = [r for r in results if r.get('decision') == 'BUY']
        holds = [r for r in results if r.get('decision') == 'HOLD']
        sells = [r for r in results if r.get('decision') == 'SELL']
        strong_sells = [r for r in results if r.get('decision') == 'STRONG_SELL']
        
        print(f"\n  STRONG BUY: {len(strong_buys)}")
        for r in strong_buys:
            print(f"    {r['name']} ({r['ticker']})")
        
        print(f"\n  BUY: {len(buys)}")
        for r in buys:
            print(f"    {r['name']} ({r['ticker']})")
        
        print(f"\n  HOLD: {len(holds)}")
        for r in holds:
            print(f"    {r['name']} ({r['ticker']})")
        
        print(f"\n  SELL: {len(sells)}")
        for r in sells:
            print(f"    {r['name']} ({r['ticker']})")
        
        print(f"\n  STRONG SELL: {len(strong_sells)}")
        for r in strong_sells:
            print(f"    {r['name']} ({r['ticker']})")
        
        print("=" * 80)
        
        return results


def main():
    """Run the ensemble trading system."""
    trader = EnsembleTrader()
    results = trader.run_ensemble_scan()
    
    # Save results
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ensemble_signals.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to: {output_path}")


if __name__ == "__main__":
    main()

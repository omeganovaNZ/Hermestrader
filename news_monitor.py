"""
News-Aware Trading Module
Scans world news for events that could impact watched stocks.
Logs events and suggests strategy adjustments.

Limitations:
- Reactive, not real-time (minutes to hours delay)
- Cannot predict market direction from news
- Best for scheduled events (earnings, product launches) and unfolding geopolitics
"""

import json
import os
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from hermes_tools import web_search

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class NewsEvent:
    date: datetime
    headline: str
    source: str
    tickers_affected: List[str]
    impact: str  # "high", "medium", "low"
    category: str  # "earnings", "geopolitical", "product", "regulatory", "macro", "other"
    summary: str
    suggested_action: str  # "hold", "pause_trading", "reduce_position", "investigate"
    url: str = ""


class NewsMonitor:
    """
    Monitors news for watched stocks and flags significant events.
    Uses web search to find recent news articles.
    """
    
    # Keywords that suggest high-impact events
    HIGH_IMPACT_KEYWORDS = [
        "earnings", "profit warning", "revenue miss", "revenue beat",
        "fda approval", "fda rejection", "recall", "lawsuit", "settlement",
        "merger", "acquisition", "takeover", "buyout",
        "tariff", "sanctions", "export ban", "trade war",
        "ceo resign", "ceo fired", "cfo", "restructuring", "bankruptcy",
        "stock split", "dividend", "buyback", "offering",
        "guidance raised", "guidance lowered", "outlook",
        "investigation", "sec", "doj", "antitrust",
        "data breach", "cyberattack", "hack",
        "production cut", "supply shortage", "chip shortage",
        "ai breakthrough", "partnership", "contract win",
        "downgrade", "upgrade", "price target",
        "trump", "white house", "federal reserve", "interest rate",
        "election", "referendum", "brexit", "war", "conflict",
    ]
    
    CATEGORY_KEYWORDS = {
        "earnings": ["earnings", "revenue", "profit", "eps", "guidance", "outlook", "q1", "q2", "q3", "q4", "quarterly"],
        "geopolitical": ["tariff", "sanctions", "war", "conflict", "trump", "white house", "election", "trade", "brexit", "china", "russia"],
        "product": ["launch", "release", "product", "iphone", "chip", "gpu", "ai", "partnership", "contract"],
        "regulatory": ["sec", "fda", "doj", "antitrust", "investigation", "regulation", "ban", "approval"],
        "macro": ["federal reserve", "interest rate", "inflation", "gdp", "unemployment", "recession", "market"],
        "corporate": ["ceo", "cfo", "merger", "acquisition", "restructuring", "bankruptcy", "layoff", "dividend", "buyback"],
    }
    
    def __init__(self, watchlist: Dict[str, str]):
        """
        watchlist: dict of {ticker: company_name}
        e.g., {"NVDA": "NVIDIA", "RKLB": "Rocket Lab"}
        """
        self.watchlist = watchlist
        self.events_log: List[NewsEvent] = []
    
    def _classify_category(self, text: str) -> str:
        """Classify news article into category."""
        text_lower = text.lower()
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return category
        return "other"
    
    def _assess_impact(self, text: str, category: str) -> str:
        """Assess potential impact level."""
        text_lower = text.lower()
        high_count = sum(1 for kw in self.HIGH_IMPACT_KEYWORDS if kw in text_lower)
        
        if category in ["earnings", "geopolitical", "regulatory"]:
            if high_count >= 2:
                return "high"
            elif high_count >= 1:
                return "medium"
        
        if high_count >= 3:
            return "high"
        elif high_count >= 1:
            return "medium"
        
        return "low"
    
    def _suggest_action(self, impact: str, category: str) -> str:
        """Suggest strategy action based on event."""
        if impact == "high":
            if category == "geopolitical":
                return "pause_trading"
            elif category == "earnings":
                return "investigate"
            elif category == "regulatory":
                return "reduce_position"
            else:
                return "pause_trading"
        elif impact == "medium":
            return "investigate"
        return "hold"
    
    def _find_affected_tickers(self, text: str) -> List[str]:
        """Find which watched tickers are mentioned in the text."""
        text_lower = text.lower()
        affected = []
        for ticker, name in self.watchlist.items():
            if ticker.lower() in text_lower or name.lower() in text_lower:
                affected.append(ticker)
        return affected
    
    def scan_news(self, max_articles_per_stock: int = 3) -> List[NewsEvent]:
        """
        Scan news for all watched stocks.
        Returns list of significant events found.
        """
        new_events = []
        seen_urls = set()
        
        # Also scan for macro/geopolitical news that could affect all stocks
        search_queries = [
            "stock market news today",
            "breaking financial news",
            "stock market volatility news today",
        ]
        
        # Add per-stock searches
        for ticker, name in self.watchlist.items():
            search_queries.append(f"{name} {ticker} stock news")
        
        for query in search_queries:
            try:
                results = web_search(query, limit=5)
                articles = results.get("data", {}).get("web", [])
                
                for article in articles:
                    url = article.get("url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    
                    title = article.get("title", "")
                    description = article.get("description", "")
                    content = f"{title} {description}"
                    
                    # Find affected tickers
                    affected = self._find_affected_tickers(content)
                    
                    # If it's a macro news query and no specific tickers found, 
                    # flag as potentially market-wide
                    if not affected and "stock market" in query.lower():
                        affected = list(self.watchlist.keys())  # Could affect all
                    
                    if not affected:
                        continue
                    
                    # Classify and assess
                    category = self._classify_category(content)
                    impact = self._assess_impact(content, category)
                    
                    # Only log medium and high impact events
                    if impact in ["medium", "high"]:
                        event = NewsEvent(
                            date=datetime.now(),
                            headline=title,
                            source=article.get("source", "Unknown"),
                            tickers_affected=affected,
                            impact=impact,
                            category=category,
                            summary=description[:500],
                            suggested_action=self._suggest_action(impact, category),
                            url=url
                        )
                        new_events.append(event)
                        self.events_log.append(event)
                        
            except Exception as e:
                print(f"  Error scanning '{query}': {e}")
        
        return new_events
    
    def get_active_alerts(self, hours: int = 24) -> List[NewsEvent]:
        """Get events from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [e for e in self.events_log if e.date > cutoff]
    
    def get_summary(self) -> str:
        """Get a text summary of recent events."""
        if not self.events_log:
            return "No events logged yet."
        
        lines = ["\n" + "=" * 70]
        lines.append("  NEWS MONITOR SUMMARY")
        lines.append("=" * 70)
        
        # Group by impact
        high = [e for e in self.events_log if e.impact == "high"]
        medium = [e for e in self.events_log if e.impact == "medium"]
        low = [e for e in self.events_log if e.impact == "low"]
        
        lines.append(f"\n  Total Events: {len(self.events_log)}")
        lines.append(f"    High Impact:   {len(high)}")
        lines.append(f"    Medium Impact: {len(medium)}")
        lines.append(f"    Low Impact:    {len(low)}")
        
        if high:
            lines.append(f"\n  HIGH IMPACT EVENTS:")
            for e in high[-5:]:  # Last 5
                lines.append(f"    [{e.date.strftime('%Y-%m-%d %H:%M')}] {e.headline}")
                lines.append(f"      Affected: {', '.join(e.tickers_affected)}")
                lines.append(f"      Category: {e.category} | Action: {e.suggested_action}")
                lines.append("")
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def save_log(self, filepath: str = None):
        """Save events log to JSON."""
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_events_log.json")
        
        data = []
        for e in self.events_log:
            data.append({
                "date": e.date.isoformat(),
                "headline": e.headline,
                "source": e.source,
                "tickers_affected": e.tickers_affected,
                "impact": e.impact,
                "category": e.category,
                "summary": e.summary,
                "suggested_action": e.suggested_action,
                "url": e.url,
            })
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Events log saved to: {filepath}")


def main():
    """Run news scan on watched stocks."""
    
    # Watchlist: ticker -> company name
    watchlist = {
        "RKLB": "Rocket Lab",
        "NVDA": "NVIDIA",
        "MU": "Micron",
        "AMD": "AMD",
        "INTC": "Intel",
        "GOOGL": "Alphabet",
    }
    
    # Samsung is Korean, search separately
    # "005930.KS": "Samsung Electronics",
    
    monitor = NewsMonitor(watchlist)
    
    print("=" * 70)
    print("  NEWS-AWARE TRADING MODULE")
    print("  Scanning for significant events affecting watched stocks...")
    print("=" * 70)
    
    events = monitor.scan_news()
    
    print(f"\nFound {len(events)} significant events:\n")
    
    for e in events:
        print(f"  [{e.impact.upper()}] {e.headline}")
        print(f"    Tickers: {', '.join(e.tickers_affected)}")
        print(f"    Category: {e.category} | Suggested: {e.suggested_action}")
        print(f"    URL: {e.url}")
        print()
    
    print(monitor.get_summary())
    monitor.save_log()
    
    # Print strategy recommendations
    high_impact_tickers = set()
    for e in events:
        if e.impact == "high":
            high_impact_tickers.update(e.tickers_affected)
    
    if high_impact_tickers:
        print(f"\n  STRATEGY RECOMMENDATIONS:")
        print(f"  ⚠️  High-impact news detected for: {', '.join(high_impact_tickers)}")
        print(f"     Consider pausing new trades on these stocks until news stabilizes.")
        print(f"     Review existing positions for potential exposure.")


if __name__ == "__main__":
    main()

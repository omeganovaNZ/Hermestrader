"""
Index Constituents — Fetches and caches S&P 500 and Nasdaq-100 constituents.
Uses urllib (stdlib) and regex parsing — no external dependencies.
"""

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta
from typing import List, Tuple

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "index_constituents.json",
)
CACHE_TTL_DAYS = 7

# Wikipedia URLs
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Regex patterns
TABLE_PATTERN = re.compile(
    r'<table[^>]*class="[^"]*wikitable[^"]*sortable[^"]*"[^>]*>(.*?)</table>',
    re.DOTALL,
)
FALLBACK_TABLE_PATTERN = re.compile(
    r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
    re.DOTALL,
)
ROW_PATTERN = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
CELL_PATTERN = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
TAG_PATTERN = re.compile(r'<[^>]+>')
REF_PATTERN = re.compile(r'\[\d+\]')
TICKER_PATTERN = re.compile(r'^[A-Z0-9.\-]{1,10}$')


def _fetch_html(url: str) -> str:
    """Fetch HTML content from a URL."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; HermesTrader/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    """Remove HTML tags, references, and extra whitespace."""
    text = TAG_PATTERN.sub("", text)
    text = REF_PATTERN.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_table_rows(html: str) -> list:
    """Extract rows from the first sortable wikitable in the HTML."""
    table_match = TABLE_PATTERN.search(html)
    if not table_match:
        table_match = FALLBACK_TABLE_PATTERN.search(html)
    if not table_match:
        return []
    table_html = table_match.group(1)
    return ROW_PATTERN.findall(table_html)


def _extract_cells(row_html: str) -> list:
    """Extract <td> cell contents from a table row."""
    return CELL_PATTERN.findall(row_html)


def _parse_constituents_table(rows: list) -> list:
    """Parse constituents from table rows.

    Returns list of (ticker, name, sector) tuples.
    Assumes first column is ticker, second is name, third is sector.
    """
    constituents = []
    for row in rows:
        cells = _extract_cells(row)
        if len(cells) < 2:
            continue
        ticker = _clean_text(cells[0])
        name = _clean_text(cells[1])
        if not TICKER_PATTERN.match(ticker):
            continue
        sector = _clean_text(cells[2]) if len(cells) > 2 else "Unknown"
        constituents.append((ticker, name, sector))
    return constituents


def _fetch_sp500() -> list:
    """Fetch and parse S&P 500 constituents."""
    html = _fetch_html(SP500_URL)
    rows = _extract_table_rows(html)
    return _parse_constituents_table(rows[1:])


def _fetch_nasdaq100() -> list:
    """Fetch and parse Nasdaq-100 constituents."""
    html = _fetch_html(NASDAQ100_URL)
    rows = _extract_table_rows(html)
    return _parse_constituents_table(rows[1:])


def _save_cache(constituents: list) -> None:
    """Save constituents to cache file."""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "count": len(constituents),
        "constituents": [[t, n, s] for t, n, s in constituents],
    }
    with open(CACHE_PATH, "w") as f:
        json.dump(cache_data, f, indent=2)


def _load_cache() -> list:
    """Load constituents from cache file."""
    with open(CACHE_PATH, "r") as f:
        cache_data = json.load(f)
    return [(t, n, s) for t, n, s in cache_data["constituents"]]


def _is_cache_fresh() -> bool:
    """Check if cache file exists and is less than CACHE_TTL_DAYS old."""
    if not os.path.exists(CACHE_PATH):
        return False
    cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(CACHE_PATH))
    return cache_age < timedelta(days=CACHE_TTL_DAYS)


def load_constituents() -> List[Tuple[str, str, str]]:
    """Load S&P 500 + Nasdaq-100 constituents.

    Returns list of (ticker, name, sector) tuples.
    Uses cached data if fresh (< 7 days old), otherwise re-fetches.
    Returns empty list on error.
    """
    # Try cache first
    if _is_cache_fresh():
        try:
            return _load_cache()
        except (json.JSONDecodeError, KeyError, IOError):
            pass  # Cache corrupted, re-fetch

    # Fetch fresh data
    try:
        sp500 = _fetch_sp500()
        nasdaq100 = _fetch_nasdaq100()

        # Combine and deduplicate by ticker
        seen = set()
        combined = []
        for ticker, name, sector in sp500 + nasdaq100:
            if ticker not in seen:
                seen.add(ticker)
                combined.append((ticker, name, sector))

        # Sort by ticker
        combined.sort(key=lambda x: x[0])

        # Save to cache
        _save_cache(combined)

        return combined
    except Exception as e:
        print(f"Error fetching constituents: {e}")
        # Try to load stale cache as fallback
        if os.path.exists(CACHE_PATH):
            try:
                return _load_cache()
            except Exception:
                pass
        return []


if __name__ == "__main__":
    constituents = load_constituents()
    print(f"Loaded {len(constituents)} constituents")
    for ticker, name, sector in constituents[:10]:
        print(f"  {ticker}: {name} ({sector})")

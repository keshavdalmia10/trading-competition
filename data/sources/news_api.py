"""NewsAPI wrapper for headline retrieval."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from config.settings import CACHE_DIR, CACHE_TTL_HOURS, NEWSAPI_KEY


def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(" ", "_")
    return Path(CACHE_DIR) / f"news_{safe_key}.json"


def _read_cache(key: str) -> Optional[Any]:
    path = _cache_path(key)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
    if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
        return None
    return data.get("payload")


def _write_cache(key: str, payload: Any) -> None:
    path = _cache_path(key)
    data = {"_cached_at": datetime.now().isoformat(), "payload": payload}
    path.write_text(json.dumps(data, default=str))


def get_headlines(query: str, days_back: int = 7, page_size: int = 20) -> list[dict[str, Any]]:
    """Fetch recent news headlines for a query (company name or ticker)."""
    cache_key = f"headlines_{query}_{days_back}d"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — returning empty headlines")
        return []

    try:
        from newsapi import NewsApiClient
        newsapi = NewsApiClient(api_key=NEWSAPI_KEY)

        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        response = newsapi.get_everything(
            q=query,
            from_param=from_date,
            to=to_date,
            language="en",
            sort_by="relevancy",
            page_size=page_size,
        )

        articles = []
        for article in response.get("articles", []):
            articles.append({
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "source": article.get("source", {}).get("name", ""),
                "published_at": article.get("publishedAt", ""),
                "url": article.get("url", ""),
            })

        _write_cache(cache_key, articles)
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch headlines for '{query}': {e}")
        return []


def get_market_headlines(page_size: int = 30) -> list[dict[str, Any]]:
    """Fetch general market/economy headlines."""
    return get_headlines("stock market economy", days_back=7, page_size=page_size)

"""Finnhub API wrapper for news, analyst recs, and earnings calendar."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from config.settings import CACHE_DIR, CACHE_TTL_HOURS, FINNHUB_KEY


def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(" ", "_")
    return Path(CACHE_DIR) / f"finnhub_{safe_key}.json"


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


def _get_client():
    if not FINNHUB_KEY:
        logger.warning("FINNHUB_KEY not set")
        return None
    import finnhub
    return finnhub.Client(api_key=FINNHUB_KEY)


def get_company_news(ticker: str, days_back: int = 14) -> list[dict[str, Any]]:
    """Get recent company news from Finnhub."""
    cache_key = f"company_news_{ticker}_{days_back}d"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        news = client.company_news(ticker, _from=from_date, to=to_date)
        result = [
            {
                "headline": n.get("headline", ""),
                "summary": n.get("summary", ""),
                "source": n.get("source", ""),
                "datetime": n.get("datetime", 0),
                "category": n.get("category", ""),
                "url": n.get("url", ""),
            }
            for n in (news or [])[:20]
        ]
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get Finnhub news for {ticker}: {e}")
        return []


def get_analyst_recommendations(ticker: str) -> list[dict[str, Any]]:
    """Get analyst recommendation trends."""
    cache_key = f"analyst_recs_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        recs = client.recommendation_trends(ticker)
        result = [
            {
                "period": r.get("period", ""),
                "strong_buy": r.get("strongBuy", 0),
                "buy": r.get("buy", 0),
                "hold": r.get("hold", 0),
                "sell": r.get("sell", 0),
                "strong_sell": r.get("strongSell", 0),
            }
            for r in (recs or [])[:4]
        ]
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get analyst recs for {ticker}: {e}")
        return []


def get_earnings_calendar(from_date: str, to_date: str) -> list[dict[str, Any]]:
    """Get earnings calendar for a date range."""
    cache_key = f"earnings_cal_{from_date}_{to_date}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        cal = client.earnings_calendar(_from=from_date, to=to_date, symbol="", international=False)
        earnings = cal.get("earningsCalendar", [])
        result = [
            {
                "symbol": e.get("symbol", ""),
                "date": e.get("date", ""),
                "eps_estimate": e.get("epsEstimate"),
                "eps_actual": e.get("epsActual"),
                "revenue_estimate": e.get("revenueEstimate"),
                "revenue_actual": e.get("revenueActual"),
                "hour": e.get("hour", ""),
            }
            for e in earnings
        ]
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get earnings calendar: {e}")
        return []


def get_price_target(ticker: str) -> dict[str, Any]:
    """Get analyst price target consensus."""
    cache_key = f"price_target_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return {}

    try:
        pt = client.price_target(ticker)
        result = {
            "target_high": pt.get("targetHigh"),
            "target_low": pt.get("targetLow"),
            "target_mean": pt.get("targetMean"),
            "target_median": pt.get("targetMedian"),
            "last_updated": pt.get("lastUpdated", ""),
        }
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get price target for {ticker}: {e}")
        return {}

"""FRED API wrapper for macroeconomic data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from config.settings import CACHE_DIR, CACHE_TTL_HOURS, FRED_API_KEY


def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    return Path(CACHE_DIR) / f"fred_{key}.json"


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


def get_series(series_id: str, periods: int = 12) -> list[dict[str, Any]]:
    """Fetch a FRED series (most recent N observations)."""
    cache_key = f"{series_id}_{periods}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — returning empty data")
        return []

    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
        series = fred.get_series(series_id)
        recent = series.dropna().tail(periods)
        result = [
            {"date": str(idx.date()), "value": float(val)}
            for idx, val in recent.items()
        ]
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to fetch FRED series {series_id}: {e}")
        return []


def get_macro_snapshot() -> dict[str, Any]:
    """Get a snapshot of key macro indicators for market regime analysis."""
    indicators = {
        "fed_funds_rate": "FEDFUNDS",
        "yield_curve_10y2y": "T10Y2Y",
        "cpi_yoy": "CPIAUCSL",
        "gdp_growth": "A191RL1Q225SBEA",
        "unemployment": "UNRATE",
        "consumer_sentiment": "UMCSENT",
        "industrial_production": "INDPRO",
    }

    snapshot = {}
    for name, series_id in indicators.items():
        data = get_series(series_id, periods=3)
        if data:
            snapshot[name] = {
                "latest": data[-1]["value"],
                "previous": data[-2]["value"] if len(data) > 1 else None,
                "date": data[-1]["date"],
            }
        else:
            snapshot[name] = {"latest": None, "previous": None, "date": None}

    return snapshot


def get_vix_and_market() -> dict[str, Any]:
    """Get VIX and S&P 500 data from yfinance (supplement to FRED)."""
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        spy = yf.Ticker("SPY")

        vix_hist = vix.history(period="1mo")
        spy_hist = spy.history(period="3mo")

        result = {}
        if not vix_hist.empty:
            result["vix_current"] = float(vix_hist["Close"].iloc[-1])
            result["vix_20d_avg"] = float(vix_hist["Close"].tail(20).mean())
        if not spy_hist.empty:
            result["spy_current"] = float(spy_hist["Close"].iloc[-1])
            spy_returns = spy_hist["Close"].pct_change().dropna()
            result["spy_1m_return"] = float(spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[-22] - 1) if len(spy_hist) >= 22 else None
            result["spy_3m_return"] = float(spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[0] - 1)

        return result
    except Exception as e:
        logger.error(f"Failed to get VIX/market data: {e}")
        return {}

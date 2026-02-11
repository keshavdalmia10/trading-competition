"""Alpha Vantage data source for price history (hybrid: supplements yfinance)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd
from loguru import logger

from config.settings import ALPHA_VANTAGE_KEY, CACHE_DIR, CACHE_TTL_HOURS, PRICE_HISTORY_DAYS

BASE_URL = "https://www.alphavantage.co/query"

# Rate limiting for free tier (25 calls/day, 5 calls/minute)
_last_call_time = 0.0
_RATE_LIMIT_SECONDS = 12.5  # ~5 calls/minute


def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(" ", "_")
    return Path(CACHE_DIR) / f"{safe_key}.json"


def _read_cache(key: str) -> Optional[dict]:
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


def _rate_limited_get(params: dict) -> dict:
    """Make a rate-limited GET request to Alpha Vantage."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < _RATE_LIMIT_SECONDS:
        time.sleep(_RATE_LIMIT_SECONDS - elapsed)

    params["apikey"] = ALPHA_VANTAGE_KEY
    resp = httpx.get(BASE_URL, params=params, timeout=30)
    _last_call_time = time.time()
    resp.raise_for_status()
    data = resp.json()

    # Check for API error messages
    if "Error Message" in data:
        raise ValueError(data["Error Message"])
    if "Note" in data:
        logger.warning(f"Alpha Vantage rate limit note: {data['Note']}")
        raise ValueError("Rate limit reached")

    return data


def get_price_history(ticker: str, days: int = PRICE_HISTORY_DAYS) -> pd.DataFrame:
    """Get daily OHLCV price history from Alpha Vantage.

    Falls back to yfinance if Alpha Vantage key is not set or call fails.
    Returns DataFrame with columns: Open, High, Low, Close, Volume (indexed by Date).
    """
    cache_key = f"av_prices_{ticker}_{days}d"
    cached = _read_cache(cache_key)
    if cached:
        df = pd.DataFrame(cached)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
        return df

    if not ALPHA_VANTAGE_KEY:
        logger.debug(f"No Alpha Vantage key, falling back to yfinance for {ticker}")
        return _yfinance_fallback(ticker, days)

    av_df = None
    try:
        outputsize = "full" if days > 100 else "compact"
        data = _rate_limited_get({
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": outputsize,
        })

        ts_key = "Time Series (Daily)"
        if ts_key not in data:
            logger.warning(f"No time series data for {ticker} from Alpha Vantage")
        else:
            records = []
            cutoff = datetime.now() - timedelta(days=days)
            for date_str, values in data[ts_key].items():
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt >= cutoff:
                    records.append({
                        "Date": date_str,
                        "Open": float(values["1. open"]),
                        "High": float(values["2. high"]),
                        "Low": float(values["3. low"]),
                        "Close": float(values["4. close"]),
                        "Volume": int(values["5. volume"]),
                    })

            if records:
                av_df = pd.DataFrame(records)
                av_df["Date"] = pd.to_datetime(av_df["Date"])
                av_df = av_df.sort_values("Date").set_index("Date")

                # Cache the result
                cache_data = av_df.reset_index().to_dict(orient="list")
                cache_data["Date"] = [str(d) for d in cache_data["Date"]]
                _write_cache(cache_key, cache_data)

                logger.debug(f"Alpha Vantage: {ticker} — {len(av_df)} days of data")

    except Exception as e:
        logger.warning(f"Alpha Vantage API error for {ticker}: {e}")

    if av_df is not None and not av_df.empty:
        return av_df

    # Alpha Vantage had no data — fall back to yfinance
    return _yfinance_fallback(ticker, days)


def _yfinance_fallback(ticker: str, days: int) -> pd.DataFrame:
    """Fall back to yfinance for price history."""
    from data.sources.yahoo_finance import get_price_history as yf_get_price_history
    return yf_get_price_history(ticker, days)

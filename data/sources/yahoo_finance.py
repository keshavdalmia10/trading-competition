"""Yahoo Finance data wrapper using yfinance."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yfinance as yf
from loguru import logger

from config.settings import CACHE_DIR, CACHE_TTL_HOURS, PRICE_HISTORY_DAYS


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


def get_stock_info(ticker: str) -> dict[str, Any]:
    """Get stock info (name, sector, market cap, PE, etc.)."""
    cache_key = f"yf_info_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        result = {
            "ticker": ticker,
            "name": info.get("shortName", info.get("longName", ticker)),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "roe": info.get("returnOnEquity"),
            "fcf": info.get("freeCashflow"),
            "profit_margin": info.get("profitMargins"),
            "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "beta": info.get("beta"),
            "analyst_target": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        }
        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get info for {ticker}: {e}")
        return {"ticker": ticker, "name": ticker, "sector": "Unknown"}


def _normalize_df_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Strip timezone info from DataFrame index to avoid mixed-tz errors."""
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def get_price_history(ticker: str, days: int = PRICE_HISTORY_DAYS) -> pd.DataFrame:
    """Get daily OHLCV price history."""
    cache_key = f"yf_prices_{ticker}_{days}d"

    # Read cache (with timezone handling for pandas 3.0+)
    try:
        cached = _read_cache(cache_key)
        if cached:
            df = pd.DataFrame(cached)
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
                df.set_index("Date", inplace=True)
            return df
    except Exception as e:
        logger.warning(f"Cache read failed for {ticker}: {e}")

    # Primary: yf.Ticker.history()
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        df = _normalize_df_tz(df)
        if not df.empty:
            _cache_prices(cache_key, df)
        return df
    except Exception as e:
        logger.debug(f"t.history() failed for {ticker}: {e}, trying yf.download()")

    # Fallback: yf.download() handles timezones differently
    try:
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
        # yf.download() may return multi-level columns for single ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = _normalize_df_tz(df)
        if not df.empty:
            _cache_prices(cache_key, df)
        return df
    except Exception as e:
        logger.error(f"Failed to get prices for {ticker}: {e}")
        return pd.DataFrame()


def _cache_prices(cache_key: str, df: pd.DataFrame) -> None:
    """Cache price DataFrame with timezone-safe date strings."""
    cache_data = df.reset_index().to_dict(orient="list")
    date_col = "Date" if "Date" in cache_data else None
    if date_col:
        cache_data[date_col] = [str(d) for d in cache_data[date_col]]
    _write_cache(cache_key, cache_data)


def get_financials(ticker: str) -> dict[str, Any]:
    """Get income statement and balance sheet data."""
    cache_key = f"yf_financials_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        result = {}

        # Income statement
        income = t.financials
        if income is not None and not income.empty:
            inc = income.iloc[:, :2].copy()
            inc.columns = [str(c) for c in inc.columns]
            result["income_statement"] = inc.to_dict()

        # Quarterly earnings
        try:
            earnings = t.quarterly_earnings
        except DeprecationWarning:
            earnings = None
        if earnings is not None and not earnings.empty:
            result["quarterly_earnings"] = earnings.tail(4).to_dict()

        # Earnings dates
        try:
            calendar = t.calendar
            if calendar is not None:
                if isinstance(calendar, dict):
                    result["earnings_date"] = str(calendar.get("Earnings Date", ["Unknown"])[0]) if "Earnings Date" in calendar else None
                elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
                    result["earnings_date"] = str(calendar.iloc[0, 0]) if calendar.shape[1] > 0 else None
        except Exception:
            result["earnings_date"] = None

        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get financials for {ticker}: {e}")
        return {}


def get_earnings_history(ticker: str) -> list[dict]:
    """Get recent earnings surprise history."""
    cache_key = f"yf_earnings_hist_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        eh = t.earnings_history
        if eh is not None and not eh.empty:
            records = eh.tail(4).to_dict(orient="records")
            _write_cache(cache_key, records)
            return records
        return []
    except Exception as e:
        logger.error(f"Failed to get earnings history for {ticker}: {e}")
        return []


def _safe_val(df: pd.DataFrame, row_name: str, col_idx: int) -> Optional[float]:
    """Safely extract a value from a financial statement DataFrame."""
    try:
        if row_name in df.index and col_idx < df.shape[1]:
            val = df.loc[row_name].iloc[col_idx]
            if pd.notna(val):
                return float(val)
    except Exception:
        pass
    return None


def get_quality_data(ticker: str) -> dict[str, Any]:
    """Get financial statement data needed for Piotroski F-Score computation."""
    cache_key = f"yf_quality_{ticker}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        result = {}

        # Income statement (annual, last 2 years)
        income = t.financials
        if income is not None and not income.empty:
            result["net_income_current"] = _safe_val(income, "Net Income", 0)
            result["net_income_prior"] = _safe_val(income, "Net Income", 1)
            result["gross_profit_current"] = _safe_val(income, "Gross Profit", 0)
            result["gross_profit_prior"] = _safe_val(income, "Gross Profit", 1)
            result["total_revenue_current"] = _safe_val(income, "Total Revenue", 0)
            result["total_revenue_prior"] = _safe_val(income, "Total Revenue", 1)

        # Balance sheet (annual, last 2 years)
        bs = t.balance_sheet
        if bs is not None and not bs.empty:
            result["total_assets_current"] = _safe_val(bs, "Total Assets", 0)
            result["total_assets_prior"] = _safe_val(bs, "Total Assets", 1)
            # Try multiple field names for debt
            for debt_field in ["Total Debt", "Long Term Debt", "Total Liabilities Net Minority Interest"]:
                val_curr = _safe_val(bs, debt_field, 0)
                val_prior = _safe_val(bs, debt_field, 1)
                if val_curr is not None:
                    result["total_debt_current"] = val_curr
                    result["total_debt_prior"] = val_prior
                    break
            result["current_assets"] = _safe_val(bs, "Current Assets", 0)
            result["current_liabilities"] = _safe_val(bs, "Current Liabilities", 0)
            result["current_assets_prior"] = _safe_val(bs, "Current Assets", 1)
            result["current_liabilities_prior"] = _safe_val(bs, "Current Liabilities", 1)
            # Try multiple field names for shares
            for shares_field in ["Share Issued", "Ordinary Shares Number", "Common Stock"]:
                val_curr = _safe_val(bs, shares_field, 0)
                val_prior = _safe_val(bs, shares_field, 1)
                if val_curr is not None:
                    result["shares_outstanding_current"] = val_curr
                    result["shares_outstanding_prior"] = val_prior
                    break

        # Cash flow statement
        cf = t.cashflow
        if cf is not None and not cf.empty:
            for cf_field in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                val = _safe_val(cf, cf_field, 0)
                if val is not None:
                    result["operating_cash_flow"] = val
                    break

        _write_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Failed to get quality data for {ticker}: {e}")
        return {}


def get_sp500_tickers() -> list[str]:
    """Get S&P 500 constituent tickers via Wikipedia."""
    cache_key = "sp500_tickers"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    try:
        table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        tickers = table[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        _write_cache(cache_key, tickers)
        return tickers
    except Exception as e:
        logger.error(f"Failed to get S&P 500 tickers: {e}")
        return []

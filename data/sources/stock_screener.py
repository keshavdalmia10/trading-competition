"""Dynamic stock screener to discover additional candidates beyond the curated list."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from config.settings import (
    SCREENER_MIN_AVG_VOLUME,
    SCREENER_MIN_EARNINGS_SURPRISE,
    SCREENER_MIN_MARKET_CAP,
    SCREENER_MIN_REVENUE_GROWTH,
)
from config.watchlist import ALL_TICKERS, TICKER_CLASSIFICATION
from data.sources.yahoo_finance import get_sp500_tickers, get_stock_info


def screen_universe() -> list[str]:
    """
    Screen S&P 500 for additional candidates that pass our filters.
    Returns tickers that are NOT already in the curated watchlist.
    """
    logger.info("Running dynamic stock screener...")

    try:
        sp500 = get_sp500_tickers()
    except Exception as e:
        logger.error(f"Failed to get S&P 500 tickers: {e}")
        return []

    # Only screen tickers not already in our curated list
    new_tickers = [t for t in sp500 if t not in ALL_TICKERS]
    logger.info(f"Screening {len(new_tickers)} tickers not in curated list")

    discovered = []
    for ticker in new_tickers:
        try:
            info = get_stock_info(ticker)
            market_cap = info.get("market_cap") or 0
            avg_volume = info.get("avg_volume") or 0
            rev_growth = info.get("revenue_growth") or 0

            # Apply filters
            if market_cap < SCREENER_MIN_MARKET_CAP:
                continue
            if avg_volume < SCREENER_MIN_AVG_VOLUME:
                continue
            if rev_growth < SCREENER_MIN_REVENUE_GROWTH:
                continue

            discovered.append(ticker)
            logger.info(f"  Screener found: {ticker} (rev_growth={rev_growth:.1%}, mcap=${market_cap/1e9:.1f}B)")

        except Exception as e:
            logger.debug(f"  Skipping {ticker}: {e}")
            continue

    logger.info(f"Dynamic screener found {len(discovered)} additional candidates")
    return discovered


def get_full_universe(include_screener: bool = True) -> list[str]:
    """
    Get the full ticker universe: curated list + dynamic screener results.
    Returns deduplicated, sorted list.
    """
    universe = list(ALL_TICKERS)

    if include_screener:
        try:
            screened = screen_universe()
            universe.extend(screened)
            # Classify new tickers as evolution by default
            for t in screened:
                TICKER_CLASSIFICATION.setdefault(t, "evolution")
        except Exception as e:
            logger.warning(f"Screener failed, using curated list only: {e}")

    return sorted(set(universe))

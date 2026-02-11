"""Technical indicator computation using pandas-ta."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger


def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute technical indicators for a price DataFrame.
    Expects columns: Open, High, Low, Close, Volume.
    Returns dict of indicator values.
    """
    if df.empty or len(df) < 20:
        return {}

    try:
        import pandas_ta as ta
    except ImportError:
        logger.warning("pandas-ta not installed, computing indicators manually")
        return _compute_manual(df)

    result = {}
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # RSI
    rsi = ta.rsi(close, length=14)
    if rsi is not None and not rsi.empty:
        result["rsi_14"] = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None

    # MACD
    macd_df = ta.macd(close)
    if macd_df is not None and not macd_df.empty:
        macd_line = macd_df.iloc[-1, 0]
        signal_line = macd_df.iloc[-1, 2] if macd_df.shape[1] > 2 else 0
        if not np.isnan(macd_line) and not np.isnan(signal_line):
            result["macd_value"] = float(macd_line)
            result["macd_signal_value"] = float(signal_line)
            result["macd_signal"] = "bullish" if macd_line > signal_line else "bearish"

    # Simple Moving Averages
    for period in [20, 50, 200]:
        sma = ta.sma(close, length=period)
        if sma is not None and not sma.empty and not np.isnan(sma.iloc[-1]):
            result[f"sma_{period}"] = float(sma.iloc[-1])
            result[f"above_sma_{period}"] = float(close.iloc[-1]) > float(sma.iloc[-1])

    # Bollinger Bands
    bb = ta.bbands(close, length=20)
    if bb is not None and not bb.empty:
        upper = bb.iloc[-1, 0]
        mid = bb.iloc[-1, 1]
        lower = bb.iloc[-1, 2]
        price = float(close.iloc[-1])
        if not any(np.isnan(x) for x in [upper, mid, lower]):
            if price > float(upper):
                result["bollinger_position"] = "above_upper"
            elif price > float(mid):
                result["bollinger_position"] = "upper"
            elif price > float(lower):
                result["bollinger_position"] = "lower"
            else:
                result["bollinger_position"] = "below_lower"

    # Volume trend (20-day avg vs recent 5-day avg)
    if len(volume) >= 20:
        vol_20d = float(volume.tail(20).mean())
        vol_5d = float(volume.tail(5).mean())
        if vol_20d > 0:
            ratio = vol_5d / vol_20d
            if ratio > 1.2:
                result["volume_trend"] = "increasing"
            elif ratio < 0.8:
                result["volume_trend"] = "decreasing"
            else:
                result["volume_trend"] = "stable"

    # Support/Resistance (simple: 20-day low/high)
    if len(df) >= 20:
        result["support_level"] = float(low.tail(20).min())
        result["resistance_level"] = float(high.tail(20).max())

    result["current_price"] = float(close.iloc[-1])

    return result


def _compute_manual(df: pd.DataFrame) -> dict[str, Any]:
    """Fallback manual computation if pandas-ta is not available."""
    result = {}
    close = df["Close"]

    # RSI (Wilder's smoothing)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    if not rsi.empty and not np.isnan(rsi.iloc[-1]):
        result["rsi_14"] = float(rsi.iloc[-1])

    # SMAs
    for period in [20, 50, 200]:
        if len(close) >= period:
            sma = float(close.rolling(period).mean().iloc[-1])
            result[f"sma_{period}"] = sma
            result[f"above_sma_{period}"] = float(close.iloc[-1]) > sma

    # MACD
    if len(close) >= 26:
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        result["macd_value"] = float(macd.iloc[-1])
        result["macd_signal_value"] = float(signal.iloc[-1])
        result["macd_signal"] = "bullish" if macd.iloc[-1] > signal.iloc[-1] else "bearish"

    result["current_price"] = float(close.iloc[-1])
    result["support_level"] = float(df["Low"].tail(20).min())
    result["resistance_level"] = float(df["High"].tail(20).max())

    # Volume trend
    volume = df["Volume"]
    if len(volume) >= 20:
        vol_20d = float(volume.tail(20).mean())
        vol_5d = float(volume.tail(5).mean())
        ratio = vol_5d / vol_20d if vol_20d > 0 else 1
        if ratio > 1.2:
            result["volume_trend"] = "increasing"
        elif ratio < 0.8:
            result["volume_trend"] = "decreasing"
        else:
            result["volume_trend"] = "stable"

    return result

"""Volatility models: EWMA, GARCH(1,1), and Cornish-Fisher VaR."""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger


def ewma_volatility(returns: pd.Series, span: int = 30) -> float:
    """Exponentially weighted moving average volatility (annualized).

    Recent returns are weighted more heavily than distant ones.
    """
    if len(returns) < 10:
        return float(returns.std() * np.sqrt(252))
    ewma_var = returns.ewm(span=span).var().iloc[-1]
    return float(np.sqrt(ewma_var) * np.sqrt(252))


def fit_garch11(returns: pd.Series) -> dict:
    """Fit GARCH(1,1) model and return parameters + one-step-ahead forecast.

    Returns dict with keys: omega, alpha, beta, forecast (daily vol),
    forecast_annualized, long_run_var, converged.
    Falls back to EWMA if fitting fails.
    """
    result = {"converged": False}

    if len(returns) < 30:
        logger.debug("GARCH: insufficient data (<30 obs), falling back to EWMA")
        fallback = ewma_volatility(returns)
        result["forecast_annualized"] = fallback
        result["forecast"] = fallback / np.sqrt(252)
        return result

    try:
        from arch import arch_model

        # Scale returns to percentage for numerical stability
        scaled = returns.dropna() * 100
        model = arch_model(scaled, vol="Garch", p=1, q=1, mean="Zero", rescale=False)
        fit = model.fit(disp="off", show_warning=False)

        omega = fit.params.get("omega", 0)
        alpha = fit.params.get("alpha[1]", 0)
        beta = fit.params.get("beta[1]", 0)

        # One-step-ahead variance forecast (in percentage^2)
        forecasts = fit.forecast(horizon=1)
        forecast_var_pct = forecasts.variance.iloc[-1, 0]
        # Convert back from percentage to decimal
        forecast_daily_vol = np.sqrt(forecast_var_pct) / 100

        # Long-run variance: omega / (1 - alpha - beta)
        persistence = alpha + beta
        long_run_var = (omega / (1 - persistence)) / 10000 if persistence < 0.999 else None

        result.update({
            "omega": float(omega),
            "alpha": float(alpha),
            "beta": float(beta),
            "persistence": float(persistence),
            "forecast": float(forecast_daily_vol),
            "forecast_annualized": float(forecast_daily_vol * np.sqrt(252)),
            "long_run_var": float(long_run_var) if long_run_var else None,
            "converged": True,
        })
    except Exception as e:
        logger.debug(f"GARCH fitting failed: {e}, falling back to EWMA")
        fallback = ewma_volatility(returns)
        result["forecast_annualized"] = fallback
        result["forecast"] = fallback / np.sqrt(252)

    return result


def cornish_fisher_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Value at Risk adjusted for skewness and kurtosis (fat tails).

    Uses the Cornish-Fisher expansion to adjust the normal quantile
    for non-normality in the return distribution.
    Returns the VaR as a negative number (loss).
    """
    if len(returns) < 20:
        # Fall back to parametric normal VaR
        return float(returns.mean() - 1.645 * returns.std())

    from scipy.stats import norm, skew, kurtosis

    z = norm.ppf(1 - confidence)  # -1.645 for 95%
    s = skew(returns.dropna())
    k = kurtosis(returns.dropna(), fisher=True)  # excess kurtosis

    # Cornish-Fisher expansion
    z_cf = (
        z
        + (z**2 - 1) * s / 6
        + (z**3 - 3 * z) * k / 24
        - (2 * z**3 - 5 * z) * s**2 / 36
    )

    var = float(returns.mean() + z_cf * returns.std())
    return var


def classify_vol_regime(
    garch_forecast_ann: float, historical_vol_ann: float
) -> str:
    """Classify volatility regime based on GARCH forecast vs historical avg.

    - "high": GARCH forecast > 1.3× historical (vol spike expected)
    - "low": GARCH forecast < 0.7× historical (calm period)
    - "normal": in between
    """
    if historical_vol_ann <= 0:
        return "normal"
    ratio = garch_forecast_ann / historical_vol_ann
    if ratio > 1.3:
        return "high"
    elif ratio < 0.7:
        return "low"
    return "normal"

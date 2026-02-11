"""Deterministic algorithmic pre-scoring functions.

These compute grounded 0-100 scores from raw data, which are then passed
to LLM agents as anchoring baselines. Pure functions, no side effects.
"""

from __future__ import annotations


def compute_momentum_score(indicators: dict) -> float:
    """
    Deterministic momentum score from technical indicator data.
    Consumes output of compute_indicators(). Returns 0-100.
    """
    if not indicators:
        return 50.0

    score = 50.0  # Neutral baseline

    # RSI Component (range: -20 to +15)
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if 40 <= rsi <= 65:
            score += 15.0 - abs(rsi - 52.5) * (15.0 / 12.5)
        elif 30 <= rsi < 40:
            score += 5.0
        elif 65 < rsi <= 70:
            pass
        elif rsi > 70:
            score -= min(20.0, (rsi - 70) * 1.0)
        elif rsi < 30:
            score += 8.0

    # MACD Component (range: -10 to +20)
    macd_signal = indicators.get("macd_signal")
    if macd_signal == "bullish":
        score += 15.0
    elif macd_signal == "bearish":
        score -= 10.0

    macd_value = indicators.get("macd_value")
    macd_signal_value = indicators.get("macd_signal_value")
    if macd_value is not None and macd_signal_value is not None:
        histogram = macd_value - macd_signal_value
        if histogram > 0:
            price = indicators.get("current_price", 1)
            normalized = (histogram / max(price, 1)) * 500
            score += min(5.0, normalized)

    # SMA Alignment Component (range: 0 to +15)
    above_20 = indicators.get("above_sma_20", False)
    above_50 = indicators.get("above_sma_50", False)
    above_200 = indicators.get("above_sma_200", False)
    score += sum([above_20, above_50, above_200]) * 5.0

    # Volume Trend Component (range: -5 to +10)
    volume_trend = indicators.get("volume_trend")
    if volume_trend == "increasing":
        score += 10.0
    elif volume_trend == "decreasing":
        score -= 5.0

    # Bollinger Band Component (range: -10 to +5)
    bb = indicators.get("bollinger_position")
    if bb == "upper":
        score += 5.0
    elif bb == "above_upper":
        score -= 10.0
    elif bb == "below_lower":
        score += 3.0

    return round(min(100.0, max(0.0, score)), 2)


def compute_quality_score(quality_data: dict) -> float:
    """
    Piotroski F-Score inspired quality score.
    9 binary tests, each worth 1 point. Normalized to 0-100.
    Returns 50.0 if insufficient data.
    """
    if not quality_data:
        return 50.0

    points = 0
    tests_run = 0

    # 1. Positive net income
    net_income = quality_data.get("net_income_current")
    if net_income is not None:
        tests_run += 1
        if net_income > 0:
            points += 1

    # 2. Positive ROA (net income / total assets)
    total_assets = quality_data.get("total_assets_current")
    if net_income is not None and total_assets and total_assets > 0:
        tests_run += 1
        if net_income / total_assets > 0:
            points += 1

    # 3. Positive operating cash flow
    ocf = quality_data.get("operating_cash_flow")
    if ocf is not None:
        tests_run += 1
        if ocf > 0:
            points += 1

    # 4. Cash flow > net income (accrual quality)
    if ocf is not None and net_income is not None:
        tests_run += 1
        if ocf > net_income:
            points += 1

    # 5. Lower debt ratio YoY
    debt_curr = quality_data.get("total_debt_current")
    debt_prior = quality_data.get("total_debt_prior")
    assets_curr = quality_data.get("total_assets_current")
    assets_prior = quality_data.get("total_assets_prior")
    if all(v is not None for v in [debt_curr, debt_prior, assets_curr, assets_prior]):
        if assets_curr > 0 and assets_prior > 0:
            tests_run += 1
            if debt_curr / assets_curr <= debt_prior / assets_prior:
                points += 1

    # 6. Higher current ratio YoY
    ca_curr = quality_data.get("current_assets")
    cl_curr = quality_data.get("current_liabilities")
    ca_prior = quality_data.get("current_assets_prior")
    cl_prior = quality_data.get("current_liabilities_prior")
    if all(v is not None for v in [ca_curr, cl_curr, ca_prior, cl_prior]):
        if cl_curr > 0 and cl_prior > 0:
            tests_run += 1
            if ca_curr / cl_curr >= ca_prior / cl_prior:
                points += 1

    # 7. No new share dilution
    shares_curr = quality_data.get("shares_outstanding_current")
    shares_prior = quality_data.get("shares_outstanding_prior")
    if shares_curr is not None and shares_prior is not None:
        tests_run += 1
        if shares_curr <= shares_prior:
            points += 1

    # 8. Higher gross margin YoY
    gp_curr = quality_data.get("gross_profit_current")
    gp_prior = quality_data.get("gross_profit_prior")
    rev_curr = quality_data.get("total_revenue_current")
    rev_prior = quality_data.get("total_revenue_prior")
    if all(v is not None for v in [gp_curr, gp_prior, rev_curr, rev_prior]):
        if rev_curr > 0 and rev_prior > 0:
            tests_run += 1
            if gp_curr / rev_curr >= gp_prior / rev_prior:
                points += 1

    # 9. Higher asset turnover YoY
    if all(v is not None for v in [rev_curr, rev_prior, assets_curr, assets_prior]):
        if assets_curr > 0 and assets_prior > 0:
            tests_run += 1
            if rev_curr / assets_curr >= rev_prior / assets_prior:
                points += 1

    if tests_run == 0:
        return 50.0
    return round((points / tests_run) * 100.0, 2)


def compute_earnings_surprise_score(
    earnings_history: list[dict],
    has_earnings_in_window: bool = False,
) -> float:
    """
    Deterministic earnings surprise score.
    Based on beat frequency, average surprise %, and upcoming earnings.
    Returns 0-100. Returns 50.0 if no data.
    """
    if not earnings_history:
        return 50.0

    surprises = []
    for e in earnings_history[-4:]:
        surprise_pct = e.get("surprisePercent")
        if surprise_pct is None:
            actual = e.get("epsActual")
            estimate = e.get("epsEstimate")
            if actual is not None and estimate is not None and estimate != 0:
                surprise_pct = ((actual - estimate) / abs(estimate)) * 100
        if surprise_pct is not None and isinstance(surprise_pct, (int, float)):
            surprises.append(float(surprise_pct))

    if not surprises:
        return 50.0

    n_quarters = len(surprises)

    # Component 1: Beat frequency (0-40 points)
    beats = sum(1 for s in surprises if s > 0)
    frequency_score = (beats / n_quarters) * 40.0

    # Component 2: Average surprise magnitude (0-35 points, can be negative)
    avg_surprise = sum(surprises) / len(surprises)
    if avg_surprise >= 0:
        magnitude_score = min(35.0, avg_surprise * 3.5)
    else:
        magnitude_score = max(-15.0, avg_surprise * 3.0)

    # Component 3: Consistency bonus (0-10 points)
    if n_quarters >= 3 and beats == n_quarters:
        consistency_bonus = 10.0
    elif n_quarters >= 3 and beats >= n_quarters - 1:
        consistency_bonus = 5.0
    else:
        consistency_bonus = 0.0

    # Component 4: Upcoming earnings in competition window (+15 points)
    earnings_window_bonus = 15.0 if has_earnings_in_window else 0.0

    total = frequency_score + magnitude_score + consistency_bonus + earnings_window_bonus
    return round(min(100.0, max(0.0, total)), 2)


def compute_risk_adjusted_score(risk_metrics: dict) -> float:
    """
    Deterministic risk-adjusted score for competition context.
    Higher = better risk/reward profile. Returns 0-100.
    """
    if not risk_metrics:
        return 50.0

    score = 0.0

    # Sharpe Ratio Component (0-35 points)
    sharpe = risk_metrics.get("sharpe_ratio")
    if sharpe is not None:
        if sharpe >= 2.0:
            score += 35.0
        elif sharpe >= 0:
            score += 10.0 + (sharpe * 12.5)
        else:
            score += max(0.0, 10.0 + sharpe * 10.0)

    # Max Drawdown Component (0-25 points)
    max_dd = risk_metrics.get("max_drawdown_90d")
    if max_dd is not None:
        dd_pct = abs(max_dd)
        if dd_pct <= 0.05:
            score += 25.0
        elif dd_pct <= 0.30:
            score += max(0.0, 25.0 - (dd_pct - 0.05) * 100.0)

    # Beta Sweet Spot Component (0-25 points)
    # Competition sweet spot: 1.0-1.5 (peak at 1.25)
    beta = risk_metrics.get("beta")
    if beta is not None:
        if 1.0 <= beta <= 1.5:
            distance = abs(beta - 1.25)
            score += 25.0 - (distance / 0.25) * 5.0
        elif 0.5 <= beta < 1.0:
            score += 15.0
        elif 1.5 < beta <= 2.0:
            score += 15.0
        elif beta > 2.0:
            score += 5.0
        else:
            score += 10.0

    # VaR Component (0-15 points) — now Cornish-Fisher adjusted
    var_95 = risk_metrics.get("value_at_risk_95")
    if var_95 is not None:
        var_abs = abs(var_95)
        if var_abs <= 0.01:
            score += 15.0
        elif var_abs <= 0.04:
            score += max(0.0, 15.0 - (var_abs - 0.01) * 500.0)

    return round(min(100.0, max(0.0, score)), 2)


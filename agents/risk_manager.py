"""Agent 6: Risk Manager — assesses risk metrics and suggests position sizes."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import RISK_WINDOW_DAYS
from data.models import (
    FundamentalScreenerOutput,
    RiskManagerOutput,
)
from data.sources.yahoo_finance import get_price_history
from tools.algorithmic_scores import compute_risk_adjusted_score
from tools.position_sizing import inverse_volatility_weights
from tools.volatility_models import (
    cornish_fisher_var,
    classify_vol_regime,
    ewma_volatility,
    fit_garch11,
)


def _compute_risk_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """Compute risk metrics from price history DataFrame."""
    if df.empty or len(df) < 20:
        return {}

    close = df["Close"]
    returns = close.pct_change().dropna()

    if returns.empty:
        return {}

    metrics = {}

    # Historical volatility (simple, kept for reference)
    historical_vol = float(returns.std() * np.sqrt(252))

    # EWMA volatility (recency-weighted)
    metrics["ewma_volatility"] = ewma_volatility(returns)

    # GARCH(1,1) forecast
    garch = fit_garch11(returns)
    metrics["garch_forecast"] = garch.get("forecast_annualized", historical_vol)

    # Use GARCH forecast as primary volatility (fallback to EWMA, then historical)
    if garch.get("converged"):
        metrics["volatility_annualized"] = metrics["garch_forecast"]
    else:
        metrics["volatility_annualized"] = metrics["ewma_volatility"]

    # Volatility regime classification
    metrics["vol_regime"] = classify_vol_regime(
        metrics["volatility_annualized"], historical_vol
    )

    metrics["max_drawdown_90d"] = float(
        (close / close.cummax() - 1).min()
    )

    # Cornish-Fisher VaR (fat-tail adjusted)
    metrics["value_at_risk_95"] = cornish_fisher_var(returns, confidence=0.95)


    # Sharpe ratio (annualized, assuming 0% risk-free for simplicity)
    mean_return = returns.mean() * 252
    vol = metrics["volatility_annualized"]
    metrics["sharpe_ratio"] = float(mean_return / vol) if vol > 0 else 0.0

    return metrics


class RiskManager(BaseAgent):
    name = "risk_manager"
    description = "Risk manager assessing portfolio risk and suggesting position sizes"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering risk data...")

        screener_output: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        if not screener_output:
            return {"tickers_data": [], "correlations": []}

        tickers = [c.ticker for c in screener_output.candidates]
        tickers_data = []
        price_series = {}

        for ticker in tickers:
            try:
                df = get_price_history(ticker, days=RISK_WINDOW_DAYS)
                if df.empty:
                    continue

                metrics = _compute_risk_metrics(df)

                tickers_data.append({
                    "ticker": ticker,
                    "beta": None,  # Will be computed relative to SPY
                    **metrics,
                })

                # Store close prices for correlation computation
                price_series[ticker] = df["Close"]
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping {ticker}: {e}")
                continue

        # Compute betas relative to SPY
        spy_df = get_price_history("SPY", days=RISK_WINDOW_DAYS)
        if not spy_df.empty:
            spy_returns = spy_df["Close"].pct_change().dropna()
            for td in tickers_data:
                ticker = td["ticker"]
                if ticker in price_series:
                    stock_returns = price_series[ticker].pct_change().dropna()
                    # Align dates
                    aligned = pd.DataFrame({
                        "stock": stock_returns, "spy": spy_returns
                    }).dropna()
                    if len(aligned) > 10:
                        cov = aligned["stock"].cov(aligned["spy"])
                        var = aligned["spy"].var()
                        td["beta"] = float(cov / var) if var > 0 else 1.0

        # Compute pairwise correlations (top correlated pairs)
        correlations = []
        if len(price_series) >= 2:
            returns_df = pd.DataFrame({
                t: s.pct_change() for t, s in price_series.items()
            }).dropna()
            if not returns_df.empty:
                corr_matrix = returns_df.corr()
                for i, t1 in enumerate(corr_matrix.columns):
                    for j, t2 in enumerate(corr_matrix.columns):
                        if i < j:
                            c = corr_matrix.iloc[i, j]
                            if abs(c) > 0.7:  # Only report high correlations
                                correlations.append({
                                    "ticker_a": t1,
                                    "ticker_b": t2,
                                    "correlation": round(float(c), 3),
                                })

        # Compute algorithmic risk-adjusted scores (after beta is available)
        for td in tickers_data:
            risk_input = {
                "sharpe_ratio": td.get("sharpe_ratio"),
                "max_drawdown_90d": td.get("max_drawdown_90d"),
                "value_at_risk_95": td.get("value_at_risk_95"),
                "beta": td.get("beta"),
            }
            td["risk_adjusted_score_algo"] = compute_risk_adjusted_score(risk_input)

        # Compute inverse-vol weights
        vol_dict = {
            td["ticker"]: td.get("volatility_annualized", 0.3)
            for td in tickers_data
        }
        suggested_weights = inverse_volatility_weights(vol_dict)
        for td in tickers_data:
            td["suggested_weight"] = suggested_weights.get(td["ticker"], 0.05)

        return {"tickers_data": tickers_data, "correlations": correlations}

    async def analyze(self, data: dict[str, Any]) -> RiskManagerOutput:
        # Get outputs from other agents on the bus
        technical = self.bus.get("technical_analyst")
        catalyst = self.bus.get("catalyst_hunter")
        sentiment = self.bus.get("sentiment_analyst")

        context = {
            "technical_summary": technical.summary if technical else "N/A",
            "catalyst_summary": catalyst.summary if catalyst else "N/A",
            "sentiment_summary": sentiment.summary if sentiment else "N/A",
        }

        prompt = f"""You are a risk manager for a 3-WEEK trading competition (Feb 9 - Mar 2, 2026).
Evaluate the risk profile of each stock and the portfolio as a whole.

RISK METRICS:
{json.dumps(data['tickers_data'], indent=1, default=str)}

HIGH CORRELATIONS (>0.7):
{json.dumps(data['correlations'], indent=1, default=str)}

OTHER AGENT INSIGHTS:
{json.dumps(context, indent=1, default=str)}

VOLATILITY MODELS: Each stock includes GARCH(1,1) forecast volatility, EWMA volatility, and a
vol_regime classification ("high"/"normal"/"low"). The VaR uses Cornish-Fisher expansion (fat-tail
adjusted, not naive normal assumption). Use these for more accurate risk assessment.

ALGORITHMIC PRE-SCORE: Each stock has a "risk_adjusted_score_algo" computed deterministically from
Sharpe ratio normalization, max drawdown penalty, beta sweet-spot analysis (1.0-1.5 ideal for
competition), and VaR component. USE THIS AS YOUR STARTING POINT for risk_score.
You may adjust by +/-15 points with clear justification.

Scoring guide (HIGHER = BETTER risk-adjusted profile):
- 80-100: Low volatility, strong Sharpe, small max drawdown, moderate beta
- 60-79: Moderate risk with acceptable risk/reward
- 40-59: Elevated risk — high volatility or beta
- 20-39: High risk — large drawdowns, extreme volatility
- 0-19: Very high risk — dangerous for a competition

IMPORTANT: For a competition, we want stocks with ENOUGH volatility to generate returns,
but not so much that drawdowns could destroy performance. Sweet spot is moderate-high volatility
with positive momentum.

Also suggest position sizes (weight as decimal 0-1) and note diversification concerns.

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "AAPL",
            "beta": 1.1,
            "volatility_annualized": 0.25,
            "max_drawdown_90d": -0.08,
            "value_at_risk_95": -0.02,
            "sharpe_ratio": 1.5,
            "risk_score": 70,
            "suggested_weight": 0.12,
            "rationale": "Moderate risk profile suitable for competition..."
        }}
    ],
    "high_correlations": [
        {{"ticker_a": "AAPL", "ticker_b": "MSFT", "correlation": 0.85}}
    ],
    "portfolio_beta": 1.15,
    "diversification_notes": "Portfolio has good sector diversification...",
    "summary": "Overall risk assessment..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, RiskManagerOutput)

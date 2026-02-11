"""Agent 3: Technical Analyst — computes technical scores for screened candidates."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from data.models import FundamentalScreenerOutput, TechnicalAnalystOutput
from data.sources.alpha_vantage import get_price_history
from tools.algorithmic_scores import compute_momentum_score
from tools.technical_indicators import compute_indicators


class TechnicalAnalyst(BaseAgent):
    name = "technical_analyst"
    description = "Technical analyst evaluating momentum and price patterns"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering technical data...")

        screener_output: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        if not screener_output:
            logger.error(f"[{self.name}] No fundamental screener data on bus!")
            return {"tickers_data": []}

        tickers = [c.ticker for c in screener_output.candidates]
        tickers_data = []

        for ticker in tickers:
            try:
                df = get_price_history(ticker, days=180)
                if df.empty:
                    continue
                indicators = compute_indicators(df)
                indicators["ticker"] = ticker
                indicators["momentum_score_algo"] = compute_momentum_score(indicators)
                tickers_data.append(indicators)
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping {ticker}: {e}")
                continue

        return {"tickers_data": tickers_data}

    async def analyze(self, data: dict[str, Any]) -> TechnicalAnalystOutput:
        prompt = f"""You are a technical analyst evaluating stocks for a 3-WEEK trading competition
(Feb 9 - Mar 2, 2026). Focus on SHORT-TERM momentum and setups.

TECHNICAL DATA for each stock:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ALGORITHMIC PRE-SCORE: Each stock has a "momentum_score_algo" computed deterministically from
RSI zone, MACD crossover, SMA alignment, volume trend, and Bollinger position.
USE THIS AS YOUR STARTING POINT for technical_score. You may adjust by +/-15 points with
clear justification. If you deviate more, explain why the formula is misleading for this stock.

Scoring factors:
- RSI: 40-65 is ideal (momentum without being overbought). >70 risky, <30 oversold bounce potential
- MACD: bullish crossover = strong positive signal
- Price above SMA 20 and 50 = bullish short-term trend
- Volume increasing = confirms trend
- Bollinger position: middle/upper band = healthy uptrend
- Support/resistance: closer to support = better risk/reward

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "AAPL",
            "current_price": 195.50,
            "rsi_14": 55.2,
            "macd_signal": "bullish",
            "sma_20": 190.0,
            "sma_50": 185.0,
            "sma_200": 175.0,
            "above_sma_20": true,
            "above_sma_50": true,
            "above_sma_200": true,
            "bollinger_position": "upper",
            "volume_trend": "increasing",
            "support_level": 188.0,
            "resistance_level": 200.0,
            "technical_score": 72,
            "rationale": "Bullish MACD crossover with increasing volume..."
        }}
    ],
    "summary": "Overall technical analysis summary..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, TechnicalAnalystOutput)

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
    provider = "claude"

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
        prompt = f"""You are a technical analyst evaluating stocks for a LONG/SHORT competition
(Mar 2 - Apr 3, 2026). Analyze BOTH bullish setups (for longs) AND bearish setups (for shorts).

CRITICAL CONTEXT:
- US-Iran war driving sector divergence. Defense/energy trending UP, airlines trending DOWN.
- Look for bullish patterns on long candidates, bearish patterns on short candidates.
- For SHORT candidates: high RSI (overbought bounces failing), bearish MACD, below key SMAs,
  increasing volume on down days = GOOD short setup = HIGH technical score.

TECHNICAL DATA for each stock:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ALGORITHMIC PRE-SCORE: "momentum_score_algo" computed from RSI, MACD, SMA, volume, Bollinger.
For LONG candidates: use as starting point for technical_score.
For SHORT candidates: INVERT it (100 - momentum_score_algo) as starting point.
A stock with terrible momentum = great short = high technical_score for a short.
Adjust by +/-15 points with justification.

FOR LONGS: RSI 40-65 ideal, bullish MACD, above SMA 20/50, increasing volume.
FOR SHORTS: RSI >70 or continued weakness below 30, bearish MACD, below SMA 20/50.

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "current_price": 520.50,
            "rsi_14": 55.2,
            "macd_signal": "bullish",
            "sma_20": 510.0,
            "sma_50": 490.0,
            "sma_200": 470.0,
            "above_sma_20": true,
            "above_sma_50": true,
            "above_sma_200": true,
            "bollinger_position": "upper",
            "volume_trend": "increasing",
            "support_level": 505.0,
            "resistance_level": 535.0,
            "technical_score": 78,
            "rationale": "Bullish MACD with war-driven momentum..."
        }}
    ],
    "summary": "Overall technical analysis covering both long and short setups..."
}}"""

        response = self._call_llm(prompt)
        result = self._parse_json_response(response, TechnicalAnalystOutput)

        # Backfill current_price from gathered data
        price_map = {
            d["ticker"]: d.get("current_price")
            for d in data["tickers_data"]
            if d.get("current_price") is not None
        }
        for analysis in result.analyses:
            if analysis.current_price is None and analysis.ticker in price_map:
                analysis.current_price = price_map[analysis.ticker]

        return result

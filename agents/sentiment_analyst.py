"""Agent 5: Sentiment Analyst — gauges market mood and institutional positioning."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from data.models import FundamentalScreenerOutput, SentimentAnalystOutput
from data.sources.finnhub_client import get_analyst_recommendations, get_price_target
from data.sources.news_api import get_headlines


def _compute_vader_sentiment(texts: list[str]) -> float:
    """Compute average VADER sentiment score for a list of texts."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        if not texts:
            return 0.0
        scores = [analyzer.polarity_scores(t)["compound"] for t in texts]
        return sum(scores) / len(scores)
    except ImportError:
        logger.warning("vaderSentiment not installed, returning 0")
        return 0.0


class SentimentAnalyst(BaseAgent):
    name = "sentiment_analyst"
    description = "Sentiment analyst evaluating market mood and institutional positioning"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering sentiment data...")

        screener_output: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        if not screener_output:
            return {"tickers_data": []}

        tickers_data = []
        for candidate in screener_output.candidates:
            ticker = candidate.ticker
            name = candidate.name
            try:
                # News headlines for VADER sentiment
                headlines = get_headlines(f"{name} {ticker} stock", days_back=7, page_size=15)
                headline_texts = [h["title"] for h in headlines if h.get("title")]
                vader_score = _compute_vader_sentiment(headline_texts)

                # Analyst recommendations from Finnhub
                analyst_recs = get_analyst_recommendations(ticker)
                price_target = get_price_target(ticker)

                # Summarize analyst consensus
                consensus = "hold"
                upgrades = 0
                downgrades = 0
                if analyst_recs:
                    latest = analyst_recs[0]
                    total = (latest.get("strong_buy", 0) + latest.get("buy", 0) +
                             latest.get("hold", 0) + latest.get("sell", 0) + latest.get("strong_sell", 0))
                    if total > 0:
                        bull = latest.get("strong_buy", 0) + latest.get("buy", 0)
                        bear = latest.get("sell", 0) + latest.get("strong_sell", 0)
                        if bull / total > 0.6:
                            consensus = "buy" if bull / total > 0.8 else "moderate buy"
                        elif bear / total > 0.4:
                            consensus = "sell"

                    # Compare with previous period for upgrades/downgrades
                    if len(analyst_recs) > 1:
                        prev = analyst_recs[1]
                        upgrades = max(0, (latest.get("strong_buy", 0) + latest.get("buy", 0)) -
                                       (prev.get("strong_buy", 0) + prev.get("buy", 0)))
                        downgrades = max(0, (latest.get("sell", 0) + latest.get("strong_sell", 0)) -
                                         (prev.get("sell", 0) + prev.get("strong_sell", 0)))

                tickers_data.append({
                    "ticker": ticker,
                    "name": name,
                    "vader_sentiment": round(vader_score, 3),
                    "analyst_consensus": consensus,
                    "analyst_target_price": price_target.get("target_mean"),
                    "recent_upgrades": upgrades,
                    "recent_downgrades": downgrades,
                    "key_headlines": headline_texts[:5],
                    "analyst_breakdown": analyst_recs[0] if analyst_recs else {},
                })
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping {ticker}: {e}")
                continue

        return {"tickers_data": tickers_data}

    async def analyze(self, data: dict[str, Any]) -> SentimentAnalystOutput:
        prompt = f"""You are a sentiment analyst for a 3-WEEK trading competition (Feb 9 - Mar 2, 2026).
Evaluate the overall market sentiment for each stock.

SENTIMENT DATA:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ANCHORING: Each stock has a "vader_sentiment" score (-1 to +1). Convert it to a 0-100 scale
as your starting point: sentiment_starting_point = (vader_sentiment + 1) / 2 * 100.
Then adjust based on analyst consensus, upgrades/downgrades, and headline quality.
You may deviate +/-15 points from this anchor with clear justification.

Scoring factors:
- VADER sentiment (-1 to +1): positive = bullish news flow
- Analyst consensus: "strong buy" or "buy" = strong positive
- Recent upgrades vs downgrades
- Quality of headlines (are they about growth, innovation, or problems?)
- Analyst target price vs current price (upside potential)

Scoring guide:
- 80-100: Very bullish sentiment — positive news, analyst upgrades, strong buy consensus
- 60-79: Moderately bullish — mostly positive news, buy consensus
- 40-59: Neutral/mixed sentiment
- 20-39: Moderately bearish — negative news, downgrades
- 0-19: Very bearish sentiment

Also provide overall_sentiment as -1 to +1 float.

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "AAPL",
            "overall_sentiment": 0.65,
            "analyst_consensus": "buy",
            "analyst_target_price": 210.0,
            "recent_upgrades": 2,
            "recent_downgrades": 0,
            "key_headlines": ["headline1", "headline2"],
            "sentiment_score": 75,
            "rationale": "Strong positive sentiment driven by..."
        }}
    ],
    "summary": "Overall sentiment landscape..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, SentimentAnalystOutput)

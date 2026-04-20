"""Agent 5: Sentiment Analyst — gauges market mood and institutional positioning."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from data.models import FundamentalScreenerOutput, SentimentAnalystOutput
from data.sources.finnhub_client import get_analyst_recommendations, get_price_target
from data.sources.news_api import get_headlines
from data.sources.polymarket import PolymarketClient


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
    provider = "claude"

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

        # Polymarket crowd sentiment
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}

        return {"tickers_data": tickers_data, "polymarket": polymarket_summary}

    async def analyze(self, data: dict[str, Any]) -> SentimentAnalystOutput:
        prompt = f"""You are a sentiment analyst for a LONG/SHORT competition (Mar 2 - Apr 3, 2026).

CRITICAL CONTEXT:
- US-Iran war dominates news. War-related sentiment is the primary driver.
- For LONG candidates (defense, energy, cyber): positive war news = HIGH sentiment score.
- For SHORT candidates (airlines, consumer): negative war/economic news = HIGH sentiment score
  (because bearish sentiment CONFIRMS the short thesis).

POLYMARKET CROWD SENTIMENT (prediction market probabilities):
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

Polymarket represents CROWD CONSENSUS on event risk. Use it as an additional sentiment signal:
- High ceasefire probability = bearish sentiment for defense longs, bullish for airline shorts
- High war escalation probability = bullish sentiment for defense/energy
- These are real-money bets, so they carry more weight than news headlines alone
- If Polymarket odds DISAGREE with news sentiment, note the divergence in your rationale

SENTIMENT DATA:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ANCHORING:
- For LONG candidates: Convert vader_sentiment to 0-100 scale as starting point.
- For SHORT candidates: INVERT the vader. Negative sentiment = GOOD for a short = high score.
  So: sentiment_starting_point = (1 - vader_sentiment) / 2 * 100.

Adjust +/-15 points based on analyst consensus, upgrades/downgrades, headline quality.

Scoring guide:
- 80-100: Strong sentiment alignment with position direction
- 60-79: Moderately aligned sentiment
- 40-59: Neutral/mixed
- 20-39: Sentiment working against position thesis
- 0-19: Strong sentiment opposition

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "overall_sentiment": 0.75,
            "analyst_consensus": "strong buy",
            "analyst_target_price": 550.0,
            "recent_upgrades": 3,
            "recent_downgrades": 0,
            "key_headlines": ["Lockheed missile systems deployed in Iran campaign"],
            "sentiment_score": 88,
            "rationale": "Very bullish war-driven sentiment..."
        }}
    ],
    "summary": "Sentiment bifurcated: defense/energy bullish, airlines/consumer bearish..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, SentimentAnalystOutput)

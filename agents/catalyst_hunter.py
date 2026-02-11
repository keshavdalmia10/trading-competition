"""Agent 4: Catalyst Hunter — finds upcoming events that could drive big moves."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import COMPETITION_END, COMPETITION_START
from data.models import CatalystHunterOutput, FundamentalScreenerOutput
from data.sources.finnhub_client import get_company_news, get_earnings_calendar
from data.sources.news_api import get_headlines
from data.sources.yahoo_finance import get_financials


class CatalystHunter(BaseAgent):
    name = "catalyst_hunter"
    description = "Catalyst hunter finding upcoming events that drive stock moves"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Hunting for catalysts...")

        screener_output: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        if not screener_output:
            return {"tickers_data": []}

        tickers = [c.ticker for c in screener_output.candidates]

        # Get earnings calendar for competition window
        earnings_cal = get_earnings_calendar(
            str(COMPETITION_START), str(COMPETITION_END)
        )
        earnings_by_ticker = {}
        for e in earnings_cal:
            sym = e.get("symbol", "")
            if sym in tickers:
                earnings_by_ticker.setdefault(sym, []).append(e)

        tickers_data = []
        for ticker in tickers:
            try:
                name = next(
                    (c.name for c in screener_output.candidates if c.ticker == ticker),
                    ticker,
                )
                # Finnhub company news
                finnhub_news = get_company_news(ticker, days_back=14)
                # NewsAPI headlines
                newsapi_headlines = get_headlines(name, days_back=7, page_size=10)
                # Yahoo Finance earnings date
                financials = get_financials(ticker)

                tickers_data.append({
                    "ticker": ticker,
                    "name": name,
                    "earnings_in_window": earnings_by_ticker.get(ticker, []),
                    "yf_earnings_date": financials.get("earnings_date"),
                    "recent_news_finnhub": [
                        {"headline": n["headline"], "datetime": n["datetime"]}
                        for n in finnhub_news[:10]
                    ],
                    "recent_news_newsapi": [
                        {"title": n["title"], "published_at": n["published_at"]}
                        for n in newsapi_headlines[:10]
                    ],
                })
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping {ticker}: {e}")
                continue

        return {
            "tickers_data": tickers_data,
            "competition_start": str(COMPETITION_START),
            "competition_end": str(COMPETITION_END),
        }

    async def analyze(self, data: dict[str, Any]) -> CatalystHunterOutput:
        prompt = f"""You are a catalyst hunter for a 3-WEEK stock trading competition
({data['competition_start']} to {data['competition_end']}).

Your job is to identify UPCOMING CATALYSTS that could drive significant stock price moves
within this exact 3-week window. The most important catalysts are:

1. EARNINGS REPORTS during the window (highest impact — stocks move 5-15% on earnings)
2. Product launches, FDA decisions, regulatory rulings
3. Conference presentations, investor days
4. Analyst days, guidance updates
5. Industry events, competitor actions
6. Macro events (Fed meetings, economic data releases)

DATA FOR EACH STOCK:
{json.dumps(data['tickers_data'], indent=1, default=str)}

For each stock, assign a catalyst_score (0-100):
- 80-100: Earnings date IN the window + positive recent news momentum
- 60-79: Major catalyst expected in window (product launch, FDA, etc.)
- 40-59: Moderate catalysts (conferences, analyst coverage)
- 20-39: Minor catalysts only
- 0-19: No meaningful catalysts in the window

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "AAPL",
            "catalysts": [
                {{
                    "event": "Q1 2026 Earnings Report",
                    "date": "2026-02-15",
                    "impact": "high",
                    "direction": "bullish",
                    "description": "Expected to beat estimates by 5%..."
                }}
            ],
            "catalyst_score": 85,
            "rationale": "Earnings during the window with strong beat expectations..."
        }}
    ],
    "summary": "Overall catalyst landscape summary..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, CatalystHunterOutput)

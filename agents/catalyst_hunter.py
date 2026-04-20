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
from data.sources.polymarket import PolymarketClient
from data.sources.yahoo_finance import get_financials


class CatalystHunter(BaseAgent):
    name = "catalyst_hunter"
    description = "Catalyst hunter finding upcoming events that drive stock moves"
    provider = "claude"

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

        # Polymarket event probabilities
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}

        return {
            "tickers_data": tickers_data,
            "competition_start": str(COMPETITION_START),
            "competition_end": str(COMPETITION_END),
            "polymarket": polymarket_summary,
        }

    async def analyze(self, data: dict[str, Any]) -> CatalystHunterOutput:
        prompt = f"""You are a catalyst hunter for a LONG/SHORT stock trading competition
({data['competition_start']} to {data['competition_end']}).

CRITICAL CONTEXT:
- US-Iran war is the DOMINANT catalyst. All war-related news is high impact.
- FOMC meeting March 17-18 is a major macro catalyst.
- US-China trade chiefs meeting mid-March could move tech/semis.
- 15% universal tariff is pressuring multinationals.

Your job is to identify catalysts for BOTH long and short positions:

FOR LONGS: Positive catalysts (earnings beats, war escalation benefiting defense/energy,
cybersecurity demand, AI infrastructure spending).

FOR SHORTS: Negative catalysts (fuel cost spikes crushing airlines, tariff damage,
consumer spending decline, crypto regulatory uncertainty, ceasefire risk for defense).

CATALYST CATEGORIES (ranked by importance):
1. GEOPOLITICAL: War escalation/de-escalation, Strait of Hormuz, oil supply
2. EARNINGS: Earnings reports during the window (5-15% moves typical)
3. MACRO POLICY: FOMC decision, tariff developments, US-China trade meeting
4. SECTOR-SPECIFIC: FDA decisions, product launches, regulatory rulings
5. SENTIMENT: Analyst upgrades/downgrades, institutional positioning

POLYMARKET EVENT PROBABILITIES (crowd-sourced prediction markets):
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

Use these probabilities to calibrate catalyst scores:
- If ceasefire probability > 20%, DOWNGRADE catalyst scores for war longs (LMT, NOC, RTX etc.)
  and UPGRADE scores for war shorts (they benefit from ceasefire).
- If war escalation probability is HIGH, UPGRADE defense/energy catalysts.
- FOMC and tariff probabilities help calibrate macro catalyst timing.

DATA FOR EACH STOCK:
{json.dumps(data['tickers_data'], indent=1, default=str)}

Scoring:
- 80-100: Multiple strong catalysts in window (earnings + geopolitical alignment)
- 60-79: One major catalyst or strong geopolitical tailwind/headwind
- 40-59: Moderate catalysts (conferences, sector trends)
- 20-39: Minor catalysts only
- 0-19: No meaningful catalysts

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "catalysts": [
                {{
                    "event": "US-Iran war escalation",
                    "date": "ongoing",
                    "impact": "high",
                    "direction": "bullish",
                    "description": "Direct beneficiary of increased defense spending..."
                }}
            ],
            "catalyst_score": 90,
            "rationale": "Multiple high-impact catalysts aligned with war theme..."
        }}
    ],
    "summary": "Overall catalyst landscape dominated by geopolitical events..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, CatalystHunterOutput)

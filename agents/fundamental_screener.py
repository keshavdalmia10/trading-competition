"""Agent 2: Fundamental Screener — filters the universe to top ~20 candidates."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import COMPETITION_END, COMPETITION_START
from config.watchlist import TICKER_CLASSIFICATION
from data.models import FundamentalData, FundamentalScreenerOutput, MacroAnalysis, StockType
from data.sources.stock_screener import get_full_universe
from data.sources.yahoo_finance import get_earnings_history, get_financials, get_quality_data, get_stock_info
from tools.algorithmic_scores import compute_earnings_surprise_score, compute_quality_score


class FundamentalScreener(BaseAgent):
    name = "fundamental_screener"
    description = "Fundamental screener that filters stocks by quality metrics"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering fundamental data for universe...")

        # Get macro analysis from bus (published by MacroAnalyst)
        macro: MacroAnalysis | None = self.bus.get("macro_analyst")
        favored_sectors = macro.favored_sectors if macro else []

        # Get full universe (curated + screener)
        tickers = get_full_universe(include_screener=True)
        logger.info(f"[{self.name}] Screening {len(tickers)} tickers")

        stocks_data = []
        for ticker in tickers:
            try:
                info = get_stock_info(ticker)
                financials = get_financials(ticker)
                earnings_hist = get_earnings_history(ticker)

                # Compute earnings surprise average
                avg_surprise = None
                if earnings_hist:
                    surprises = [
                        e.get("surprisePercent", e.get("epsActual", 0))
                        for e in earnings_hist
                        if e.get("surprisePercent") is not None or e.get("epsActual") is not None
                    ]
                    if surprises:
                        avg_surprise = sum(s for s in surprises if isinstance(s, (int, float))) / max(len(surprises), 1)

                stock_type = TICKER_CLASSIFICATION.get(ticker, "evolution")

                # Compute algorithmic pre-scores
                quality_data = get_quality_data(ticker)
                quality_algo = compute_quality_score(quality_data)

                has_earnings_in_window = False
                earnings_date_str = financials.get("earnings_date")
                if earnings_date_str:
                    try:
                        from datetime import date as dt_date
                        edate = dt_date.fromisoformat(str(earnings_date_str)[:10])
                        has_earnings_in_window = COMPETITION_START <= edate <= COMPETITION_END
                    except (ValueError, TypeError):
                        pass

                earnings_algo = compute_earnings_surprise_score(earnings_hist, has_earnings_in_window)

                stocks_data.append({
                    "ticker": ticker,
                    "name": info.get("name", ticker),
                    "sector": info.get("sector", "Unknown"),
                    "market_cap": info.get("market_cap"),
                    "pe_ratio": info.get("pe_ratio"),
                    "peg_ratio": info.get("peg_ratio"),
                    "revenue_growth_yoy": info.get("revenue_growth"),
                    "eps_growth_yoy": info.get("earnings_growth"),
                    "roe": info.get("roe"),
                    "fcf": info.get("fcf"),
                    "earnings_surprise_pct": avg_surprise,
                    "stock_type": stock_type,
                    "earnings_date": financials.get("earnings_date"),
                    "in_favored_sector": info.get("sector", "") in favored_sectors,
                    "quality_score_algo": quality_algo,
                    "earnings_surprise_score_algo": earnings_algo,
                })
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping {ticker}: {e}")
                continue

        return {"stocks_data": stocks_data, "favored_sectors": favored_sectors}

    async def analyze(self, data: dict[str, Any]) -> FundamentalScreenerOutput:
        prompt = f"""You are screening stocks for a 3-week trading competition (Feb 9 - Mar 2, 2026).
Select the TOP 20 candidates based on fundamental quality.

ALGORITHMIC PRE-SCORES: Each stock has two deterministic pre-scores:
- quality_score_algo: Piotroski F-Score (9 binary financial health tests, 0-100)
- earnings_surprise_score_algo: Beat frequency + magnitude + upcoming earnings bonus (0-100)
USE THE AVERAGE of these two as your starting point for fundamental_score.
You may adjust +/-15 points based on qualitative factors with clear justification.

CRITERIA (prioritized for 3-week horizon):
1. Earnings surprise history (companies that beat estimates tend to have momentum)
2. Revenue growth YoY (>15% preferred)
3. EPS growth
4. Reasonable PE/PEG (not overvalued)
5. Strong ROE and FCF
6. Sector alignment with macro (favored sectors: {data['favored_sectors']})

STOCK DATA ({len(data['stocks_data'])} candidates):
{json.dumps(data['stocks_data'], indent=1, default=str)}

For EACH of the top 20 candidates, provide a fundamental_score (0-100) and classification.

Respond with a JSON object:
{{
    "candidates": [
        {{
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "market_cap": 3000000000000,
            "pe_ratio": 30.5,
            "peg_ratio": 2.1,
            "revenue_growth_yoy": 0.08,
            "eps_growth_yoy": 0.12,
            "roe": 0.45,
            "fcf": 100000000000,
            "earnings_surprise_pct": 5.2,
            "stock_type": "evolution" or "revolution",
            "fundamental_score": 75,
            "rationale": "Strong earnings beat history, solid FCF..."
        }}
    ],
    "screening_summary": "Overall screening summary..."
}}

Return exactly 20 candidates sorted by fundamental_score descending."""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, FundamentalScreenerOutput)

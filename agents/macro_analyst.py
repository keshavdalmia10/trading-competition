"""Agent 1: Macro Analyst — analyzes market regime and sector preferences."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from data.models import MacroAnalysis
from data.sources.fred_api import get_macro_snapshot, get_vix_and_market


class MacroAnalyst(BaseAgent):
    name = "macro_analyst"
    description = "Macroeconomic analyst that determines market regime and sector preferences"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering macro data...")
        macro = get_macro_snapshot()
        market = get_vix_and_market()
        return {"macro_indicators": macro, "market_data": market}

    async def analyze(self, data: dict[str, Any]) -> MacroAnalysis:
        prompt = f"""Analyze the following macroeconomic data and market conditions.
Determine the current market regime and which sectors to favor or avoid
for a 3-week stock trading competition (Feb 9 - Mar 2, 2026).

MACRO INDICATORS:
{json.dumps(data['macro_indicators'], indent=2, default=str)}

MARKET DATA (VIX, S&P 500):
{json.dumps(data['market_data'], indent=2, default=str)}

Respond with a JSON object matching this exact structure:
{{
    "regime": "risk_on" or "risk_off" or "neutral",
    "regime_rationale": "explanation of regime determination",
    "favored_sectors": ["sector1", "sector2", ...],
    "avoided_sectors": ["sector1", ...],
    "macro_score": 0-100 (overall macro health),
    "indicators": [
        {{"name": "indicator name", "value": 0.0, "interpretation": "what it means"}}
    ],
    "key_events": ["upcoming event 1", "event 2"],
    "summary": "2-3 sentence overall macro summary"
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, MacroAnalysis)

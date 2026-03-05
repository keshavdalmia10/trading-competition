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
    provider = "claude"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering macro data...")
        macro = get_macro_snapshot()
        market = get_vix_and_market()
        return {"macro_indicators": macro, "market_data": market}

    async def analyze(self, data: dict[str, Any]) -> MacroAnalysis:
        prompt = f"""Analyze the following macroeconomic data and market conditions.
Determine the current market regime and which sectors to favor (LONG) or avoid (SHORT)
for a LONG/SHORT stock trading competition (Mar 2 - Apr 3, 2026).

CRITICAL CONTEXT:
- US-Iran war ongoing since late Feb 2026. Strait of Hormuz disrupted.
- Oil at $82+ Brent. Defense stocks rallying 3-6%. Airlines down 6-8%.
- 15% universal tariff via Section 122 after Supreme Court struck down IEEPA tariffs.
- Fed at 3.5-3.75%, FOMC meeting March 17-18. Inflation sticky near 3%.
- US-China trade chiefs meeting mid-March. Trump-Xi summit planned April.
- Portfolio can go LONG and SHORT. Identify sectors for both sides.

MACRO INDICATORS:
{json.dumps(data['macro_indicators'], indent=2, default=str)}

MARKET DATA (VIX, S&P 500):
{json.dumps(data['market_data'], indent=2, default=str)}

For favored_sectors: list sectors ideal for LONG positions.
For avoided_sectors: list sectors ideal for SHORT positions.

Respond with a JSON object matching this exact structure:
{{
    "regime": "risk_on" or "risk_off" or "neutral",
    "regime_rationale": "explanation including war, tariffs, Fed impact",
    "favored_sectors": ["Defense", "Energy", "Cybersecurity"],
    "avoided_sectors": ["Airlines", "Travel", "Consumer Discretionary"],
    "macro_score": 0-100,
    "indicators": [
        {{"name": "indicator name", "value": 0.0, "interpretation": "what it means"}}
    ],
    "key_events": ["FOMC Mar 17-18", "US-China trade meeting mid-March"],
    "summary": "2-3 sentence overall macro summary covering war, tariffs, and Fed"
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, MacroAnalysis)

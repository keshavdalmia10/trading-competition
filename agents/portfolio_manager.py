"""Agent 7: Portfolio Manager — synthesizes all analysis into final long/short picks."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import (
    COMPETITION_END,
    COMPETITION_START,
    MAX_PER_SECTOR,
    MAX_PORTFOLIO_STOCKS,
    MAX_SINGLE_WEIGHT,
    SCORING_WEIGHTS,
    SLEEVE_TARGETS,
    STOP_LOSS_DEFAULTS,
    TOTAL_BUYING_POWER,
)
from config.watchlist import TICKER_DIRECTION, TICKER_SLEEVE
from data.models import (
    CatalystHunterOutput,
    FundamentalScreenerOutput,
    MacroAnalysis,
    PortfolioManagerOutput,
    PositionDirection,
    PortfolioSleeve,
    RiskManagerOutput,
    SentimentAnalystOutput,
    TechnicalAnalystOutput,
)


class PortfolioManager(BaseAgent):
    name = "portfolio_manager"
    description = "Portfolio manager synthesizing all analysis into final stock picks"
    provider = "claude"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering all agent outputs...")

        macro: MacroAnalysis | None = self.bus.get("macro_analyst")
        fundamental: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        technical: TechnicalAnalystOutput | None = self.bus.get("technical_analyst")
        catalyst: CatalystHunterOutput | None = self.bus.get("catalyst_hunter")
        sentiment: SentimentAnalystOutput | None = self.bus.get("sentiment_analyst")
        risk: RiskManagerOutput | None = self.bus.get("risk_manager")

        consolidated = {}
        if fundamental:
            for c in fundamental.candidates:
                consolidated[c.ticker] = {
                    "ticker": c.ticker,
                    "name": c.name,
                    "sector": c.sector,
                    "stock_type": c.stock_type.value,
                    "direction": TICKER_DIRECTION.get(c.ticker, "long"),
                    "sleeve": TICKER_SLEEVE.get(c.ticker, "flexible"),
                    "fundamental_score": c.fundamental_score,
                    "fundamental_rationale": c.rationale,
                    "quality_score_algo": c.quality_score_algo,
                    "earnings_surprise_score_algo": c.earnings_surprise_score_algo,
                }

        if technical:
            for t in technical.analyses:
                if t.ticker in consolidated:
                    consolidated[t.ticker]["technical_score"] = t.technical_score
                    consolidated[t.ticker]["technical_rationale"] = t.rationale
                    consolidated[t.ticker]["current_price"] = t.current_price
                    consolidated[t.ticker]["momentum_score_algo"] = t.momentum_score_algo

        if catalyst:
            for c in catalyst.analyses:
                if c.ticker in consolidated:
                    consolidated[c.ticker]["catalyst_score"] = c.catalyst_score
                    consolidated[c.ticker]["catalyst_rationale"] = c.rationale
                    consolidated[c.ticker]["catalysts"] = [
                        cat.model_dump() for cat in c.catalysts
                    ]

        if sentiment:
            for s in sentiment.analyses:
                if s.ticker in consolidated:
                    consolidated[s.ticker]["sentiment_score"] = s.sentiment_score
                    consolidated[s.ticker]["sentiment_rationale"] = s.rationale
                    consolidated[s.ticker]["analyst_consensus"] = s.analyst_consensus

        if risk:
            for r in risk.analyses:
                if r.ticker in consolidated:
                    consolidated[r.ticker]["risk_score"] = r.risk_score
                    consolidated[r.ticker]["risk_rationale"] = r.rationale
                    consolidated[r.ticker]["suggested_weight"] = r.suggested_weight
                    consolidated[r.ticker]["beta"] = r.beta
                    consolidated[r.ticker]["volatility"] = r.volatility_annualized
                    consolidated[r.ticker]["risk_adjusted_score_algo"] = r.risk_adjusted_score_algo

        return {
            "consolidated": list(consolidated.values()),
            "macro_summary": macro.summary if macro else "N/A",
            "macro_regime": macro.regime.value if macro else "neutral",
            "favored_sectors": macro.favored_sectors if macro else [],
            "avoided_sectors": macro.avoided_sectors if macro else [],
            "risk_correlations": [
                cp.model_dump() for cp in risk.high_correlations
            ] if risk else [],
            "risk_diversification": risk.diversification_notes if risk else "N/A",
        }

    async def analyze(self, data: dict[str, Any]) -> PortfolioManagerOutput:
        prompt = f"""You are the Portfolio Manager for a LONG/SHORT trading competition
({COMPETITION_START} to {COMPETITION_END}). Strategy: "War Pairs" with 1.5x margin.

TOTAL BUYING POWER: ${TOTAL_BUYING_POWER:,.0f} (~$80K long, ~$70K short)

Your job is to SELECT ~{MAX_PORTFOLIO_STOCKS} STOCKS (8 long + 8 short), assign weights,
directions, sleeves, and provide investment theses.

SLEEVE ALLOCATION TARGETS:
{json.dumps(SLEEVE_TARGETS, indent=2)}

STOP-LOSS DEFAULTS:
{json.dumps(STOP_LOSS_DEFAULTS, indent=2)}

CONSTRAINTS:
1. ~8 long positions, ~8 short positions (~16 total)
2. Maximum {MAX_PER_SECTOR} stocks per sector (across both sides)
3. No single stock > {MAX_SINGLE_WEIGHT*100}% weight
4. Total long weights + total short weights = 100%
5. Long exposure target: ~53%, Short exposure target: ~47%

SCORING WEIGHTS:
{json.dumps(SCORING_WEIGHTS, indent=2)}

MACRO CONTEXT:
- Regime: {data['macro_regime']}
- Summary: {data['macro_summary']}
- Favored sectors (LONG): {data['favored_sectors']}
- Sectors to SHORT: {data.get('avoided_sectors', [])}

HIGH CORRELATIONS TO WATCH:
{json.dumps(data['risk_correlations'], indent=1, default=str)}

DIVERSIFICATION NOTES: {data['risk_diversification']}

CONSOLIDATED CANDIDATE DATA ({len(data['consolidated'])} stocks):
{json.dumps(data['consolidated'], indent=1, default=str)}

Each candidate has a "direction" (long/short) and "sleeve" (war_long/war_short/flexible).
Respect these assignments.

CONTINGENCY PLANS (include in portfolio_rationale):
- Ceasefire: Close war shorts immediately, trim war longs 50%
- Escalation (oil >$100): Add energy longs, add airline shorts
- FOMC surprise: Adjust rate-sensitive positions

Respond with JSON:
{{
    "stocks": [
        {{
            "ticker": "LMT",
            "name": "Lockheed Martin",
            "sector": "Industrials",
            "stock_type": "evolution",
            "direction": "long",
            "sleeve": "war_long",
            "stop_loss_pct": 15.0,
            "weight_pct": 8.0,
            "composite_score": 82.5,
            "fundamental_score": 75.0,
            "technical_score": 80.0,
            "catalyst_score": 90.0,
            "sentiment_score": 85.0,
            "risk_score": 70.0,
            "entry_strategy": "Buy at market open",
            "exit_strategy": "Hold unless -15% stop hit or ceasefire announced",
            "thesis": "Top defense contractor directly benefiting from US-Iran war..."
        }}
    ],
    "portfolio_rationale": "War Pairs strategy rationale with contingency plans...",
    "long_count": 8,
    "short_count": 8,
    "long_exposure_pct": 53.0,
    "short_exposure_pct": 47.0,
    "sector_breakdown": {{"Industrials": 4, "Energy": 3, "Technology": 4}},
    "expected_portfolio_beta": 0.2,
    "key_risks": ["ceasefire reversal", "oil collapse", "margin call in crash"],
    "key_catalysts": ["oil >$100", "FOMC Mar 17-18", "US-China mid-March meeting"]
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, PortfolioManagerOutput)

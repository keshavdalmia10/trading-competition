"""Agent 7: Portfolio Manager (Orchestrator) — synthesizes all analysis into final picks."""

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
    MIN_EVOLUTION,
    MIN_REVOLUTION,
    SCORING_WEIGHTS,
)
from data.models import (
    CatalystHunterOutput,
    FundamentalScreenerOutput,
    MacroAnalysis,
    PortfolioManagerOutput,
    RiskManagerOutput,
    SentimentAnalystOutput,
    TechnicalAnalystOutput,
)


class PortfolioManager(BaseAgent):
    name = "portfolio_manager"
    description = "Portfolio manager synthesizing all analysis into final stock picks"
    provider = "deepseek"

    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering all agent outputs...")

        macro: MacroAnalysis | None = self.bus.get("macro_analyst")
        fundamental: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        technical: TechnicalAnalystOutput | None = self.bus.get("technical_analyst")
        catalyst: CatalystHunterOutput | None = self.bus.get("catalyst_hunter")
        sentiment: SentimentAnalystOutput | None = self.bus.get("sentiment_analyst")
        risk: RiskManagerOutput | None = self.bus.get("risk_manager")

        # Build consolidated view per ticker
        consolidated = {}
        if fundamental:
            for c in fundamental.candidates:
                consolidated[c.ticker] = {
                    "ticker": c.ticker,
                    "name": c.name,
                    "sector": c.sector,
                    "stock_type": c.stock_type.value,
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
            "risk_correlations": [
                cp.model_dump() for cp in risk.high_correlations
            ] if risk else [],
            "risk_diversification": risk.diversification_notes if risk else "N/A",
        }

    async def analyze(self, data: dict[str, Any]) -> PortfolioManagerOutput:
        prompt = f"""You are the Portfolio Manager for a 3-WEEK college stock trading competition
({COMPETITION_START} to {COMPETITION_END}).

Your job is to SELECT EXACTLY {MAX_PORTFOLIO_STOCKS} STOCKS from the candidates below,
assign weights, and provide investment theses.

CONSTRAINTS (MUST be followed):
1. Exactly {MAX_PORTFOLIO_STOCKS} stocks
2. Maximum {MAX_PER_SECTOR} stocks per sector
3. At least {MIN_EVOLUTION} "evolution" stocks (established companies innovating)
4. At least {MIN_REVOLUTION} "revolution" stocks (disruptive companies)
5. No single stock > {MAX_SINGLE_WEIGHT*100}% weight
6. Total weights must sum to 100%

SCORING WEIGHTS:
{json.dumps(SCORING_WEIGHTS, indent=2)}

MACRO CONTEXT:
- Regime: {data['macro_regime']}
- Summary: {data['macro_summary']}
- Favored sectors: {data['favored_sectors']}

HIGH CORRELATIONS TO WATCH:
{json.dumps(data['risk_correlations'], indent=1, default=str)}

DIVERSIFICATION NOTES: {data['risk_diversification']}

CONSOLIDATED CANDIDATE DATA ({len(data['consolidated'])} stocks):
{json.dumps(data['consolidated'], indent=1, default=str)}

SELECT YOUR TOP {MAX_PORTFOLIO_STOCKS}. For each, compute a composite score using the weights above.

ALGORITHMIC PRE-SCORES: Each candidate includes deterministic algo scores
(momentum_score_algo, quality_score_algo, earnings_surprise_score_algo, risk_adjusted_score_algo).
These are formula-based anchors. If any LLM-assigned score deviates by >15 points from its
algo counterpart, flag it in the stock's rationale and explain why.

Consider:
- Highest composite scores should generally be selected
- But also ensure sector diversification and evo/revo balance
- Avoid highly correlated pairs (pick the better one)
- Favor stocks with catalysts IN the competition window
- In a competition, moderate-high risk is acceptable for potential returns

Respond with JSON:
{{
    "stocks": [
        {{
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "stock_type": "evolution",
            "weight_pct": 12.0,
            "composite_score": 82.5,
            "fundamental_score": 75.0,
            "technical_score": 80.0,
            "catalyst_score": 90.0,
            "sentiment_score": 70.0,
            "risk_score": 65.0,
            "entry_strategy": "Buy at market open on Monday",
            "exit_strategy": "Hold through competition unless -10% stop loss hit",
            "thesis": "Strong earnings catalyst with bullish technical setup..."
        }}
    ],
    "portfolio_rationale": "Overall portfolio construction rationale...",
    "evolution_count": 5,
    "revolution_count": 5,
    "sector_breakdown": {{"Technology": 3, "Healthcare": 2, ...}},
    "expected_portfolio_beta": 1.15,
    "key_risks": ["risk1", "risk2"],
    "key_catalysts": ["catalyst1", "catalyst2"]
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, PortfolioManagerOutput)

"""Tests for agent modules."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from data.models import (
    MacroAnalysis,
    MarketRegime,
    FundamentalScreenerOutput,
    FundamentalData,
    StockType,
    PositionDirection,
    PortfolioSleeve,
    PortfolioStock,
    PortfolioManagerOutput,
    ScoringRow,
)
from orchestrator.message_bus import MessageBus


class TestMessageBus(unittest.TestCase):
    """Tests for the message bus."""

    def test_publish_and_get(self):
        bus = MessageBus()
        bus.publish("test_key", {"data": 123})
        result = bus.get("test_key")
        self.assertEqual(result, {"data": 123})

    def test_get_missing_returns_none(self):
        bus = MessageBus()
        self.assertIsNone(bus.get("nonexistent"))

    def test_has_key(self):
        bus = MessageBus()
        bus.publish("exists", True)
        self.assertTrue(bus.has("exists"))
        self.assertFalse(bus.has("missing"))

    def test_keys(self):
        bus = MessageBus()
        bus.publish("a", 1)
        bus.publish("b", 2)
        self.assertEqual(sorted(bus.keys()), ["a", "b"])

    def test_get_all(self):
        bus = MessageBus()
        bus.publish("x", 10)
        bus.publish("y", 20)
        all_data = bus.get_all()
        self.assertEqual(all_data, {"x": 10, "y": 20})


class TestBaseAgent(unittest.TestCase):
    """Tests for the base agent JSON parsing."""

    def test_parse_json_with_code_fence(self):
        from agents.base_agent import BaseAgent

        class DummyAgent(BaseAgent):
            name = "dummy"
            provider = "claude"
            async def gather_data(self):
                return {}
            async def analyze(self, data):
                pass

        bus = MessageBus()
        with patch.object(BaseAgent, '_build_client', return_value=MagicMock()):
            agent = DummyAgent(bus)

        text = '''Here is the analysis:
```json
{
    "regime": "risk_on",
    "regime_rationale": "test",
    "favored_sectors": ["Technology"],
    "avoided_sectors": [],
    "macro_score": 75,
    "indicators": [],
    "key_events": [],
    "summary": "Test summary"
}
```'''
        result = agent._parse_json_response(text, MacroAnalysis)
        self.assertEqual(result.regime, MarketRegime.RISK_ON)
        self.assertEqual(result.macro_score, 75)

    def test_parse_json_raw(self):
        from agents.base_agent import BaseAgent

        class DummyAgent(BaseAgent):
            name = "dummy"
            provider = "claude"
            async def gather_data(self):
                return {}
            async def analyze(self, data):
                pass

        bus = MessageBus()
        with patch.object(BaseAgent, '_build_client', return_value=MagicMock()):
            agent = DummyAgent(bus)

        text = '{"regime": "neutral", "regime_rationale": "x", "favored_sectors": [], "avoided_sectors": [], "macro_score": 50, "indicators": [], "summary": "s"}'
        result = agent._parse_json_response(text, MacroAnalysis)
        self.assertEqual(result.regime, MarketRegime.NEUTRAL)


class TestModels(unittest.TestCase):
    """Tests for Pydantic models."""

    def test_macro_analysis_validation(self):
        ma = MacroAnalysis(
            regime=MarketRegime.RISK_ON,
            regime_rationale="Strong economy",
            favored_sectors=["Technology", "Healthcare"],
            avoided_sectors=["Energy"],
            macro_score=75.0,
            indicators=[],
            summary="Bullish environment",
        )
        self.assertEqual(ma.regime, MarketRegime.RISK_ON)
        self.assertEqual(ma.macro_score, 75.0)

    def test_fundamental_data_validation(self):
        fd = FundamentalData(
            ticker="AAPL",
            name="Apple Inc",
            sector="Technology",
            stock_type=StockType.EVOLUTION,
            fundamental_score=80.0,
            rationale="Strong fundamentals",
        )
        self.assertEqual(fd.ticker, "AAPL")
        self.assertEqual(fd.stock_type, StockType.EVOLUTION)

    def test_score_bounds(self):
        with self.assertRaises(Exception):
            FundamentalData(
                ticker="X",
                name="X",
                sector="X",
                stock_type=StockType.EVOLUTION,
                fundamental_score=150.0,  # Over 100, should fail
                rationale="X",
            )


class TestRound2Models(unittest.TestCase):
    """Tests for Round 2 long/short model additions."""

    def test_position_direction_enum(self):
        self.assertEqual(PositionDirection.LONG.value, "long")
        self.assertEqual(PositionDirection.SHORT.value, "short")

    def test_portfolio_sleeve_enum(self):
        self.assertEqual(PortfolioSleeve.WAR_LONG.value, "war_long")
        self.assertEqual(PortfolioSleeve.WAR_SHORT.value, "war_short")
        self.assertEqual(PortfolioSleeve.FLEXIBLE.value, "flexible")

    def test_portfolio_stock_has_direction_and_sleeve(self):
        stock = PortfolioStock(
            ticker="LMT", name="Lockheed Martin", sector="Industrials",
            stock_type=StockType.EVOLUTION, direction=PositionDirection.LONG,
            sleeve=PortfolioSleeve.WAR_LONG, stop_loss_pct=15.0,
            weight_pct=8.0, composite_score=80.0, fundamental_score=70.0,
            technical_score=75.0, catalyst_score=85.0, sentiment_score=80.0,
            risk_score=65.0, entry_strategy="Buy at open",
            exit_strategy="Hold unless -15% stop hit", thesis="Defense war play",
        )
        self.assertEqual(stock.direction, PositionDirection.LONG)
        self.assertEqual(stock.sleeve, PortfolioSleeve.WAR_LONG)
        self.assertEqual(stock.stop_loss_pct, 15.0)

    def test_portfolio_stock_short(self):
        stock = PortfolioStock(
            ticker="AAL", name="American Airlines", sector="Industrials",
            stock_type=StockType.EVOLUTION, direction=PositionDirection.SHORT,
            sleeve=PortfolioSleeve.WAR_SHORT, stop_loss_pct=25.0,
            weight_pct=8.0, composite_score=75.0, fundamental_score=40.0,
            technical_score=30.0, catalyst_score=80.0, sentiment_score=25.0,
            risk_score=60.0, entry_strategy="Short at open",
            exit_strategy="Cover if rises 25%", thesis="Airlines crushed",
        )
        self.assertEqual(stock.direction, PositionDirection.SHORT)

    def test_portfolio_manager_output_has_long_short_fields(self):
        output = PortfolioManagerOutput(
            stocks=[], portfolio_rationale="Test",
            long_count=8, short_count=8,
            long_exposure_pct=53.0, short_exposure_pct=47.0,
            sector_breakdown={"Industrials": 3},
            expected_portfolio_beta=0.2,
            key_risks=["war ends"], key_catalysts=["oil spike"],
        )
        self.assertEqual(output.long_count, 8)
        self.assertEqual(output.short_count, 8)

    def test_scoring_row_has_direction(self):
        row = ScoringRow(
            ticker="LMT", name="Lockheed Martin", sector="Industrials",
            stock_type=StockType.EVOLUTION, direction=PositionDirection.LONG,
            fundamental_score=70.0, technical_score=75.0, catalyst_score=85.0,
            sentiment_score=80.0, risk_score=65.0, composite_score=75.0,
        )
        self.assertEqual(row.direction, PositionDirection.LONG)


if __name__ == "__main__":
    unittest.main()

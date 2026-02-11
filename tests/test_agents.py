"""Tests for agent modules."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from data.models import (
    MacroAnalysis,
    MarketRegime,
    FundamentalScreenerOutput,
    FundamentalData,
    StockType,
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
            provider = "deepseek"
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
            provider = "deepseek"
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


if __name__ == "__main__":
    unittest.main()

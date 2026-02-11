"""Tests for algorithmic pre-scoring functions."""

import unittest

from tools.algorithmic_scores import (
    compute_earnings_surprise_score,
    compute_momentum_score,
    compute_quality_score,
    compute_risk_adjusted_score,
)


class TestMomentumScore(unittest.TestCase):

    def test_empty_returns_neutral(self):
        self.assertEqual(compute_momentum_score({}), 50.0)

    def test_perfect_bullish_setup(self):
        indicators = {
            "rsi_14": 52.5,
            "macd_signal": "bullish",
            "macd_value": 2.0,
            "macd_signal_value": 1.0,
            "current_price": 100,
            "above_sma_20": True,
            "above_sma_50": True,
            "above_sma_200": True,
            "volume_trend": "increasing",
            "bollinger_position": "upper",
        }
        score = compute_momentum_score(indicators)
        self.assertGreaterEqual(score, 90)
        self.assertLessEqual(score, 100)

    def test_bearish_setup(self):
        indicators = {
            "rsi_14": 80,
            "macd_signal": "bearish",
            "above_sma_20": False,
            "above_sma_50": False,
            "above_sma_200": False,
            "volume_trend": "decreasing",
            "bollinger_position": "above_upper",
        }
        score = compute_momentum_score(indicators)
        self.assertLess(score, 30)

    def test_neutral_setup(self):
        indicators = {
            "rsi_14": 50,
            "macd_signal": "neutral",
            "above_sma_20": True,
            "above_sma_50": False,
            "volume_trend": "stable",
        }
        score = compute_momentum_score(indicators)
        self.assertGreater(score, 40)
        self.assertLess(score, 80)

    def test_overbought_rsi_penalty(self):
        base = {"rsi_14": 55}
        overbought = {"rsi_14": 85}
        self.assertGreater(
            compute_momentum_score(base),
            compute_momentum_score(overbought),
        )

    def test_score_bounds(self):
        """Score should always be 0-100."""
        extreme_bull = {
            "rsi_14": 52.5, "macd_signal": "bullish", "macd_value": 100,
            "macd_signal_value": 0, "current_price": 1,
            "above_sma_20": True, "above_sma_50": True, "above_sma_200": True,
            "volume_trend": "increasing", "bollinger_position": "upper",
        }
        self.assertLessEqual(compute_momentum_score(extreme_bull), 100)

        extreme_bear = {
            "rsi_14": 95, "macd_signal": "bearish",
            "above_sma_20": False, "above_sma_50": False, "above_sma_200": False,
            "volume_trend": "decreasing", "bollinger_position": "above_upper",
        }
        self.assertGreaterEqual(compute_momentum_score(extreme_bear), 0)

    def test_deterministic(self):
        """Same input always produces same output."""
        indicators = {"rsi_14": 55, "macd_signal": "bullish", "above_sma_20": True}
        score1 = compute_momentum_score(indicators)
        score2 = compute_momentum_score(indicators)
        self.assertEqual(score1, score2)


class TestQualityScore(unittest.TestCase):

    def test_empty_returns_neutral(self):
        self.assertEqual(compute_quality_score({}), 50.0)

    def test_perfect_quality(self):
        data = {
            "net_income_current": 1_000_000,
            "total_assets_current": 10_000_000,
            "total_assets_prior": 9_000_000,
            "operating_cash_flow": 1_500_000,
            "total_debt_current": 1_000_000,
            "total_debt_prior": 1_500_000,
            "current_assets": 5_000_000,
            "current_liabilities": 2_000_000,
            "current_assets_prior": 4_000_000,
            "current_liabilities_prior": 2_500_000,
            "shares_outstanding_current": 100_000,
            "shares_outstanding_prior": 100_000,
            "gross_profit_current": 4_000_000,
            "gross_profit_prior": 3_000_000,
            "total_revenue_current": 8_000_000,
            "total_revenue_prior": 7_000_000,
        }
        score = compute_quality_score(data)
        self.assertEqual(score, 100.0)  # 9/9 tests pass

    def test_poor_quality(self):
        data = {
            "net_income_current": -500_000,
            "total_assets_current": 10_000_000,
            "total_assets_prior": 10_000_000,
            "operating_cash_flow": -200_000,
            "total_debt_current": 5_000_000,
            "total_debt_prior": 3_000_000,
            "current_assets": 2_000_000,
            "current_liabilities": 4_000_000,
            "current_assets_prior": 3_000_000,
            "current_liabilities_prior": 3_000_000,
            "shares_outstanding_current": 150_000,
            "shares_outstanding_prior": 100_000,
            "gross_profit_current": 1_000_000,
            "gross_profit_prior": 2_000_000,
            "total_revenue_current": 5_000_000,
            "total_revenue_prior": 6_000_000,
        }
        score = compute_quality_score(data)
        self.assertLess(score, 20)

    def test_partial_data(self):
        data = {"net_income_current": 1_000_000}
        score = compute_quality_score(data)
        self.assertEqual(score, 100.0)  # 1/1 test passes

    def test_score_bounds(self):
        data = {"net_income_current": -1}
        score = compute_quality_score(data)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class TestEarningsSurpriseScore(unittest.TestCase):

    def test_empty_returns_neutral(self):
        self.assertEqual(compute_earnings_surprise_score([], False), 50.0)

    def test_perfect_beats(self):
        history = [
            {"surprisePercent": 10},
            {"surprisePercent": 8},
            {"surprisePercent": 12},
            {"surprisePercent": 9},
        ]
        score = compute_earnings_surprise_score(history, has_earnings_in_window=True)
        self.assertGreaterEqual(score, 90)

    def test_all_misses(self):
        history = [
            {"surprisePercent": -5},
            {"surprisePercent": -3},
            {"surprisePercent": -8},
            {"surprisePercent": -2},
        ]
        score = compute_earnings_surprise_score(history, has_earnings_in_window=False)
        self.assertLess(score, 20)

    def test_earnings_window_bonus(self):
        history = [{"surprisePercent": 5}, {"surprisePercent": 5}]
        without = compute_earnings_surprise_score(history, has_earnings_in_window=False)
        with_window = compute_earnings_surprise_score(history, has_earnings_in_window=True)
        self.assertEqual(with_window - without, 15.0)

    def test_computed_surprise_from_actual_estimate(self):
        history = [{"epsActual": 1.10, "epsEstimate": 1.00}]
        score = compute_earnings_surprise_score(history, False)
        self.assertGreater(score, 50)

    def test_score_bounds(self):
        huge_beats = [{"surprisePercent": 50}] * 4
        self.assertLessEqual(compute_earnings_surprise_score(huge_beats, True), 100)
        huge_misses = [{"surprisePercent": -50}] * 4
        self.assertGreaterEqual(compute_earnings_surprise_score(huge_misses, False), 0)


class TestRiskAdjustedScore(unittest.TestCase):

    def test_empty_returns_neutral(self):
        self.assertEqual(compute_risk_adjusted_score({}), 50.0)

    def test_ideal_profile(self):
        metrics = {
            "sharpe_ratio": 2.5,
            "max_drawdown_90d": -0.03,
            "beta": 1.25,
            "value_at_risk_95": -0.005,
        }
        score = compute_risk_adjusted_score(metrics)
        self.assertGreaterEqual(score, 90)

    def test_poor_profile(self):
        metrics = {
            "sharpe_ratio": -0.5,
            "max_drawdown_90d": -0.35,
            "beta": 3.0,
            "value_at_risk_95": -0.06,
        }
        score = compute_risk_adjusted_score(metrics)
        self.assertLess(score, 25)

    def test_beta_sweet_spot(self):
        base = {"beta": 1.25}
        extreme = {"beta": 3.0}
        self.assertGreater(
            compute_risk_adjusted_score(base),
            compute_risk_adjusted_score(extreme),
        )

    def test_score_bounds(self):
        perfect = {"sharpe_ratio": 5, "max_drawdown_90d": 0, "beta": 1.25, "value_at_risk_95": 0}
        self.assertLessEqual(compute_risk_adjusted_score(perfect), 100)
        worst = {"sharpe_ratio": -5, "max_drawdown_90d": -0.9, "beta": 10, "value_at_risk_95": -0.2}
        self.assertGreaterEqual(compute_risk_adjusted_score(worst), 0)

    def test_deterministic(self):
        metrics = {"sharpe_ratio": 1.0, "max_drawdown_90d": -0.1, "beta": 1.2, "value_at_risk_95": -0.02}
        self.assertEqual(
            compute_risk_adjusted_score(metrics),
            compute_risk_adjusted_score(metrics),
        )


if __name__ == "__main__":
    unittest.main()

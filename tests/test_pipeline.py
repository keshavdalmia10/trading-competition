"""Tests for pipeline orchestration and tools."""

import unittest

from tools.scoring import compute_composite_score, normalize_score
from tools.position_sizing import inverse_volatility_weights, score_based_weights, blend_weights


class TestScoring(unittest.TestCase):
    """Tests for scoring module."""

    def test_composite_score_calculation(self):
        # Weights: fundamental=0.15, technical=0.25, catalyst=0.25, sentiment=0.15, risk=0.20
        score = compute_composite_score(
            fundamental=80,
            technical=70,
            catalyst=90,
            sentiment=60,
            risk=75,
        )
        expected = 80 * 0.15 + 70 * 0.25 + 90 * 0.25 + 60 * 0.15 + 75 * 0.20
        self.assertAlmostEqual(score, expected, places=1)

    def test_composite_score_bounds(self):
        score = compute_composite_score(100, 100, 100, 100, 100)
        self.assertLessEqual(score, 100)

        score = compute_composite_score(0, 0, 0, 0, 0)
        self.assertGreaterEqual(score, 0)

    def test_normalize_score(self):
        self.assertEqual(normalize_score(50, 0, 100), 50.0)
        self.assertEqual(normalize_score(0, 0, 100), 0.0)
        self.assertEqual(normalize_score(100, 0, 100), 100.0)

    def test_normalize_score_same_range(self):
        self.assertEqual(normalize_score(5, 5, 5), 50.0)


class TestPositionSizing(unittest.TestCase):
    """Tests for position sizing module."""

    def test_inverse_volatility_weights_sum_to_one(self):
        vols = {"AAPL": 0.25, "TSLA": 0.60, "MSFT": 0.20}
        weights = inverse_volatility_weights(vols)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)
        # Lower vol should get higher weight
        self.assertGreater(weights["MSFT"], weights["TSLA"])

    def test_score_based_weights_sum_to_one(self):
        scores = {"AAPL": 80, "TSLA": 60, "MSFT": 90}
        weights = score_based_weights(scores)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)

    def test_weight_capping(self):
        scores = {"AAPL": 95, "TSLA": 2, "MSFT": 3}
        weights = score_based_weights(scores)
        for w in weights.values():
            self.assertLessEqual(w, 0.15 + 0.01)  # Max 15% with small rounding tolerance

    def test_blend_weights(self):
        score_w = {"AAPL": 0.5, "TSLA": 0.5}
        vol_w = {"AAPL": 0.7, "TSLA": 0.3}
        blended = blend_weights(score_w, vol_w, score_blend=0.6)
        self.assertAlmostEqual(sum(blended.values()), 1.0, places=2)

    def test_empty_weights(self):
        self.assertEqual(inverse_volatility_weights({}), {})
        self.assertEqual(score_based_weights({}), {})


class TestWatchlist(unittest.TestCase):
    """Tests for watchlist configuration."""

    def test_all_tickers_deduplicated(self):
        from config.watchlist import ALL_TICKERS
        self.assertEqual(len(ALL_TICKERS), len(set(ALL_TICKERS)))

    def test_classification_covers_all(self):
        from config.watchlist import ALL_TICKERS, TICKER_CLASSIFICATION
        for ticker in ALL_TICKERS:
            self.assertIn(ticker, TICKER_CLASSIFICATION)

    def test_min_universe_size(self):
        from config.watchlist import ALL_TICKERS
        self.assertGreaterEqual(len(ALL_TICKERS), 30)


if __name__ == "__main__":
    unittest.main()

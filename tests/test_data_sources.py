"""Tests for data source modules."""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from config.settings import SCREENER_MIN_MARKET_CAP


class TestYahooFinance(unittest.TestCase):
    """Tests for yahoo_finance.py data wrapper."""

    @patch("data.sources.yahoo_finance.yf.Ticker")
    def test_get_stock_info_returns_dict(self, mock_ticker):
        mock_ticker.return_value.info = {
            "shortName": "Apple Inc",
            "sector": "Technology",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 30.5,
            "currentPrice": 195.0,
        }
        from data.sources.yahoo_finance import get_stock_info
        result = get_stock_info("AAPL")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["name"], "Apple Inc")
        self.assertEqual(result["sector"], "Technology")

    @patch("data.sources.yahoo_finance.yf.Ticker")
    def test_get_price_history_returns_dataframe(self, mock_ticker):
        dates = pd.date_range("2025-01-01", periods=30)
        mock_df = pd.DataFrame({
            "Open": range(30),
            "High": range(30),
            "Low": range(30),
            "Close": range(30),
            "Volume": [1000] * 30,
        }, index=dates)
        mock_ticker.return_value.history.return_value = mock_df

        from data.sources.yahoo_finance import get_price_history
        result = get_price_history("AAPL", days=30)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    @patch("data.sources.yahoo_finance.yf.Ticker")
    def test_get_stock_info_handles_error(self, mock_ticker):
        mock_ticker.return_value.info = None
        from data.sources.yahoo_finance import get_stock_info
        result = get_stock_info("INVALID")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["ticker"], "INVALID")


class TestFredApi(unittest.TestCase):
    """Tests for fred_api.py wrapper."""

    @patch("data.sources.fred_api.FRED_API_KEY", "")
    def test_get_series_no_key_returns_empty(self):
        from data.sources.fred_api import get_series
        result = get_series("FEDFUNDS")
        self.assertEqual(result, [])

    def test_get_macro_snapshot_returns_dict(self):
        from data.sources.fred_api import get_macro_snapshot
        result = get_macro_snapshot()
        self.assertIsInstance(result, dict)
        self.assertIn("fed_funds_rate", result)
        self.assertIn("yield_curve_10y2y", result)


class TestNewsApi(unittest.TestCase):
    """Tests for news_api.py wrapper."""

    @patch("data.sources.news_api.NEWSAPI_KEY", "")
    def test_get_headlines_no_key_returns_empty(self):
        from data.sources.news_api import get_headlines
        result = get_headlines("AAPL")
        self.assertEqual(result, [])


class TestFinnhub(unittest.TestCase):
    """Tests for finnhub_client.py wrapper."""

    @patch("data.sources.finnhub_client.FINNHUB_KEY", "")
    def test_get_company_news_no_key_returns_empty(self):
        from data.sources.finnhub_client import get_company_news
        result = get_company_news("AAPL")
        self.assertEqual(result, [])


class TestStockScreener(unittest.TestCase):
    """Tests for stock_screener.py."""

    def test_get_full_universe_returns_list(self):
        from data.sources.stock_screener import get_full_universe
        result = get_full_universe(include_screener=False)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 30)
        self.assertIn("AAPL", result)
        self.assertIn("TSLA", result)


if __name__ == "__main__":
    unittest.main()

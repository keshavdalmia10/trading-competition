"""Tests for Polymarket data source client."""

import json
from unittest.mock import patch, MagicMock

import pytest


def test_search_markets_returns_parsed_results():
    from data.sources.polymarket import PolymarketClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "123",
            "question": "Will there be a ceasefire in Iran by April?",
            "outcomePrices": "[0.15, 0.85]",
            "outcomes": "[\"Yes\", \"No\"]",
            "volume": "500000",
            "liquidity": "120000",
            "endDate": "2026-04-30",
            "active": True,
            "slug": "ceasefire-iran-april",
        }
    ]

    with patch("data.sources.polymarket.requests.get", return_value=mock_response):
        client = PolymarketClient()
        results = client.search_markets("ceasefire")

    assert len(results) == 1
    assert results[0]["question"] == "Will there be a ceasefire in Iran by April?"
    assert results[0]["yes_price"] == 0.15
    assert results[0]["no_price"] == 0.85
    assert results[0]["volume"] == 500000.0


def test_search_markets_handles_api_failure():
    from data.sources.polymarket import PolymarketClient, _cache_path

    # Clear any cached result from previous tests
    cache_file = _cache_path("search_ceasefire_20")
    if cache_file.exists():
        cache_file.unlink()

    with patch("data.sources.polymarket.requests.get", side_effect=Exception("API down")):
        client = PolymarketClient()
        results = client.search_markets("ceasefire")

    assert results == []


def test_get_war_relevant_markets_groups_by_category():
    from data.sources.polymarket import PolymarketClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "1",
            "question": "Iran ceasefire before May?",
            "description": "",
            "outcomePrices": "[0.20, 0.80]",
            "outcomes": "[\"Yes\", \"No\"]",
            "volume": "300000",
            "liquidity": "80000",
            "endDate": "2026-05-01",
            "active": True,
            "slug": "iran-ceasefire-may",
        }
    ]

    with patch("data.sources.polymarket.requests.get", return_value=mock_response):
        client = PolymarketClient()
        result = client.get_war_relevant_markets()

    assert "ceasefire" in result
    assert len(result["ceasefire"]) >= 1
    assert result["ceasefire"][0]["yes_price"] == 0.20

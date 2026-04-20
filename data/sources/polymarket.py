"""Polymarket Gamma API client for event probability tracking."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests
from loguru import logger

from config.settings import (
    CACHE_DIR,
    POLYMARKET_BASE_URL,
    POLYMARKET_CACHE_TTL_MINUTES,
    POLYMARKET_CATEGORIES,
)


def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(" ", "_")[:80]
    return Path(CACHE_DIR) / f"polymarket_{safe_key}.json"


def _read_cache(key: str) -> Optional[Any]:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(minutes=POLYMARKET_CACHE_TTL_MINUTES):
            return None
        return data.get("payload")
    except Exception:
        return None


def _write_cache(key: str, payload: Any) -> None:
    try:
        path = _cache_path(key)
        data = {"_cached_at": datetime.now().isoformat(), "payload": payload}
        path.write_text(json.dumps(data, default=str))
    except Exception as e:
        logger.warning(f"Failed to write Polymarket cache: {e}")


class PolymarketClient:
    """Client for Polymarket Gamma API (no auth required)."""

    def __init__(self) -> None:
        self.base_url = POLYMARKET_BASE_URL

    def search_markets(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search Polymarket for active markets matching a query string."""
        cache_key = f"search_{query}_{limit}"
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

        try:
            resp = requests.get(
                f"{self.base_url}/markets",
                params={"tag": query, "limit": limit, "active": True},
                timeout=15,
            )
            if resp.status_code != 200:
                resp = requests.get(
                    f"{self.base_url}/markets",
                    params={"limit": 100, "active": True},
                    timeout=15,
                )
            markets = resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.error(f"Polymarket API error for query '{query}': {e}")
            return []

        results = []
        for m in markets:
            question = m.get("question", "")

            try:
                outcome_prices = json.loads(m.get("outcomePrices", "[]"))
            except (json.JSONDecodeError, TypeError):
                outcome_prices = []

            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else None
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else None

            if yes_price is None:
                continue

            results.append({
                "id": m.get("id", ""),
                "question": question,
                "slug": m.get("slug", ""),
                "yes_price": yes_price,
                "no_price": no_price,
                "volume": float(m.get("volume", 0) or 0),
                "liquidity": float(m.get("liquidity", 0) or 0),
                "end_date": m.get("endDate", ""),
                "active": m.get("active", True),
            })

        _write_cache(cache_key, results)
        return results

    def get_war_relevant_markets(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch markets for all strategy-relevant categories defined in settings."""
        cache_key = "war_relevant_all"
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

        try:
            resp = requests.get(
                f"{self.base_url}/markets",
                params={
                    "limit": 500,
                    "active": True,
                    "closed": False,
                    "order": "volume",
                    "ascending": False,
                },
                timeout=25,
            )
            all_markets = resp.json() if resp.status_code == 200 else []
            logger.info(f"[polymarket] Fetched {len(all_markets)} active markets")
        except Exception as e:
            logger.error(f"Polymarket bulk fetch failed: {e}")
            return {}

        categorized: dict[str, list[dict[str, Any]]] = {}

        for category, config in POLYMARKET_CATEGORIES.items():
            keywords = config["keywords"]
            matches = []

            for m in all_markets:
                question = (m.get("question", "") + " " + m.get("description", "")).lower()
                if any(kw.lower() in question for kw in keywords):
                    try:
                        outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                    except (json.JSONDecodeError, TypeError):
                        continue

                    yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else None
                    if yes_price is None:
                        continue
                    no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else None

                    matches.append({
                        "id": m.get("id", ""),
                        "question": m.get("question", ""),
                        "slug": m.get("slug", ""),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "volume": float(m.get("volume", 0) or 0),
                        "liquidity": float(m.get("liquidity", 0) or 0),
                        "end_date": m.get("endDate", ""),
                    })

            matches.sort(key=lambda x: x["volume"], reverse=True)
            categorized[category] = matches[:5]

        _write_cache(cache_key, categorized)
        return categorized

    def get_summary_for_agents(self) -> dict[str, Any]:
        """Build a concise summary dict suitable for injecting into agent prompts."""
        raw = self.get_war_relevant_markets()
        summary: dict[str, Any] = {"categories": {}, "raw_markets": raw}

        highest_risk_prob = 0.0
        highest_risk_cat = "none"

        for category, markets in raw.items():
            config = POLYMARKET_CATEGORIES.get(category, {})
            if not markets:
                summary["categories"][category] = {
                    "top_market": "No active markets found",
                    "probability": None,
                    "market_count": 0,
                    "impact": config.get("impact", ""),
                }
                continue

            top = markets[0]
            prob = top["yes_price"]

            summary["categories"][category] = {
                "top_market": top["question"],
                "probability": prob,
                "market_count": len(markets),
                "impact": config.get("impact", ""),
                "affected_sleeves": config.get("affected_sleeves", []),
                "all_markets": [
                    {"question": m["question"], "probability": m["yes_price"]}
                    for m in markets
                ],
            }

            if category in ("ceasefire", "war_escalation") and prob > highest_risk_prob:
                highest_risk_prob = prob
                highest_risk_cat = category

        summary["highest_risk_event"] = highest_risk_cat
        summary["highest_risk_probability"] = highest_risk_prob
        return summary

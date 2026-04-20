# Polymarket Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Polymarket event probabilities as a data source feeding into Catalyst Hunter, Sentiment Analyst, Risk Manager, and Portfolio Manager agents.

**Architecture:** One new data source file (`data/sources/polymarket.py`) using the Polymarket Gamma API (no auth). A config dict in `settings.py` maps market slugs to strategy categories. Four existing agents get Polymarket context injected into their `gather_data()` and LLM prompts.

**Tech Stack:** `requests` (already in requirements), Polymarket Gamma API (`https://gamma-api.polymarket.com`), existing JSON file cache pattern.

---

### Task 1: Polymarket Client — Data Source

**Files:**
- Create: `data/sources/polymarket.py`
- Modify: `config/settings.py` (add market slug config)
- Test: `tests/test_polymarket.py`

**Step 1: Add Polymarket config to settings.py**

Add after the `SCREENER_*` constants at the bottom of `config/settings.py`:

```python
# ── Polymarket Event Tracking ───────────────────────────────────────────
POLYMARKET_BASE_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CACHE_TTL_MINUTES = 10

# Maps strategy-relevant categories to Polymarket search keywords and affected tickers.
# The client searches market titles for these keywords and returns matching markets.
POLYMARKET_CATEGORIES = {
    "ceasefire": {
        "keywords": ["ceasefire", "peace deal", "iran peace", "iran negotiate", "de-escalation"],
        "impact": "Ceasefire reverses entire war sleeve — close war shorts, trim war longs 50%",
        "affected_sleeves": ["war_long", "war_short"],
        "risk_direction": "war_reversal",
    },
    "war_escalation": {
        "keywords": ["iran war", "strait of hormuz", "military strike", "iran attack", "iran conflict"],
        "impact": "Escalation amplifies war thesis — defense/energy up, airlines/consumer down",
        "affected_sleeves": ["war_long", "war_short"],
        "risk_direction": "war_amplify",
    },
    "oil_energy": {
        "keywords": ["oil price", "OPEC", "crude oil", "oil $100", "petroleum"],
        "impact": "Oil spike benefits energy longs (XOM/CVX/OXY), crushes airline shorts (AAL/DAL/UAL)",
        "affected_sleeves": ["war_long", "war_short"],
        "risk_direction": "oil_spike",
    },
    "tariffs": {
        "keywords": ["tariff", "trade war", "import duty", "IEEPA", "customs"],
        "impact": "Tariff escalation hurts consumer/retail, adds pressure on shorts like NKE",
        "affected_sleeves": ["flexible"],
        "risk_direction": "tariff_risk",
    },
    "fed_rates": {
        "keywords": ["rate cut", "fed funds", "FOMC", "federal reserve", "interest rate"],
        "impact": "Dovish surprise benefits GS/JPM longs; hawkish surprise pressures growth",
        "affected_sleeves": ["flexible"],
        "risk_direction": "rate_sensitivity",
    },
    "geopolitical": {
        "keywords": ["china taiwan", "russia ukraine", "nato", "nuclear", "sanctions"],
        "impact": "Broader geopolitical risk is a tailwind for defense/cyber, headwind for consumer",
        "affected_sleeves": ["war_long", "flexible"],
        "risk_direction": "geopolitical_risk",
    },
}

# Threshold: if ceasefire probability exceeds this, flag war sleeve as high risk
POLYMARKET_CEASEFIRE_RISK_THRESHOLD = 0.25
```

**Step 2: Write the failing test**

Create `tests/test_polymarket.py`:

```python
"""Tests for Polymarket data source client."""

import json
from unittest.mock import patch, MagicMock

import pytest


def test_search_markets_returns_parsed_results():
    """PolymarketClient.search_markets should return list of dicts with expected keys."""
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
    """Should return empty list on API failure."""
    from data.sources.polymarket import PolymarketClient

    with patch("data.sources.polymarket.requests.get", side_effect=Exception("API down")):
        client = PolymarketClient()
        results = client.search_markets("ceasefire")

    assert results == []


def test_get_war_relevant_markets_groups_by_category():
    """get_war_relevant_markets should return dict keyed by category."""
    from data.sources.polymarket import PolymarketClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": "1",
            "question": "Iran ceasefire before May?",
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
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -m pytest tests/test_polymarket.py -v`
Expected: FAIL (module not found)

**Step 4: Write the implementation**

Create `data/sources/polymarket.py`:

```python
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
                # Fallback: search without tag filter, do keyword match client-side
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
        query_lower = query.lower()
        for m in markets:
            question = m.get("question", "")
            # Accept if query appears in question or if API already filtered by tag
            if query_lower not in question.lower() and resp.status_code == 200:
                # If we used tag endpoint successfully, keep all results
                pass

            try:
                outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                outcomes = json.loads(m.get("outcomes", "[]"))
            except (json.JSONDecodeError, TypeError):
                outcome_prices = []
                outcomes = []

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
        """Fetch markets for all strategy-relevant categories defined in settings.

        Returns dict keyed by category name, each containing a list of matching markets.
        """
        cache_key = "war_relevant_all"
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

        # Fetch a large batch of active markets once
        try:
            resp = requests.get(
                f"{self.base_url}/markets",
                params={"limit": 200, "active": True},
                timeout=20,
            )
            all_markets = resp.json() if resp.status_code == 200 else []
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

            # Sort by volume (most liquid markets first)
            matches.sort(key=lambda x: x["volume"], reverse=True)
            categorized[category] = matches[:5]  # Top 5 per category

        _write_cache(cache_key, categorized)
        return categorized

    def get_summary_for_agents(self) -> dict[str, Any]:
        """Build a concise summary dict suitable for injecting into agent prompts.

        Returns:
            {
                "categories": {
                    "ceasefire": {
                        "top_market": "Will there be a ceasefire?",
                        "probability": 0.15,
                        "market_count": 3,
                        "impact": "Ceasefire reverses entire war sleeve...",
                    },
                    ...
                },
                "highest_risk_event": "ceasefire",
                "highest_risk_probability": 0.15,
                "raw_markets": { ... },  # full data for detailed agents
            }
        """
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

            top = markets[0]  # highest volume market
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

            # Track highest-risk event (for risk manager)
            if category in ("ceasefire", "war_escalation") and prob > highest_risk_prob:
                highest_risk_prob = prob
                highest_risk_cat = category

        summary["highest_risk_event"] = highest_risk_cat
        summary["highest_risk_probability"] = highest_risk_prob
        return summary
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -m pytest tests/test_polymarket.py -v`
Expected: 3 PASS

**Step 6: Commit**

```bash
git add config/settings.py data/sources/polymarket.py tests/test_polymarket.py
git commit -m "feat: add Polymarket data source client for event probability tracking"
```

---

### Task 2: Integrate into Catalyst Hunter

**Files:**
- Modify: `agents/catalyst_hunter.py`

**Step 1: Add Polymarket data to `gather_data()`**

In `catalyst_hunter.py`, after the existing news/earnings data gathering, add Polymarket fetch. Add this import at the top:

```python
from data.sources.polymarket import PolymarketClient
```

At the end of `gather_data()`, before the return statement, add:

```python
        # Polymarket event probabilities
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}
```

Update the return dict to include `"polymarket": polymarket_summary`.

**Step 2: Add Polymarket context to the LLM prompt**

In the `analyze()` method, add this block to the prompt string before the `DATA FOR EACH STOCK:` section:

```
POLYMARKET EVENT PROBABILITIES (crowd-sourced prediction markets):
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

Use these probabilities to calibrate catalyst scores:
- If ceasefire probability > 20%, DOWNGRADE catalyst scores for war longs (LMT, NOC, RTX etc.)
  and UPGRADE scores for war shorts (they benefit from ceasefire).
- If war escalation probability is HIGH, UPGRADE defense/energy catalysts.
- FOMC and tariff probabilities help calibrate macro catalyst timing.
```

**Step 3: Verify manually**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "from agents.catalyst_hunter import CatalystHunter; print('import OK')"`
Expected: `import OK`

**Step 4: Commit**

```bash
git add agents/catalyst_hunter.py
git commit -m "feat: inject Polymarket event probabilities into Catalyst Hunter"
```

---

### Task 3: Integrate into Sentiment Analyst

**Files:**
- Modify: `agents/sentiment_analyst.py`

**Step 1: Add Polymarket data to `gather_data()`**

Add import at top:

```python
from data.sources.polymarket import PolymarketClient
```

At the end of `gather_data()`, before the return, add:

```python
        # Polymarket crowd sentiment
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}
```

Add `"polymarket": polymarket_summary` to the return dict.

**Step 2: Add Polymarket context to the LLM prompt**

Add this block to the prompt before the `SENTIMENT DATA:` section:

```
POLYMARKET CROWD SENTIMENT (prediction market probabilities):
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

Polymarket represents CROWD CONSENSUS on event risk. Use it as an additional sentiment signal:
- High ceasefire probability = bearish sentiment for defense longs, bullish for airline shorts
- High war escalation probability = bullish sentiment for defense/energy
- These are real-money bets, so they carry more weight than news headlines alone
- If Polymarket odds DISAGREE with news sentiment, note the divergence in your rationale
```

**Step 3: Verify import**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "from agents.sentiment_analyst import SentimentAnalyst; print('import OK')"`

**Step 4: Commit**

```bash
git add agents/sentiment_analyst.py
git commit -m "feat: inject Polymarket crowd sentiment into Sentiment Analyst"
```

---

### Task 4: Integrate into Risk Manager

**Files:**
- Modify: `agents/risk_manager.py`

**Step 1: Add Polymarket data to `gather_data()`**

Add imports:

```python
from data.sources.polymarket import PolymarketClient
from config.settings import POLYMARKET_CEASEFIRE_RISK_THRESHOLD
```

At the end of `gather_data()`, before the return, add:

```python
        # Polymarket event risk for regime-change detection
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}

        # Flag if ceasefire risk is elevated
        ceasefire_prob = polymarket_summary.get("highest_risk_probability", 0)
        ceasefire_alert = ceasefire_prob >= POLYMARKET_CEASEFIRE_RISK_THRESHOLD
        if ceasefire_alert:
            logger.warning(
                f"[{self.name}] ⚠ CEASEFIRE PROBABILITY {ceasefire_prob:.0%} "
                f"exceeds threshold {POLYMARKET_CEASEFIRE_RISK_THRESHOLD:.0%} — "
                f"war sleeve positions at elevated risk!"
            )
```

Add to the return dict: `"polymarket": polymarket_summary, "ceasefire_alert": ceasefire_alert, "ceasefire_probability": ceasefire_prob`.

**Step 2: Add Polymarket context to the LLM prompt**

Add this block to the prompt after `OTHER AGENT INSIGHTS:`:

```
POLYMARKET EVENT RISK:
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

CEASEFIRE ALERT: {'⚠ YES — probability ' + str(round(data.get('ceasefire_probability', 0) * 100)) + '%' if data.get('ceasefire_alert') else 'No — below threshold'}

CRITICAL: If ceasefire probability > 20%, you MUST:
1. Penalize risk scores for ALL war_long positions by 10-20 points (regime reversal risk)
2. Note in rationale that war shorts face squeeze risk on ceasefire
3. Recommend smaller position sizes for war sleeve stocks
4. Flag this prominently in your summary and diversification_notes
```

**Step 3: Verify import**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "from agents.risk_manager import RiskManager; print('import OK')"`

**Step 4: Commit**

```bash
git add agents/risk_manager.py
git commit -m "feat: add Polymarket ceasefire risk detection to Risk Manager"
```

---

### Task 5: Integrate into Portfolio Manager

**Files:**
- Modify: `agents/portfolio_manager.py`

**Step 1: Add Polymarket data to `gather_data()`**

Add import:

```python
from data.sources.polymarket import PolymarketClient
```

At the end of `gather_data()`, before the return, add:

```python
        # Polymarket event probabilities for portfolio construction context
        try:
            poly_client = PolymarketClient()
            polymarket_summary = poly_client.get_summary_for_agents()
        except Exception as e:
            logger.warning(f"[{self.name}] Polymarket fetch failed: {e}")
            polymarket_summary = {}
```

Add `"polymarket": polymarket_summary` to the return dict.

**Step 2: Add Polymarket context to the LLM prompt**

Add this block to the prompt after `DIVERSIFICATION NOTES:` and before `CONSOLIDATED CANDIDATE DATA`:

```
POLYMARKET LIVE EVENT PROBABILITIES:
{json.dumps(data.get('polymarket', {}).get('categories', {}), indent=1, default=str)}

These are REAL-MONEY prediction market odds. Factor them into position sizing:
- If ceasefire probability > 20%: REDUCE war_long weights, TIGHTEN war_short stops
- If war escalation probability HIGH: INCREASE war sleeve allocation
- FOMC rate-cut odds inform GS/JPM sizing
- Tariff odds inform NKE and consumer exposure
- Use these to refine your contingency plan triggers with SPECIFIC probability thresholds
```

**Step 3: Verify import**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "from agents.portfolio_manager import PortfolioManager; print('import OK')"`

**Step 4: Commit**

```bash
git add agents/portfolio_manager.py
git commit -m "feat: add Polymarket probability context to Portfolio Manager"
```

---

### Task 6: End-to-End Smoke Test

**Files:**
- Test: run full pipeline

**Step 1: Verify Polymarket API is reachable**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "from data.sources.polymarket import PolymarketClient; c = PolymarketClient(); r = c.get_war_relevant_markets(); print(f'Categories found: {list(r.keys())}'); print(f'Total markets: {sum(len(v) for v in r.values())}')"`

Expected: Categories listed, some number of markets found (may be 0 for some categories if no matching markets exist — that's OK).

**Step 2: Verify summary format**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -c "
from data.sources.polymarket import PolymarketClient
import json
c = PolymarketClient()
s = c.get_summary_for_agents()
print(json.dumps(s.get('categories', {}), indent=2, default=str)[:2000])
"`

Expected: JSON dict with category keys, each having `top_market`, `probability`, `market_count`, `impact`.

**Step 3: Run unit tests**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python -m pytest tests/test_polymarket.py -v`
Expected: All pass.

**Step 4: Run full pipeline**

Run: `cd /Users/keshavdalmia/Documents/trading_competition && .venv/bin/python main.py`
Expected: Pipeline completes with Polymarket data visible in agent logs (look for "Polymarket" in output). Report generated.

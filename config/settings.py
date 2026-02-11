"""Central configuration for the trading competition analysis system."""

import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── LLM Configuration ────────────────────────────────────────────────────
GROK_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-3-mini-beta"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-reasoner"

LLM_MAX_RETRIES = 3
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 8192

# ── Competition Parameters ────────────────────────────────────────────────
COMPETITION_START = date(2026, 2, 11)
COMPETITION_END = date(2026, 3, 2)
MAX_PORTFOLIO_STOCKS = 10
MAX_PER_SECTOR = 3
MIN_EVOLUTION = 3
MIN_REVOLUTION = 3
MAX_SINGLE_WEIGHT = 0.15  # 15%

# ── Scoring Weights ──────────────────────────────────────────────────────
SCORING_WEIGHTS = {
    "technical": 0.25,
    "catalyst": 0.25,
    "risk": 0.20,
    "fundamental": 0.15,
    "sentiment": 0.15,
}

# ── Data Parameters ──────────────────────────────────────────────────────
PRICE_HISTORY_DAYS = 180  # 6 months of daily data for technicals
RISK_WINDOW_DAYS = 90
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
CACHE_TTL_HOURS = 4  # Cache expiration

# ── Screener Filters ────────────────────────────────────────────────────
SCREENER_MIN_MARKET_CAP = 5e9  # $5B
SCREENER_MIN_AVG_VOLUME = 1_000_000
SCREENER_MIN_REVENUE_GROWTH = 0.15  # 15% YoY
SCREENER_MIN_EARNINGS_SURPRISE = 0.05  # 5%

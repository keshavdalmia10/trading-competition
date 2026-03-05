"""Central configuration for the trading competition analysis system."""

import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── LLM Configuration ────────────────────────────────────────────────────
GROK_BASE_URL = "https://api.x.ai/v1"
GROK_MODEL = "grok-3-mini-beta"

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

LLM_MAX_RETRIES = 3
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 8192

# -- Competition Parameters (Round 2) ------------------------------------
COMPETITION_START = date(2026, 3, 2)
COMPETITION_END = date(2026, 4, 3)
STARTING_CASH = 100_000
MARGIN_MULTIPLIER = 1.5  # 1.5x leverage
TOTAL_BUYING_POWER = STARTING_CASH * MARGIN_MULTIPLIER  # $150K
MAX_PORTFOLIO_STOCKS = 16  # 8 long + 8 short
MAX_PER_SECTOR = 4
MAX_SINGLE_WEIGHT = 0.12  # 12% of total buying power
COMMISSION = 1.99
MIN_SHORT_PRICE = 5.00
MARGIN_INTEREST_DAILY = 0.0008  # 0.08%

# -- Sleeve Allocation Targets -------------------------------------------
SLEEVE_TARGETS = {
    "war_long": 0.35,   # ~$52K
    "war_short": 0.30,  # ~$45K
    "flexible": 0.35,   # ~$53K
}

# -- Stop-Loss Defaults ---------------------------------------------------
STOP_LOSS_DEFAULTS = {
    "war_long": 15.0,
    "war_short": 25.0,
    "flexible_long": 12.0,
    "flexible_short": 20.0,
}

# -- Scoring Weights (Round 2: war-adjusted) ------------------------------
SCORING_WEIGHTS = {
    "technical": 0.20,
    "catalyst": 0.30,
    "risk": 0.15,
    "fundamental": 0.10,
    "sentiment": 0.25,
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

"""Initial ticker universe for the trading competition."""

# Evolution: established companies innovating incrementally
# Evolution: established blue-chip and mega-cap growth leaders
EVOLUTION_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    "NVDA", "JPM", "WMT", "CRM", "ADBE",
    "NFLX", "V", "UNH", "JNJ", "COST",
]

# Revolution: disruptive companies changing entire industries
REVOLUTION_TICKERS = [
    "TSLA", "PLTR", "COIN", "RKLB", "IONQ",
    "ARM", "CRSP", "HOOD", "XYZ", "NET",
    "SNOW", "AFRM", "SMCI", "DDOG", "AI",
]

# High momentum plays: stocks with strong relative strength and trend
MOMENTUM_TICKERS = [
    "AVGO", "AMD", "MRVL", "PANW", "NOW",
    "UBER", "LLY", "NVO", "APP", "MSTR",
]

# Pre-classified evolution/revolution mapping
TICKER_CLASSIFICATION: dict[str, str] = {}
for t in EVOLUTION_TICKERS:
    TICKER_CLASSIFICATION[t] = "evolution"
for t in REVOLUTION_TICKERS:
    TICKER_CLASSIFICATION[t] = "revolution"
for t in MOMENTUM_TICKERS:
    # Momentum tickers default to evolution unless overridden
    TICKER_CLASSIFICATION.setdefault(t, "evolution")

# Full curated watchlist (deduplicated)
ALL_TICKERS = sorted(set(EVOLUTION_TICKERS + REVOLUTION_TICKERS + MOMENTUM_TICKERS))

"""Ticker universe for Round 2: War Pairs strategy (Mar 2 - Apr 3, 2026)."""

# War Longs: defense, energy — benefit from US-Iran conflict
WAR_LONG_TICKERS = [
    "LMT",   # Lockheed Martin — top defense contractor
    "NOC",   # Northrop Grumman — missiles & drones
    "RTX",   # RTX Corp — Patriot missile systems
    "GD",    # General Dynamics — naval/Gulf escort ops
    "XOM",   # ExxonMobil — oil surge, ATH
    "CVX",   # Chevron — oil thesis, strong balance sheet
    "OXY",   # Occidental — high beta oil play
    "LNG",   # Cheniere Energy — LNG exports surging
]

# War Shorts: airlines, travel, consumer — hurt by war
WAR_SHORT_TICKERS = [
    "AAL",   # American Airlines — worst balance sheet, fuel costs
    "DAL",   # Delta — international route exposure
    "UAL",   # United — fuel hedge inadequate
    "CCL",   # Carnival — cruise devastated by fuel + Gulf closures
    "ABNB",  # Airbnb — travel demand destruction
    "DIS",   # Disney — parks spending squeeze
    "NKE",   # Nike — consumer discretionary + tariff hit
]

# Flexible Longs: AI, cybersecurity, financials — war-agnostic momentum
FLEXIBLE_LONG_TICKERS = [
    "CRWD",  # CrowdStrike — cybersecurity + AI + war demand
    "PANW",  # Palo Alto — cyber demand surge
    "PLTR",  # Palantir — AI + gov/defense contracts
    "AVGO",  # Broadcom — AI infrastructure momentum
    "DELL",  # Dell — AI infrastructure, 30% earnings surge
    "GS",    # Goldman Sachs — higher rates, trading revenue
    "JPM",   # JPMorgan — same thesis as GS
    "AXON",  # Axon — defense/law enforcement tech
]

# Flexible Shorts: unprofitable, tariff-exposed, weak sectors
FLEXIBLE_SHORT_TICKERS = [
    "RIVN",  # Rivian — no profits, EV demand destruction
    "LCID",  # Lucid — cash burn, demand destruction
    "SNAP",  # Snap — ad revenue collapse
    "COIN",  # Coinbase — crypto Fear Index at 14
    "HOOD",  # Robinhood — crypto + retail trading slowdown
]

# Sleeve classification mapping
TICKER_SLEEVE: dict[str, str] = {}
for t in WAR_LONG_TICKERS:
    TICKER_SLEEVE[t] = "war_long"
for t in WAR_SHORT_TICKERS:
    TICKER_SLEEVE[t] = "war_short"
for t in FLEXIBLE_LONG_TICKERS:
    TICKER_SLEEVE[t] = "flexible"
for t in FLEXIBLE_SHORT_TICKERS:
    TICKER_SLEEVE[t] = "flexible"

# Direction mapping
TICKER_DIRECTION: dict[str, str] = {}
for t in WAR_LONG_TICKERS + FLEXIBLE_LONG_TICKERS:
    TICKER_DIRECTION[t] = "long"
for t in WAR_SHORT_TICKERS + FLEXIBLE_SHORT_TICKERS:
    TICKER_DIRECTION[t] = "short"

# Backward-compatible classification (all are "evolution" for simplicity)
TICKER_CLASSIFICATION: dict[str, str] = {t: "evolution" for t in TICKER_SLEEVE}

# Full ticker universe
ALL_LONG_TICKERS = sorted(set(WAR_LONG_TICKERS + FLEXIBLE_LONG_TICKERS))
ALL_SHORT_TICKERS = sorted(set(WAR_SHORT_TICKERS + FLEXIBLE_SHORT_TICKERS))
ALL_TICKERS = sorted(set(ALL_LONG_TICKERS + ALL_SHORT_TICKERS))

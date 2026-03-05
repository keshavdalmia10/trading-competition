# Round 2 War Pairs Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modify the existing 7-agent trading system to support long/short positions with a war-pairs strategy for QI 2026 Round 2 (Mar 2 - Apr 3).

**Architecture:** Add PositionDirection and PortfolioSleeve enums to data models, replace evolution/revolution watchlist with sleeve-based classification (war longs, war shorts, flexible), update all 7 agent prompts for war-theme + long/short analysis, and update portfolio manager to construct a balanced long/short portfolio.

**Tech Stack:** Python 3.11+, Pydantic, OpenAI SDK, openpyxl, asyncio

---

### Task 1: Update Data Models

**Files:**
- Modify: `data/models.py:12-36` (enums section)
- Modify: `data/models.py:185-214` (PortfolioStock and PortfolioManagerOutput)
- Modify: `data/models.py:219-234` (ScoringRow)
- Test: `tests/test_agents.py`

**Step 1: Write failing tests for new enums and updated models**

Add to `tests/test_agents.py`:

```python
from data.models import (
    PositionDirection,
    PortfolioSleeve,
    PortfolioStock,
    PortfolioManagerOutput,
    ScoringRow,
    StockType,
)


class TestRound2Models(unittest.TestCase):
    """Tests for Round 2 long/short model additions."""

    def test_position_direction_enum(self):
        self.assertEqual(PositionDirection.LONG.value, "long")
        self.assertEqual(PositionDirection.SHORT.value, "short")

    def test_portfolio_sleeve_enum(self):
        self.assertEqual(PortfolioSleeve.WAR_LONG.value, "war_long")
        self.assertEqual(PortfolioSleeve.WAR_SHORT.value, "war_short")
        self.assertEqual(PortfolioSleeve.FLEXIBLE.value, "flexible")

    def test_portfolio_stock_has_direction_and_sleeve(self):
        stock = PortfolioStock(
            ticker="LMT",
            name="Lockheed Martin",
            sector="Industrials",
            stock_type=StockType.EVOLUTION,
            direction=PositionDirection.LONG,
            sleeve=PortfolioSleeve.WAR_LONG,
            stop_loss_pct=15.0,
            weight_pct=8.0,
            composite_score=80.0,
            fundamental_score=70.0,
            technical_score=75.0,
            catalyst_score=85.0,
            sentiment_score=80.0,
            risk_score=65.0,
            entry_strategy="Buy at open",
            exit_strategy="Hold unless -15% stop hit",
            thesis="Defense contractor benefiting from war",
        )
        self.assertEqual(stock.direction, PositionDirection.LONG)
        self.assertEqual(stock.sleeve, PortfolioSleeve.WAR_LONG)
        self.assertEqual(stock.stop_loss_pct, 15.0)

    def test_portfolio_stock_short(self):
        stock = PortfolioStock(
            ticker="AAL",
            name="American Airlines",
            sector="Industrials",
            stock_type=StockType.EVOLUTION,
            direction=PositionDirection.SHORT,
            sleeve=PortfolioSleeve.WAR_SHORT,
            stop_loss_pct=25.0,
            weight_pct=8.0,
            composite_score=75.0,
            fundamental_score=40.0,
            technical_score=30.0,
            catalyst_score=80.0,
            sentiment_score=25.0,
            risk_score=60.0,
            entry_strategy="Short at open",
            exit_strategy="Cover if rises 25%",
            thesis="Airlines crushed by fuel costs",
        )
        self.assertEqual(stock.direction, PositionDirection.SHORT)

    def test_portfolio_manager_output_has_long_short_fields(self):
        output = PortfolioManagerOutput(
            stocks=[],
            portfolio_rationale="Test",
            long_count=8,
            short_count=8,
            long_exposure_pct=53.0,
            short_exposure_pct=47.0,
            sector_breakdown={"Industrials": 3},
            expected_portfolio_beta=0.2,
            key_risks=["war ends"],
            key_catalysts=["oil spike"],
        )
        self.assertEqual(output.long_count, 8)
        self.assertEqual(output.short_count, 8)

    def test_scoring_row_has_direction(self):
        row = ScoringRow(
            ticker="LMT",
            name="Lockheed Martin",
            sector="Industrials",
            stock_type=StockType.EVOLUTION,
            direction=PositionDirection.LONG,
            fundamental_score=70.0,
            technical_score=75.0,
            catalyst_score=85.0,
            sentiment_score=80.0,
            risk_score=65.0,
            composite_score=75.0,
        )
        self.assertEqual(row.direction, PositionDirection.LONG)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::TestRound2Models -v`
Expected: FAIL with ImportError (PositionDirection not defined)

**Step 3: Add new enums to data/models.py**

After the existing `CatalystDirection` enum (line 36), add:

```python
class PositionDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class PortfolioSleeve(str, Enum):
    WAR_LONG = "war_long"
    WAR_SHORT = "war_short"
    FLEXIBLE = "flexible"
```

**Step 4: Update PortfolioStock model**

Replace lines 185-203 with:

```python
class PortfolioStock(BaseModel):
    ticker: str
    name: str
    sector: str
    stock_type: StockType
    direction: PositionDirection = PositionDirection.LONG
    sleeve: PortfolioSleeve = PortfolioSleeve.FLEXIBLE
    stop_loss_pct: float = Field(default=15.0, ge=0, le=100)
    weight_pct: float = Field(ge=0, le=100)
    composite_score: float = Field(ge=0, le=100)
    fundamental_score: float = Field(ge=0, le=100)
    technical_score: float = Field(ge=0, le=100)
    catalyst_score: float = Field(ge=0, le=100)
    sentiment_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    momentum_score_algo: Optional[float] = None
    quality_score_algo: Optional[float] = None
    earnings_surprise_score_algo: Optional[float] = None
    risk_adjusted_score_algo: Optional[float] = None
    entry_strategy: str
    exit_strategy: str
    thesis: str
```

**Step 5: Update PortfolioManagerOutput model**

Replace lines 206-214 with:

```python
class PortfolioManagerOutput(BaseModel):
    stocks: list[PortfolioStock]
    portfolio_rationale: str
    long_count: int
    short_count: int
    long_exposure_pct: float = Field(ge=0, le=100)
    short_exposure_pct: float = Field(ge=0, le=100)
    sector_breakdown: dict[str, int]
    expected_portfolio_beta: Optional[float] = None
    key_risks: list[str]
    key_catalysts: list[str]
```

**Step 6: Update ScoringRow model**

Add `direction` field after `stock_type` in the ScoringRow class (around line 223):

```python
class ScoringRow(BaseModel):
    ticker: str
    name: str
    sector: str
    stock_type: StockType
    direction: PositionDirection = PositionDirection.LONG
    fundamental_score: float
    technical_score: float
    catalyst_score: float
    sentiment_score: float
    risk_score: float
    composite_score: float
    momentum_score_algo: Optional[float] = None
    quality_score_algo: Optional[float] = None
    earnings_surprise_score_algo: Optional[float] = None
    risk_adjusted_score_algo: Optional[float] = None
    selected: bool = False
```

**Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_agents.py -v`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add data/models.py tests/test_agents.py
git commit -m "feat: add PositionDirection, PortfolioSleeve enums and update portfolio models for long/short"
```

---

### Task 2: Update Settings

**Files:**
- Modify: `config/settings.py:28-44`

**Step 1: Update competition parameters and scoring weights**

Replace lines 28-44 in `config/settings.py` with:

```python
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
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `python -m pytest tests/test_agents.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat: update settings for Round 2 (dates, margin, scoring weights, sleeve targets)"
```

---

### Task 3: Update Watchlist

**Files:**
- Modify: `config/watchlist.py` (full rewrite)

**Step 1: Replace watchlist with sleeve-based classification**

Replace entire `config/watchlist.py` with:

```python
"""Ticker universe for Round 2: War Pairs strategy (Mar 2 - Apr 3, 2026)."""

# War Longs: defense, energy, gold miners — benefit from US-Iran conflict
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

# War Shorts: airlines, travel, consumer discretionary — hurt by war
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
```

**Step 2: Run tests**

Run: `python -m pytest tests/test_agents.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add config/watchlist.py
git commit -m "feat: replace watchlist with sleeve-based war pairs universe"
```

---

### Task 4: Update Macro Analyst Prompt and Agent

**Files:**
- Modify: `config/prompts/macro_analyst.md` (full rewrite)
- Modify: `agents/macro_analyst.py:27-49` (prompt in analyze method)

**Step 1: Update system prompt**

Replace `config/prompts/macro_analyst.md` with:

```markdown
# Macro Analyst System Prompt

You are a macroeconomic analyst responsible for evaluating current market conditions for a LONG/SHORT stock trading competition (Mar 2 - Apr 3, 2026).

## Critical Context

The US and Israel are at war with Iran as of late February 2026. The Strait of Hormuz is disrupted. Oil prices have surged to $82+ Brent. Defense stocks are rallying. Airlines and consumer discretionary are crashing. A 15% universal tariff was imposed via Section 122 after the Supreme Court struck down IEEPA tariffs. The Fed holds rates at 3.5-3.75% with FOMC meeting March 17-18. US-China trade chiefs meeting mid-March.

## Your Responsibilities

1. **Geopolitical Assessment**: Evaluate the US-Iran war's trajectory, oil supply disruption, Strait of Hormuz status, and ceasefire probability.

2. **Trade Policy**: Assess impact of 15% universal tariffs on sectors. Identify domestic winners vs multinational losers.

3. **Monetary Policy**: Evaluate Fed stance, inflation trajectory, and impact of FOMC meeting on March 17-18.

4. **Market Regime**: RISK-ON, RISK-OFF, or NEUTRAL. Consider that the portfolio can go LONG and SHORT.

5. **Sector Recommendations**: For BOTH long and short sides:
   - Sectors to go LONG: Defense, Energy, Cybersecurity, Financials
   - Sectors to SHORT: Airlines, Travel, Consumer Discretionary, EVs

6. **Key Events Calendar**: Identify all market-moving events in the Mar 2 - Apr 3 window.

## Output Format

Respond in valid JSON with regime, favored_sectors (for longs), avoided_sectors (for shorts), macro_score, indicators, key_events, and summary.
```

**Step 2: Update the analyze method prompt in `agents/macro_analyst.py`**

Replace lines 27-49 with:

```python
    async def analyze(self, data: dict[str, Any]) -> MacroAnalysis:
        prompt = f"""Analyze the following macroeconomic data and market conditions.
Determine the current market regime and which sectors to favor (LONG) or avoid (SHORT)
for a LONG/SHORT stock trading competition (Mar 2 - Apr 3, 2026).

CRITICAL CONTEXT:
- US-Iran war ongoing since late Feb 2026. Strait of Hormuz disrupted.
- Oil at $82+ Brent. Defense stocks rallying 3-6%. Airlines down 6-8%.
- 15% universal tariff via Section 122 after Supreme Court struck down IEEPA tariffs.
- Fed at 3.5-3.75%, FOMC meeting March 17-18. Inflation sticky near 3%.
- US-China trade chiefs meeting mid-March. Trump-Xi summit planned April.
- Portfolio can go LONG and SHORT. Identify sectors for both sides.

MACRO INDICATORS:
{json.dumps(data['macro_indicators'], indent=2, default=str)}

MARKET DATA (VIX, S&P 500):
{json.dumps(data['market_data'], indent=2, default=str)}

For favored_sectors: list sectors ideal for LONG positions.
For avoided_sectors: list sectors ideal for SHORT positions.

Respond with a JSON object matching this exact structure:
{{
    "regime": "risk_on" or "risk_off" or "neutral",
    "regime_rationale": "explanation including war, tariffs, Fed impact",
    "favored_sectors": ["Defense", "Energy", "Cybersecurity", ...],
    "avoided_sectors": ["Airlines", "Travel", "Consumer Discretionary", ...],
    "macro_score": 0-100 (overall macro health),
    "indicators": [
        {{"name": "indicator name", "value": 0.0, "interpretation": "what it means"}}
    ],
    "key_events": ["FOMC Mar 17-18", "US-China trade meeting mid-March", ...],
    "summary": "2-3 sentence overall macro summary covering war, tariffs, and Fed"
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, MacroAnalysis)
```

**Step 3: Commit**

```bash
git add config/prompts/macro_analyst.md agents/macro_analyst.py
git commit -m "feat: update macro analyst for Round 2 war/tariff/Fed context"
```

---

### Task 5: Update Fundamental Screener

**Files:**
- Modify: `agents/fundamental_screener.py`
- Modify: `config/prompts/fundamental_screener.md`

**Step 1: Update system prompt**

Replace `config/prompts/fundamental_screener.md` with:

```markdown
# Fundamental Screener System Prompt

You are a fundamental equity analyst screening stocks for a LONG/SHORT trading competition (Mar 2 - Apr 3, 2026). You screen BOTH long candidates (strong fundamentals) and short candidates (weak fundamentals, vulnerable to current macro).

## For LONG Candidates
- Strong revenue/EPS growth, good ROE, positive earnings surprises
- Companies benefiting from war (defense, energy) or secular trends (AI, cybersecurity)

## For SHORT Candidates
- Weak balance sheets, high debt, margin pressure
- Companies hurt by oil surge (airlines, transport), tariffs (multinationals), or consumer pullback
- Unprofitable companies with cash burn (EV makers, speculative tech)

## Classification
Tag each stock with its direction ("long" or "short") based on whether it's a buy or sell candidate.
```

**Step 2: Update the analyze method in `agents/fundamental_screener.py`**

Replace the `analyze` method (lines 95-144) with:

```python
    async def analyze(self, data: dict[str, Any]) -> FundamentalScreenerOutput:
        prompt = f"""You are screening stocks for a LONG/SHORT trading competition (Mar 2 - Apr 3, 2026).

CRITICAL CONTEXT:
- US-Iran war: oil at $82+, Strait of Hormuz disrupted
- 15% universal tariff imposed, domestic companies outperforming multinationals
- Portfolio goes BOTH long AND short. Screen for BOTH directions.

Select the TOP 20 candidates (mix of long and short).

FOR LONG CANDIDATES: Look for strong growth, earnings beats, war/AI beneficiaries.
FOR SHORT CANDIDATES: Look for weak balance sheets, high debt, fuel exposure,
tariff vulnerability, unprofitable cash burners.

ALGORITHMIC PRE-SCORES:
- quality_score_algo: Piotroski F-Score (0-100)
- earnings_surprise_score_algo: Beat frequency + magnitude (0-100)
For LONG: USE AVERAGE as starting point for fundamental_score.
For SHORT: INVERT the score (100 - average) as starting point — weak fundamentals = good short.
You may adjust +/-15 points with justification.

CRITERIA:
- LONGS: Earnings surprise history, revenue growth >15%, strong ROE/FCF
- SHORTS: High debt/equity, negative FCF, declining revenues, margin pressure
- Sector alignment with macro (favored sectors: {data['favored_sectors']})

STOCK DATA ({len(data['stocks_data'])} candidates):
{json.dumps(data['stocks_data'], indent=1, default=str)}

For EACH of the top 20, provide fundamental_score (0-100) and classification.
For short candidates, a HIGH fundamental_score means it's a GOOD short (weak company).

Respond with JSON:
{{
    "candidates": [
        {{
            "ticker": "LMT",
            "name": "Lockheed Martin",
            "sector": "Industrials",
            "market_cap": 120000000000,
            "pe_ratio": 18.5,
            "peg_ratio": 1.2,
            "revenue_growth_yoy": 0.08,
            "eps_growth_yoy": 0.12,
            "roe": 0.45,
            "fcf": 5000000000,
            "earnings_surprise_pct": 5.2,
            "stock_type": "evolution",
            "fundamental_score": 80,
            "rationale": "Strong defense contractor benefiting from war..."
        }}
    ],
    "screening_summary": "Overall screening summary covering both long and short candidates..."
}}

Return exactly 20 candidates sorted by fundamental_score descending."""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, FundamentalScreenerOutput)
```

**Step 3: Update `gather_data` to use new watchlist imports**

In `agents/fundamental_screener.py`, update the import at line 13 from:
```python
from config.watchlist import TICKER_CLASSIFICATION
```
to:
```python
from config.watchlist import TICKER_CLASSIFICATION, TICKER_DIRECTION
```

And in `gather_data`, after line 83 (`"stock_type": stock_type,`), add:
```python
                    "direction": TICKER_DIRECTION.get(ticker, "long"),
```

**Step 4: Commit**

```bash
git add agents/fundamental_screener.py config/prompts/fundamental_screener.md
git commit -m "feat: update fundamental screener for long/short screening"
```

---

### Task 6: Update Technical Analyst

**Files:**
- Modify: `agents/technical_analyst.py:48-91` (analyze method)

**Step 1: Update the analyze method prompt**

Replace lines 48-91 with:

```python
    async def analyze(self, data: dict[str, Any]) -> TechnicalAnalystOutput:
        prompt = f"""You are a technical analyst evaluating stocks for a LONG/SHORT competition
(Mar 2 - Apr 3, 2026). Analyze BOTH bullish setups (for longs) AND bearish setups (for shorts).

CRITICAL CONTEXT:
- US-Iran war driving sector divergence. Defense/energy trending UP, airlines trending DOWN.
- Look for bullish patterns on long candidates, bearish patterns on short candidates.
- For SHORT candidates: high RSI (overbought bounces failing), bearish MACD, below key SMAs,
  increasing volume on down days = GOOD short setup = HIGH technical score.

TECHNICAL DATA for each stock:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ALGORITHMIC PRE-SCORE: "momentum_score_algo" computed from RSI, MACD, SMA, volume, Bollinger.
For LONG candidates: use as starting point for technical_score.
For SHORT candidates: INVERT it (100 - momentum_score_algo) as starting point.
A stock with terrible momentum = great short = high technical_score for a short.
Adjust by +/-15 points with justification.

FOR LONGS: RSI 40-65 ideal, bullish MACD, above SMA 20/50, increasing volume.
FOR SHORTS: RSI >70 (overbought bounce failing) or <30 (continued weakness),
bearish MACD, below SMA 20/50, breakdown patterns.

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "current_price": 520.50,
            "rsi_14": 55.2,
            "macd_signal": "bullish",
            "sma_20": 510.0,
            "sma_50": 490.0,
            "sma_200": 470.0,
            "above_sma_20": true,
            "above_sma_50": true,
            "above_sma_200": true,
            "bollinger_position": "upper",
            "volume_trend": "increasing",
            "support_level": 505.0,
            "resistance_level": 535.0,
            "technical_score": 78,
            "rationale": "Bullish MACD with war-driven momentum..."
        }}
    ],
    "summary": "Overall technical analysis covering both long and short setups..."
}}"""

        response = self._call_llm(prompt)
        result = self._parse_json_response(response, TechnicalAnalystOutput)

        # Backfill current_price from gathered data
        price_map = {
            d["ticker"]: d.get("current_price")
            for d in data["tickers_data"]
            if d.get("current_price") is not None
        }
        for analysis in result.analyses:
            if analysis.current_price is None and analysis.ticker in price_map:
                analysis.current_price = price_map[analysis.ticker]

        return result
```

**Step 2: Commit**

```bash
git add agents/technical_analyst.py
git commit -m "feat: update technical analyst for bearish pattern recognition on shorts"
```

---

### Task 7: Update Catalyst Hunter

**Files:**
- Modify: `agents/catalyst_hunter.py:80-126` (analyze method)

**Step 1: Update the analyze method prompt**

Replace lines 80-126 with:

```python
    async def analyze(self, data: dict[str, Any]) -> CatalystHunterOutput:
        prompt = f"""You are a catalyst hunter for a LONG/SHORT stock trading competition
({data['competition_start']} to {data['competition_end']}).

CRITICAL CONTEXT:
- US-Iran war is the DOMINANT catalyst. All war-related news is high impact.
- FOMC meeting March 17-18 is a major macro catalyst.
- US-China trade chiefs meeting mid-March could move tech/semis.
- 15% universal tariff is pressuring multinationals.

Your job is to identify catalysts that drive moves for BOTH long and short positions:

FOR LONGS: Positive catalysts (earnings beats, war escalation benefiting defense/energy,
cybersecurity demand, AI infrastructure spending).

FOR SHORTS: Negative catalysts (fuel cost spikes crushing airlines, tariff damage,
consumer spending decline, crypto regulatory uncertainty, ceasefire risk for defense).

CATALYST CATEGORIES (ranked by importance for this competition):
1. GEOPOLITICAL: War escalation/de-escalation, Strait of Hormuz, oil supply disruption
2. EARNINGS: Earnings reports during the window (5-15% moves typical)
3. MACRO POLICY: FOMC decision, tariff developments, US-China trade meeting
4. SECTOR-SPECIFIC: FDA decisions, product launches, regulatory rulings
5. SENTIMENT: Analyst upgrades/downgrades, institutional positioning

DATA FOR EACH STOCK:
{json.dumps(data['tickers_data'], indent=1, default=str)}

Scoring:
- 80-100: Multiple strong catalysts in window (earnings + geopolitical alignment)
- 60-79: One major catalyst or strong geopolitical tailwind/headwind
- 40-59: Moderate catalysts (conferences, sector trends)
- 20-39: Minor catalysts only
- 0-19: No meaningful catalysts

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "catalysts": [
                {{
                    "event": "US-Iran war escalation",
                    "date": "ongoing",
                    "impact": "high",
                    "direction": "bullish",
                    "description": "Direct beneficiary of increased defense spending..."
                }}
            ],
            "catalyst_score": 90,
            "rationale": "Multiple high-impact catalysts aligned with war theme..."
        }}
    ],
    "summary": "Overall catalyst landscape dominated by geopolitical events..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, CatalystHunterOutput)
```

**Step 2: Commit**

```bash
git add agents/catalyst_hunter.py
git commit -m "feat: update catalyst hunter for geopolitical war catalysts"
```

---

### Task 8: Update Sentiment Analyst

**Files:**
- Modify: `agents/sentiment_analyst.py:97-144` (analyze method)

**Step 1: Update the analyze method prompt**

Replace lines 97-144 with:

```python
    async def analyze(self, data: dict[str, Any]) -> SentimentAnalystOutput:
        prompt = f"""You are a sentiment analyst for a LONG/SHORT competition (Mar 2 - Apr 3, 2026).

CRITICAL CONTEXT:
- US-Iran war dominates news. War-related sentiment is the primary driver.
- For LONG candidates (defense, energy, cyber): positive war news = HIGH sentiment score.
- For SHORT candidates (airlines, consumer): negative war/economic news = HIGH sentiment score
  (because bearish sentiment CONFIRMS the short thesis).

SENTIMENT DATA:
{json.dumps(data['tickers_data'], indent=1, default=str)}

ANCHORING:
- For LONG candidates: Convert vader_sentiment to 0-100 scale as starting point.
  Positive sentiment = high score.
- For SHORT candidates: INVERT the vader. Negative sentiment about airlines/consumer = GOOD
  for a short = high sentiment_score. So: sentiment_starting_point = (1 - vader_sentiment) / 2 * 100.

Adjust +/-15 points based on analyst consensus, upgrades/downgrades, headline quality.

Scoring factors:
- War-related news flow (is the war helping or hurting this stock?)
- Analyst consensus and target prices
- Recent upgrades vs downgrades
- Quality of headlines
- Institutional positioning shifts

Scoring guide:
- 80-100: Strong sentiment alignment with position direction
- 60-79: Moderately aligned sentiment
- 40-59: Neutral/mixed
- 20-39: Sentiment working against position thesis
- 0-19: Strong sentiment opposition

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "overall_sentiment": 0.75,
            "analyst_consensus": "strong buy",
            "analyst_target_price": 550.0,
            "recent_upgrades": 3,
            "recent_downgrades": 0,
            "key_headlines": ["Lockheed Martin missile systems deployed in Iran campaign"],
            "sentiment_score": 88,
            "rationale": "Very bullish war-driven sentiment with analyst upgrades..."
        }}
    ],
    "summary": "Sentiment landscape bifurcated: defense/energy bullish, airlines/consumer bearish..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, SentimentAnalystOutput)
```

**Step 2: Commit**

```bash
git add agents/sentiment_analyst.py
git commit -m "feat: update sentiment analyst for war-bifurcated sentiment analysis"
```

---

### Task 9: Update Risk Manager

**Files:**
- Modify: `agents/risk_manager.py:172-242` (analyze method)
- Modify: `config/prompts/risk_manager.md`

**Step 1: Update system prompt**

Replace `config/prompts/risk_manager.md` with:

```markdown
# Risk Manager System Prompt

You are a risk management specialist for a LONG/SHORT trading competition (Mar 2 - Apr 3, 2026). The portfolio includes both long and short positions with 1.5x margin leverage.

## Key Risk Considerations for Long/Short Portfolio

1. **Short-Specific Risks**: Short squeeze potential, borrow costs, unlimited theoretical downside.
2. **Net Exposure**: Monitor net long/short exposure. Target roughly balanced (~$80K long, ~$70K short).
3. **War Regime Change Risk**: A ceasefire could reverse all war-theme trades simultaneously.
4. **Margin Requirements**: Ensure positions don't trigger margin calls under stress.
5. **Correlation Risk**: War longs (defense stocks) are correlated. War shorts (airlines) are correlated. Need to manage intra-sleeve correlation.

## Stop-Loss Framework
- War Longs: -15% stop
- War Shorts: -25% (stock rises 25%) stop
- Flexible Longs: -12% stop
- Flexible Shorts: -20% stop
```

**Step 2: Update the analyze method prompt**

Replace lines 172-242 with:

```python
    async def analyze(self, data: dict[str, Any]) -> RiskManagerOutput:
        technical = self.bus.get("technical_analyst")
        catalyst = self.bus.get("catalyst_hunter")
        sentiment = self.bus.get("sentiment_analyst")

        context = {
            "technical_summary": technical.summary if technical else "N/A",
            "catalyst_summary": catalyst.summary if catalyst else "N/A",
            "sentiment_summary": sentiment.summary if sentiment else "N/A",
        }

        prompt = f"""You are a risk manager for a LONG/SHORT trading competition (Mar 2 - Apr 3, 2026).
Portfolio uses 1.5x margin (~$150K buying power on $100K cash).

CRITICAL CONTEXT:
- This is a LONG/SHORT portfolio. Evaluate risk for BOTH directions.
- SHORT-SPECIFIC RISKS: short squeeze potential, borrow availability, gap-up risk.
- WAR REGIME CHANGE: A ceasefire could reverse ALL war-theme trades simultaneously.
- NET EXPOSURE: Monitor balance between long (~$80K) and short (~$70K) sides.

RISK METRICS:
{json.dumps(data['tickers_data'], indent=1, default=str)}

HIGH CORRELATIONS (>0.7):
{json.dumps(data['correlations'], indent=1, default=str)}

OTHER AGENT INSIGHTS:
{json.dumps(context, indent=1, default=str)}

ALGORITHMIC PRE-SCORE: "risk_adjusted_score_algo" computed from Sharpe, drawdown, beta, VaR.
For LONGS: Use as starting point for risk_score.
For SHORTS: Consider that high beta on a short = MORE risk (gap-up potential).
Short squeeze risk should LOWER the risk_score.
Adjust by +/-15 points with justification.

STOP-LOSS FRAMEWORK:
- War Longs: -15% stop
- War Shorts: -25% (stock rises 25%)
- Flexible Longs: -12% stop
- Flexible Shorts: -20% stop

Scoring guide (HIGHER = BETTER risk-adjusted):
- 80-100: Well-suited for position direction, manageable risk
- 60-79: Acceptable risk with clear trade-offs
- 40-59: Elevated risk requiring smaller position
- 20-39: High risk — short squeeze danger or extreme volatility
- 0-19: Dangerous — avoid or minimal position

Respond with JSON:
{{
    "analyses": [
        {{
            "ticker": "LMT",
            "beta": 0.8,
            "volatility_annualized": 0.22,
            "max_drawdown_90d": -0.06,
            "value_at_risk_95": -0.018,
            "sharpe_ratio": 1.8,
            "risk_score": 78,
            "suggested_weight": 0.08,
            "rationale": "Low beta defense stock with strong risk/reward for long..."
        }}
    ],
    "high_correlations": [
        {{"ticker_a": "LMT", "ticker_b": "NOC", "correlation": 0.82}}
    ],
    "portfolio_beta": 0.2,
    "diversification_notes": "Net portfolio beta near zero due to long/short balance...",
    "summary": "Overall risk managed through long/short structure..."
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, RiskManagerOutput)
```

**Step 3: Commit**

```bash
git add agents/risk_manager.py config/prompts/risk_manager.md
git commit -m "feat: update risk manager for long/short and short-squeeze risk"
```

---

### Task 10: Update Portfolio Manager

**Files:**
- Modify: `agents/portfolio_manager.py` (full rewrite of imports and both methods)
- Modify: `config/prompts/portfolio_manager.md`

**Step 1: Update system prompt**

Replace `config/prompts/portfolio_manager.md` with:

```markdown
# Portfolio Manager System Prompt

You are the portfolio manager for a LONG/SHORT trading competition (Mar 2 - Apr 3, 2026). You synthesize inputs from 6 specialist agents into a final portfolio of ~16 positions (8 long, 8 short) using a "War Pairs" strategy with 1.5x margin leverage (~$150K total buying power).

## Strategy: War Pairs

Three sleeves:
1. **War Longs (~35%)**: Defense, energy stocks benefiting from US-Iran conflict
2. **War Shorts (~30%)**: Airlines, travel, consumer stocks hurt by war
3. **Flexible (~35%)**: War-agnostic momentum plays (AI, cyber, financials) and weak shorts

## Constraints
- ~8 long positions, ~8 short positions
- Max single position: 12% of total buying power
- Long exposure: ~$80K, Short exposure: ~$70K
- Commission: $1.99 per trade
- Min short price: $5.00

## Stop-Losses
- War Longs: -15%, War Shorts: -25%, Flexible Longs: -12%, Flexible Shorts: -20%

## Contingency Plans
- Ceasefire: Close war shorts, trim war longs 50%, rotate to recovery plays
- Escalation (oil >$100): Add energy longs, add airline shorts
- FOMC surprise: Adjust rate-sensitive positions
```

**Step 2: Update imports in `agents/portfolio_manager.py`**

Replace lines 1-29 with:

```python
"""Agent 7: Portfolio Manager — synthesizes all analysis into final long/short picks."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import (
    COMPETITION_END,
    COMPETITION_START,
    MAX_PER_SECTOR,
    MAX_PORTFOLIO_STOCKS,
    MAX_SINGLE_WEIGHT,
    SCORING_WEIGHTS,
    SLEEVE_TARGETS,
    STOP_LOSS_DEFAULTS,
    TOTAL_BUYING_POWER,
)
from config.watchlist import TICKER_DIRECTION, TICKER_SLEEVE
from data.models import (
    CatalystHunterOutput,
    FundamentalScreenerOutput,
    MacroAnalysis,
    PortfolioManagerOutput,
    PositionDirection,
    PortfolioSleeve,
    RiskManagerOutput,
    SentimentAnalystOutput,
    TechnicalAnalystOutput,
)
```

**Step 3: Update gather_data method**

Replace the `gather_data` method (lines 37-105) to add direction/sleeve info:

```python
    async def gather_data(self) -> dict[str, Any]:
        logger.info(f"[{self.name}] Gathering all agent outputs...")

        macro: MacroAnalysis | None = self.bus.get("macro_analyst")
        fundamental: FundamentalScreenerOutput | None = self.bus.get("fundamental_screener")
        technical: TechnicalAnalystOutput | None = self.bus.get("technical_analyst")
        catalyst: CatalystHunterOutput | None = self.bus.get("catalyst_hunter")
        sentiment: SentimentAnalystOutput | None = self.bus.get("sentiment_analyst")
        risk: RiskManagerOutput | None = self.bus.get("risk_manager")

        consolidated = {}
        if fundamental:
            for c in fundamental.candidates:
                consolidated[c.ticker] = {
                    "ticker": c.ticker,
                    "name": c.name,
                    "sector": c.sector,
                    "stock_type": c.stock_type.value,
                    "direction": TICKER_DIRECTION.get(c.ticker, "long"),
                    "sleeve": TICKER_SLEEVE.get(c.ticker, "flexible"),
                    "fundamental_score": c.fundamental_score,
                    "fundamental_rationale": c.rationale,
                    "quality_score_algo": c.quality_score_algo,
                    "earnings_surprise_score_algo": c.earnings_surprise_score_algo,
                }

        if technical:
            for t in technical.analyses:
                if t.ticker in consolidated:
                    consolidated[t.ticker]["technical_score"] = t.technical_score
                    consolidated[t.ticker]["technical_rationale"] = t.rationale
                    consolidated[t.ticker]["current_price"] = t.current_price
                    consolidated[t.ticker]["momentum_score_algo"] = t.momentum_score_algo

        if catalyst:
            for c in catalyst.analyses:
                if c.ticker in consolidated:
                    consolidated[c.ticker]["catalyst_score"] = c.catalyst_score
                    consolidated[c.ticker]["catalyst_rationale"] = c.rationale
                    consolidated[c.ticker]["catalysts"] = [
                        cat.model_dump() for cat in c.catalysts
                    ]

        if sentiment:
            for s in sentiment.analyses:
                if s.ticker in consolidated:
                    consolidated[s.ticker]["sentiment_score"] = s.sentiment_score
                    consolidated[s.ticker]["sentiment_rationale"] = s.rationale
                    consolidated[s.ticker]["analyst_consensus"] = s.analyst_consensus

        if risk:
            for r in risk.analyses:
                if r.ticker in consolidated:
                    consolidated[r.ticker]["risk_score"] = r.risk_score
                    consolidated[r.ticker]["risk_rationale"] = r.rationale
                    consolidated[r.ticker]["suggested_weight"] = r.suggested_weight
                    consolidated[r.ticker]["beta"] = r.beta
                    consolidated[r.ticker]["volatility"] = r.volatility_annualized
                    consolidated[r.ticker]["risk_adjusted_score_algo"] = r.risk_adjusted_score_algo

        return {
            "consolidated": list(consolidated.values()),
            "macro_summary": macro.summary if macro else "N/A",
            "macro_regime": macro.regime.value if macro else "neutral",
            "favored_sectors": macro.favored_sectors if macro else [],
            "avoided_sectors": macro.avoided_sectors if macro else [],
            "risk_correlations": [
                cp.model_dump() for cp in risk.high_correlations
            ] if risk else [],
            "risk_diversification": risk.diversification_notes if risk else "N/A",
        }
```

**Step 4: Update analyze method**

Replace the `analyze` method (lines 107-182) with:

```python
    async def analyze(self, data: dict[str, Any]) -> PortfolioManagerOutput:
        prompt = f"""You are the Portfolio Manager for a LONG/SHORT trading competition
({COMPETITION_START} to {COMPETITION_END}). Strategy: "War Pairs" with 1.5x margin.

TOTAL BUYING POWER: ${TOTAL_BUYING_POWER:,.0f} (~$80K long, ~$70K short)

Your job is to SELECT ~{MAX_PORTFOLIO_STOCKS} STOCKS (8 long + 8 short), assign weights,
directions, sleeves, and provide investment theses.

SLEEVE ALLOCATION TARGETS:
{json.dumps(SLEEVE_TARGETS, indent=2)}

STOP-LOSS DEFAULTS:
{json.dumps(STOP_LOSS_DEFAULTS, indent=2)}

CONSTRAINTS:
1. ~8 long positions, ~8 short positions (~16 total)
2. Maximum {MAX_PER_SECTOR} stocks per sector (across both sides)
3. No single stock > {MAX_SINGLE_WEIGHT*100}% weight
4. Total long weights + total short weights = 100%
5. Long exposure target: ~53%, Short exposure target: ~47%

SCORING WEIGHTS:
{json.dumps(SCORING_WEIGHTS, indent=2)}

MACRO CONTEXT:
- Regime: {data['macro_regime']}
- Summary: {data['macro_summary']}
- Favored sectors (LONG): {data['favored_sectors']}
- Sectors to SHORT: {data.get('avoided_sectors', [])}

HIGH CORRELATIONS TO WATCH:
{json.dumps(data['risk_correlations'], indent=1, default=str)}

DIVERSIFICATION NOTES: {data['risk_diversification']}

CONSOLIDATED CANDIDATE DATA ({len(data['consolidated'])} stocks):
{json.dumps(data['consolidated'], indent=1, default=str)}

Each candidate has a "direction" (long/short) and "sleeve" (war_long/war_short/flexible).
Respect these — don't go long on a short candidate or vice versa.

ALGORITHMIC PRE-SCORES: Each candidate includes deterministic algo scores.
If any LLM-assigned score deviates by >15 points from algo counterpart, flag it.

For each stock provide: ticker, name, sector, stock_type, direction, sleeve, stop_loss_pct,
weight_pct, composite_score, all dimension scores, entry_strategy, exit_strategy, thesis.

CONTINGENCY PLANS (include in portfolio_rationale):
- Ceasefire: Close war shorts immediately, trim war longs 50%
- Escalation (oil >$100): Add energy longs, add airline shorts
- FOMC surprise: Adjust rate-sensitive positions

Respond with JSON:
{{
    "stocks": [
        {{
            "ticker": "LMT",
            "name": "Lockheed Martin",
            "sector": "Industrials",
            "stock_type": "evolution",
            "direction": "long",
            "sleeve": "war_long",
            "stop_loss_pct": 15.0,
            "weight_pct": 8.0,
            "composite_score": 82.5,
            "fundamental_score": 75.0,
            "technical_score": 80.0,
            "catalyst_score": 90.0,
            "sentiment_score": 85.0,
            "risk_score": 70.0,
            "entry_strategy": "Buy at market open",
            "exit_strategy": "Hold unless -15% stop hit or ceasefire announced",
            "thesis": "Top defense contractor directly benefiting from US-Iran war..."
        }},
        {{
            "ticker": "AAL",
            "name": "American Airlines",
            "sector": "Industrials",
            "stock_type": "evolution",
            "direction": "short",
            "sleeve": "war_short",
            "stop_loss_pct": 25.0,
            "weight_pct": 8.0,
            "composite_score": 78.0,
            "fundamental_score": 75.0,
            "technical_score": 72.0,
            "catalyst_score": 85.0,
            "sentiment_score": 80.0,
            "risk_score": 60.0,
            "entry_strategy": "Short at market open",
            "exit_strategy": "Cover if rises 25% or ceasefire announced",
            "thesis": "Worst balance sheet airline, fuel costs crushing margins..."
        }}
    ],
    "portfolio_rationale": "War Pairs strategy rationale with contingency plans...",
    "long_count": 8,
    "short_count": 8,
    "long_exposure_pct": 53.0,
    "short_exposure_pct": 47.0,
    "sector_breakdown": {{"Industrials": 4, "Energy": 3, "Technology": 4, ...}},
    "expected_portfolio_beta": 0.2,
    "key_risks": ["ceasefire reversal", "oil collapse", "margin call in crash"],
    "key_catalysts": ["oil >$100", "FOMC Mar 17-18", "US-China mid-March meeting"]
}}"""

        response = self._call_llm(prompt)
        return self._parse_json_response(response, PortfolioManagerOutput)
```

**Step 5: Commit**

```bash
git add agents/portfolio_manager.py config/prompts/portfolio_manager.md
git commit -m "feat: update portfolio manager for long/short war pairs construction"
```

---

### Task 11: Update Excel Generator

**Files:**
- Modify: `output/excel_generator.py:82-123` (_build_portfolio_summary)
- Modify: `output/excel_generator.py:318-426` (_build_scoring_matrix)

**Step 1: Update _build_portfolio_summary to show direction**

In `_build_portfolio_summary`, replace the headers and rows section (lines 92-102) with:

```python
    headers = [
        "Ticker", "Name", "Direction", "Sleeve", "Sector", "Composite Score",
        "Weight %", "Stop-Loss %", "Entry Strategy", "Exit Strategy", "Thesis",
    ]
    rows = []
    for s in sorted(portfolio.stocks, key=lambda x: x.composite_score, reverse=True):
        rows.append([
            s.ticker, s.name,
            s.direction.value.upper() if hasattr(s, 'direction') else "LONG",
            s.sleeve.value.replace("_", " ").title() if hasattr(s, 'sleeve') else "N/A",
            s.sector,
            round(s.composite_score, 1), round(s.weight_pct, 1),
            round(s.stop_loss_pct, 1) if hasattr(s, 'stop_loss_pct') else "N/A",
            s.entry_strategy, s.exit_strategy, s.thesis,
        ])
```

Also update line 90 to show long/short counts:
```python
    ws.cell(row=4, column=1, value=f"Long: {portfolio.long_count} | Short: {portfolio.short_count} | Long Exposure: {portfolio.long_exposure_pct}% | Short Exposure: {portfolio.short_exposure_pct}%")
```

And update the thesis column reference from "I" to "K":
```python
    ws.column_dimensions["K"].width = 60
```

**Step 2: Update _build_scoring_matrix to include direction**

In the headers list (lines 394-401), add "Direction" after "Type":

```python
    headers = [
        "Ticker", "Name", "Sector", "Type", "Direction",
        "Fund", "Fund Algo (Qual)", "Fund Algo (Earn)",
        "Tech", "Tech Algo (Mom)",
        "Catalyst", "Sentiment",
        "Risk", "Risk Algo",
        "Composite", "Selected",
    ]
```

And in the row building (lines 403-416), add direction:
```python
    for r in rows_data:
        rows.append([
            r.ticker, r.name, r.sector, r.stock_type.value.title(),
            r.direction.value.upper() if hasattr(r, 'direction') else "LONG",
            round(r.fundamental_score, 1),
            ...  # rest stays the same
        ])
```

Update the selected column check from column 15 to column 16.

**Step 3: Commit**

```bash
git add output/excel_generator.py
git commit -m "feat: update Excel generator to show direction, sleeve, and stop-loss"
```

---

### Task 12: Update README

**Files:**
- Modify: `README.md`

**Step 1: Update README to reflect Round 2 changes**

Update key sections:
- Competition details: Round 2 dates, long/short allowed
- Strategy: War Pairs instead of Evolution/Revolution
- Portfolio constraints: 8 long + 8 short, sleeve targets
- Scoring weights: updated for Round 2

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Round 2 War Pairs strategy"
```

---

### Task 13: Run Full Test Suite and Verify

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Fix any import errors or type mismatches**

Check that all agents can be imported without errors:

```bash
python -c "from agents.macro_analyst import MacroAnalyst; from agents.fundamental_screener import FundamentalScreener; from agents.technical_analyst import TechnicalAnalyst; from agents.catalyst_hunter import CatalystHunter; from agents.sentiment_analyst import SentimentAnalyst; from agents.risk_manager import RiskManager; from agents.portfolio_manager import PortfolioManager; print('All agents imported successfully')"
```

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve import and type issues from Round 2 migration"
```

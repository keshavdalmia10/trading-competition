# Trading Competition Multi-Agent Analysis System

## Overview

This is an AI-powered multi-agent system designed for a 3-week college stock trading competition on the Investopedia Simulator, running from **February 9 to March 2, 2026**. The system analyzes and selects up to 10 stocks with "evolution or revolution" properties—companies driving transformative change in their industries or fundamentally disrupting traditional markets.

The system leverages multiple specialized AI agents working in a coordinated pipeline to perform macro analysis, fundamental screening, technical analysis, catalyst identification, sentiment analysis, risk management, and portfolio construction. The final output is a comprehensive Excel workbook with detailed recommendations and analysis.

## Architecture

The system uses a **7-agent pipeline architecture** organized in three phases:

```
Phase 0 (Sequential):   Macro Analyst → Fundamental Screener
                                              ↓ (top ~20 tickers)
Phase 1 (Parallel):     Technical Analyst ─┐
                        Catalyst Hunter   ─┼── run concurrently
                        Sentiment Analyst ─┘
                                              ↓
Phase 2 (Sequential):   Risk Manager → Portfolio Manager → Excel Report
```

### Agent Descriptions

**Phase 0: Market Understanding & Initial Screening**

1. **Macro Analyst**: Analyzes current macroeconomic conditions including interest rates, inflation, GDP growth, sector trends, and market regime. Provides market context and identifies favorable sectors/themes for the competition period.

2. **Fundamental Screener**: Performs quantitative screening of the stock universe based on financial metrics (growth, profitability, valuation) and filters for "evolution or revolution" characteristics. Outputs ~20 top-ranked tickers for deeper analysis.

**Phase 1: Deep Multi-Dimensional Analysis (Parallel)**

3. **Technical Analyst**: Analyzes price action, trend strength, momentum indicators, support/resistance levels, and chart patterns for each screened ticker. Assigns technical scores based on entry timing and trend quality.

4. **Catalyst Hunter**: Identifies upcoming catalysts including earnings dates, product launches, regulatory decisions, industry events, and other potential stock-moving events. Evaluates catalyst timing and magnitude.

5. **Sentiment Analyst**: Analyzes news sentiment, social media buzz, analyst ratings, and market positioning. Uses VADER sentiment analysis and news aggregation to gauge market perception.

**Phase 2: Risk Management & Portfolio Construction**

6. **Risk Manager**: Evaluates volatility, beta, correlation, sector concentration, liquidity, and downside risks for each stock. Assigns risk scores and identifies potential red flags.

7. **Portfolio Manager**: Synthesizes all agent outputs using weighted scoring system. Constructs final portfolio of up to 10 stocks, allocates position sizes, and ensures compliance with portfolio constraints. Uses advanced reasoning (Grok model) for final decision-making.

## Setup

### Prerequisites

- Python 3.11 or higher
- API keys for external data sources (see Environment Variables below)

### Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Fill in the required API keys in the `.env` file in the project root:
```
GROK_API_KEY=your_grok_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
FRED_API_KEY=your_fred_api_key_here
NEWSAPI_KEY=your_newsapi_key_here
FINNHUB_KEY=your_finnhub_key_here
```

### LLM Providers

The system uses two LLM providers for optimal cost-performance balance:

- **Grok (xAI)**: Used for the Portfolio Manager agent due to superior reasoning capabilities for complex decision-making and portfolio construction
- **Claude (Anthropic)**: Used for all analysis agents (Macro, Fundamental, Technical, Catalyst, Sentiment, Risk) due to strong reasoning capabilities and reliable structured output

## Usage

Run the entire pipeline with a single command:

```bash
python main.py
```

The system will:
1. Execute Phase 0 agents sequentially
2. Run Phase 1 agents in parallel for efficiency
3. Execute Phase 2 agents sequentially
4. Generate a comprehensive Excel report in `output/reports/`

Execution time: Approximately 10-15 minutes depending on API response times.

## Scoring System

The Portfolio Manager uses a weighted scoring system to rank and select stocks. Each dimension is normalized to 0-100 scale:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Technical** | 25% | Chart patterns, momentum, trend strength, entry timing |
| **Catalyst** | 25% | Upcoming events, catalyst timing, magnitude of potential impact |
| **Risk** | 20% | Volatility, beta, liquidity, downside protection (inverse scoring) |
| **Fundamental** | 15% | Growth metrics, profitability, valuation, competitive position |
| **Sentiment** | 15% | News sentiment, analyst ratings, market positioning |

**Total Score** = (Technical × 0.25) + (Catalyst × 0.25) + (Risk × 0.20) + (Fundamental × 0.15) + (Sentiment × 0.15)

Stocks are ranked by total score, then filtered through portfolio constraints to produce the final selection.

## Output

The system generates a multi-sheet Excel workbook saved to `output/reports/` with the following structure:

- **Portfolio Summary**: Final portfolio composition, position sizes, allocation percentages, aggregate metrics
- **Macro Overview**: Economic analysis, sector trends, market regime assessment, competition period outlook
- **Stock Sheets (×10)**: Individual analysis for each selected stock including:
  - Company overview and thesis
  - Technical analysis with key levels
  - Fundamental metrics
  - Upcoming catalysts
  - Sentiment summary
  - Risk assessment
  - Score breakdown
- **Scoring Matrix**: Complete scoring table for all analyzed stocks showing dimension scores and rankings
- **Risk Analysis**: Portfolio-level risk metrics including correlation matrix, sector concentration, VaR estimates

File naming convention: `trading_competition_YYYYMMDD_HHMMSS.xlsx`

## Project Structure

```
trading_competition/
├── agents/                          # AI agent implementations
│   ├── __init__.py
│   ├── base_agent.py               # Base agent class with LLM interface
│   ├── macro_analyst.py            # Phase 0: Macro analysis
│   ├── fundamental_screener.py     # Phase 0: Stock screening
│   ├── technical_analyst.py        # Phase 1: Technical analysis
│   ├── catalyst_hunter.py          # Phase 1: Catalyst identification
│   ├── sentiment_analyst.py        # Phase 1: Sentiment analysis
│   ├── risk_manager.py             # Phase 2: Risk assessment
│   └── portfolio_manager.py        # Phase 2: Portfolio construction
├── config/                          # Configuration and settings
│   ├── __init__.py
│   ├── settings.py                 # System configuration
│   ├── watchlist.py                # Initial stock universe
│   └── prompts/                    # Agent prompt templates
│       └── macro_analyst.md
├── data/                            # Data models and sources
│   ├── __init__.py
│   ├── models.py                   # Pydantic data models
│   ├── cache/                      # Local data cache
│   └── sources/                    # External data integrations
│       ├── __init__.py
│       ├── yahoo_finance.py        # yfinance wrapper
│       ├── fred_api.py             # Federal Reserve Economic Data
│       ├── news_api.py             # News aggregation
│       ├── finnhub_client.py       # Market data and earnings
│       └── stock_screener.py       # Dynamic stock screening
├── orchestrator/                    # Pipeline coordination
│   ├── __init__.py
│   ├── pipeline.py                 # Phase orchestration logic
│   └── message_bus.py              # Inter-agent communication
├── output/                          # Report generation
│   ├── __init__.py
│   ├── excel_generator.py          # Excel workbook builder
│   └── reports/                    # Generated reports directory
├── tools/                           # Utility functions
│   ├── __init__.py
│   ├── technical_indicators.py     # TA calculations
│   ├── scoring.py                  # Scoring algorithms
│   └── position_sizing.py          # Portfolio allocation logic
├── tests/                           # Unit tests
│   └── __init__.py
├── main.py                          # Entry point
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (not in git)
├── .gitignore
└── README.md
```

## Portfolio Constraints

The Portfolio Manager enforces the following constraints during portfolio construction:

- **Maximum Stocks**: Up to 10 positions
- **Sector Diversification**: Maximum 3 stocks per GICS sector
- **Theme Balance**: At least 3 "evolution" stocks AND at least 3 "revolution" stocks
- **Position Sizing**: No single stock can exceed 15% of portfolio weight
- **Minimum Position**: No position smaller than 5% (to ensure meaningful exposure)
- **Full Investment**: Portfolio must be 95-100% invested (max 5% cash)

These constraints ensure diversification while maintaining concentrated exposure to the highest-conviction ideas.

## Data Sources

The system integrates multiple data sources for comprehensive analysis:

| Source | Purpose | API Key Required |
|--------|---------|------------------|
| **yfinance** | Primary source for stock prices, fundamentals, historical data | No |
| **FRED API** | Macroeconomic indicators (interest rates, inflation, GDP) | Yes |
| **NewsAPI** | News article aggregation and sentiment analysis | Yes |
| **Finnhub** | Earnings dates, analyst estimates, insider trading | Yes |
| **Stock Screener** | Dynamic filtering of stock universe by criteria | No |

Note: yfinance is the primary data source and does not require an API key, making the system accessible even with limited API access.

## Competition Notes

**Competition Details:**
- Platform: Investopedia Stock Simulator
- Duration: 3 weeks (Feb 9 - Mar 2, 2026)
- Starting Capital: $100,000 virtual cash
- Goal: Maximum absolute return

**Strategy Focus:**
- "Evolution or Revolution" theme emphasizes transformative companies
- Short-term time horizon (3 weeks) increases weight on Technical and Catalyst dimensions
- System optimizes for momentum + upcoming catalysts rather than long-term fundamentals
- Risk management prevents catastrophic losses while maintaining upside exposure

## License

This project is for educational and competition purposes.

## Contributing

This is a competition project. External contributions are not currently accepted.

---

**Last Updated**: February 9, 2026

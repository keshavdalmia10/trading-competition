"""Pydantic models defining the data contracts between agents."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────

class StockType(str, Enum):
    EVOLUTION = "evolution"
    REVOLUTION = "revolution"


class MarketRegime(str, Enum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NEUTRAL = "neutral"


class CatalystImpact(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CatalystDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


# ── Macro Analyst Output ──────────────────────────────────────────────────

class MacroIndicator(BaseModel):
    name: str
    value: float
    interpretation: str


class MacroAnalysis(BaseModel):
    regime: MarketRegime
    regime_rationale: str
    favored_sectors: list[str]
    avoided_sectors: list[str]
    macro_score: float = Field(ge=0, le=100, description="0-100 macro health score")
    indicators: list[MacroIndicator]
    key_events: list[str] = Field(default_factory=list)
    summary: str


# ── Fundamental Screener Output ───────────────────────────────────────────

class FundamentalData(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    eps_growth_yoy: Optional[float] = None
    roe: Optional[float] = None
    fcf: Optional[float] = None
    earnings_surprise_pct: Optional[float] = None
    stock_type: StockType
    quality_score_algo: Optional[float] = Field(None, ge=0, le=100, description="Piotroski F-Score quality score")
    earnings_surprise_score_algo: Optional[float] = Field(None, ge=0, le=100, description="Deterministic earnings surprise score")
    fundamental_score: float = Field(ge=0, le=100)
    rationale: str


class FundamentalScreenerOutput(BaseModel):
    candidates: list[FundamentalData]
    screening_summary: str


# ── Technical Analyst Output ──────────────────────────────────────────────

class TechnicalData(BaseModel):
    ticker: str
    current_price: float
    rsi_14: Optional[float] = None
    macd_signal: Optional[str] = None  # "bullish", "bearish", "neutral"
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    above_sma_20: Optional[bool] = None
    above_sma_50: Optional[bool] = None
    above_sma_200: Optional[bool] = None
    bollinger_position: Optional[str] = None  # "upper", "middle", "lower"
    volume_trend: Optional[str] = None  # "increasing", "decreasing", "stable"
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    momentum_score_algo: Optional[float] = Field(None, ge=0, le=100, description="Deterministic momentum score")
    technical_score: float = Field(ge=0, le=100)
    rationale: str


class TechnicalAnalystOutput(BaseModel):
    analyses: list[TechnicalData]
    summary: str


# ── Catalyst Hunter Output ────────────────────────────────────────────────

class Catalyst(BaseModel):
    event: str
    date: Optional[str] = None
    impact: CatalystImpact
    direction: CatalystDirection
    description: str


class CatalystData(BaseModel):
    ticker: str
    catalysts: list[Catalyst]
    catalyst_score: float = Field(ge=0, le=100)
    rationale: str


class CatalystHunterOutput(BaseModel):
    analyses: list[CatalystData]
    summary: str


# ── Sentiment Analyst Output ──────────────────────────────────────────────

class SentimentData(BaseModel):
    ticker: str
    overall_sentiment: float = Field(ge=-1, le=1, description="-1 bearish to +1 bullish")
    analyst_consensus: Optional[str] = None  # "strong buy", "buy", "hold", "sell"
    analyst_target_price: Optional[float] = None
    recent_upgrades: int = 0
    recent_downgrades: int = 0
    key_headlines: list[str] = Field(default_factory=list)
    sentiment_score: float = Field(ge=0, le=100)
    rationale: str


class SentimentAnalystOutput(BaseModel):
    analyses: list[SentimentData]
    summary: str


# ── Risk Manager Output ───────────────────────────────────────────────────

class RiskData(BaseModel):
    ticker: str
    beta: Optional[float] = None
    volatility_annualized: Optional[float] = None
    max_drawdown_90d: Optional[float] = None
    value_at_risk_95: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    ewma_volatility: Optional[float] = None
    garch_forecast: Optional[float] = None
    vol_regime: Optional[str] = None  # "high", "normal", "low"
    risk_adjusted_score_algo: Optional[float] = Field(None, ge=0, le=100, description="Deterministic risk-adjusted score")
    risk_score: float = Field(ge=0, le=100, description="Higher = better risk-adjusted")
    suggested_weight: float = Field(ge=0, le=1)
    rationale: str


class CorrelationPair(BaseModel):
    ticker_a: str
    ticker_b: str
    correlation: float


class RiskManagerOutput(BaseModel):
    analyses: list[RiskData]
    high_correlations: list[CorrelationPair] = Field(default_factory=list)
    portfolio_beta: Optional[float] = None
    diversification_notes: str
    summary: str


# ── Portfolio Manager Output ──────────────────────────────────────────────

class PortfolioStock(BaseModel):
    ticker: str
    name: str
    sector: str
    stock_type: StockType
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


class PortfolioManagerOutput(BaseModel):
    stocks: list[PortfolioStock]
    portfolio_rationale: str
    evolution_count: int
    revolution_count: int
    sector_breakdown: dict[str, int]
    expected_portfolio_beta: Optional[float] = None
    key_risks: list[str]
    key_catalysts: list[str]


# ── Scoring Matrix (for Excel output) ────────────────────────────────────

class ScoringRow(BaseModel):
    ticker: str
    name: str
    sector: str
    stock_type: StockType
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

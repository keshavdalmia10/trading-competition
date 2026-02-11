"""Composite scoring formulas for the trading competition."""

from __future__ import annotations

from config.settings import SCORING_WEIGHTS
from data.models import ScoringRow


def compute_composite_score(
    fundamental: float,
    technical: float,
    catalyst: float,
    sentiment: float,
    risk: float,
) -> float:
    """
    Compute weighted composite score from sub-scores.
    All inputs should be 0-100. Returns 0-100.
    """
    w = SCORING_WEIGHTS
    score = (
        fundamental * w["fundamental"]
        + technical * w["technical"]
        + catalyst * w["catalyst"]
        + sentiment * w["sentiment"]
        + risk * w["risk"]
    )
    return round(min(100, max(0, score)), 2)


def rank_candidates(rows: list[ScoringRow]) -> list[ScoringRow]:
    """Sort candidates by composite score descending."""
    return sorted(rows, key=lambda r: r.composite_score, reverse=True)


def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """Normalize a raw value to 0-100 scale."""
    if max_val == min_val:
        return 50.0
    normalized = (value - min_val) / (max_val - min_val) * 100
    return round(min(100, max(0, normalized)), 2)

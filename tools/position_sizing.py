"""Position sizing utilities for portfolio construction."""

from __future__ import annotations

import numpy as np
from loguru import logger

from config.settings import MAX_SINGLE_WEIGHT


def inverse_volatility_weights(volatilities: dict[str, float]) -> dict[str, float]:
    """
    Compute position weights inversely proportional to volatility.
    Higher volatility → smaller position.
    """
    if not volatilities:
        return {}

    inv_vols = {t: 1.0 / max(v, 0.01) for t, v in volatilities.items()}
    total = sum(inv_vols.values())
    weights = {t: v / total for t, v in inv_vols.items()}

    # Cap at max single weight
    weights = _cap_weights(weights, MAX_SINGLE_WEIGHT)
    return weights


def score_based_weights(scores: dict[str, float]) -> dict[str, float]:
    """
    Weight positions proportionally to their composite scores.
    """
    if not scores:
        return {}

    total = sum(scores.values())
    if total == 0:
        n = len(scores)
        return {t: 1.0 / n for t in scores}

    weights = {t: s / total for t, s in scores.items()}
    weights = _cap_weights(weights, MAX_SINGLE_WEIGHT)
    return weights


def blend_weights(
    score_weights: dict[str, float],
    vol_weights: dict[str, float],
    score_blend: float = 0.6,
) -> dict[str, float]:
    """
    Blend score-based and volatility-based weights.
    score_blend=0.6 means 60% score-based, 40% vol-based.
    """
    tickers = set(score_weights) | set(vol_weights)
    blended = {}
    for t in tickers:
        sw = score_weights.get(t, 0)
        vw = vol_weights.get(t, 0)
        blended[t] = score_blend * sw + (1 - score_blend) * vw

    # Renormalize
    total = sum(blended.values())
    if total > 0:
        blended = {t: w / total for t, w in blended.items()}

    blended = _cap_weights(blended, MAX_SINGLE_WEIGHT)
    return blended


def _cap_weights(weights: dict[str, float], max_weight: float) -> dict[str, float]:
    """Cap individual weights and redistribute excess proportionally."""
    capped = {}
    excess = 0.0
    uncapped_total = 0.0

    for t, w in weights.items():
        if w > max_weight:
            capped[t] = max_weight
            excess += w - max_weight
        else:
            capped[t] = w
            uncapped_total += w

    # Redistribute excess proportionally among uncapped
    if excess > 0 and uncapped_total > 0:
        for t in capped:
            if capped[t] < max_weight:
                capped[t] += excess * (capped[t] / uncapped_total)

    # Final normalization
    total = sum(capped.values())
    if total > 0 and abs(total - 1.0) > 0.001:
        capped = {t: w / total for t, w in capped.items()}

    return {t: round(w, 4) for t, w in capped.items()}

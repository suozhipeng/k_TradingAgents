"""V1.7 Stock Analysis V2 — comprehensive scoring and risk list integration.

Rules:
- unavailable dimensions don't count as 0, weights are re-normalized
- less than 5 valid dimensions → overall status = partial
- confidence drops with fewer dimensions
"""

from __future__ import annotations

from typing import Any

DEFAULT_WEIGHTS = {
    "technical": 0.20,
    "fundamental": 0.20,
    "valuation": 0.10,
    "capital_flow": 0.10,
    "news": 0.10,
    "sector": 0.10,
    "sentiment": 0.10,
    "risk": 0.10,
}

COMPREHENSIVE_STRATEGIES = {
    "aggressive": {"technical": 0.30, "capital_flow": 0.20, "sentiment": 0.15,
                   "sector": 0.15, "fundamental": 0.10, "valuation": 0.05,
                   "news": 0.03, "risk": 0.02},
    "conservative": {"fundamental": 0.30, "valuation": 0.20, "risk": 0.15,
                     "technical": 0.15, "sector": 0.08, "sentiment": 0.05,
                     "capital_flow": 0.05, "news": 0.02},
}


def compute_comprehensive_score(
    dimensions: dict[str, dict[str, Any]],
    strategy: str = "default",
) -> dict[str, Any]:
    """Compute comprehensive stock score using V1.7 rules.

    Args:
        dimensions: dict of dimension -> {status, score, confidence}
        strategy: default | aggressive | conservative

    Returns:
        {score, confidence, status, weighted_dimensions, strategy}
    """
    weights = DEFAULT_WEIGHTS.copy()
    if strategy in COMPREHENSIVE_STRATEGIES:
        weights = COMPREHENSIVE_STRATEGIES[strategy]

    valid_count = 0
    weighted_sum = 0.0
    total_weight = 0.0
    dims_info: dict[str, dict] = {}
    risk_penalty = 0.0

    for dim, w in weights.items():
        info = dimensions.get(dim, {})
        status = info.get("status", "unavailable")
        score = info.get("score", 0)
        confidence = info.get("confidence", 0.0)

        if status == "unavailable":
            continue  # skip unavailable, renormalize weight

        valid_count += 1
        total_weight += w
        weighted_sum += score * w * confidence

        # Extract risk penalty
        if dim == "risk":
            risks = info.get("risks", [])
            risk_penalty = min(len(risks) * 0.05, 0.30)

        dims_info[dim] = {
            "status": status,
            "score": score,
            "confidence": confidence,
            "weight": w,
        }

    if valid_count < 1:
        return {
            "status": "unavailable",
            "score": 0,
            "confidence": 0.0,
            "weighted_dimensions": dims_info,
            "strategy": strategy,
        }

    overall_status = "available" if valid_count >= 5 else "partial"
    raw_score = (weighted_sum / total_weight * 100) if total_weight > 0 else 0
    final_score = max(0, min(100, raw_score * (1 - risk_penalty)))
    confidence = min(1.0, valid_count / 8)

    return {
        "status": overall_status,
        "score": round(final_score, 1),
        "confidence": round(confidence, 3),
        "weighted_dimensions": dims_info,
        "valid_dimensions": valid_count,
        "strategy": strategy,
        "risk_penalty": round(risk_penalty, 4),
    }

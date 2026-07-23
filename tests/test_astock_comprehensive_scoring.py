"""Tests for V1.7 Stock Analysis V2 comprehensive scoring."""

from tradingagents.astock.analysis.scoring_v17 import compute_comprehensive_score


def test_all_dimensions_available():
    dims = {d: {"status": "available", "score": 70, "confidence": 0.8}
            for d in ("technical", "fundamental", "valuation", "capital_flow",
                      "news", "sector", "sentiment", "risk")}
    result = compute_comprehensive_score(dims)
    assert result["status"] == "available"
    assert result["score"] > 0
    assert result["confidence"] > 0


def test_partial_when_less_than_5_dimensions():
    dims = {"technical": {"status": "available", "score": 70, "confidence": 0.8},
            "fundamental": {"status": "unavailable", "score": 0, "confidence": 0}}
    result = compute_comprehensive_score(dims)
    assert result["status"] == "partial"


def test_unavailable_does_not_count_as_zero():
    dims = {"technical": {"status": "available", "score": 100, "confidence": 1.0},
            "fundamental": {"status": "available", "score": 100, "confidence": 1.0},
            "valuation": {"status": "unavailable", "score": 0, "confidence": 0},
            "capital_flow": {"status": "available", "score": 100, "confidence": 1.0},
            "news": {"status": "unavailable", "score": 0, "confidence": 0},
            "sector": {"status": "available", "score": 100, "confidence": 1.0},
            "sentiment": {"status": "available", "score": 100, "confidence": 1.0},
            "risk": {"status": "available", "score": 0, "confidence": 1.0}}
    result = compute_comprehensive_score(dims)
    # With 6 valid dims, unavailable weights are renormalized
    assert result["status"] == "available"
    assert result["score"] > 0


def test_aggressive_strategy():
    dims = {d: {"status": "available", "score": 70, "confidence": 0.8}
            for d in ("technical", "fundamental", "valuation", "capital_flow",
                      "news", "sector", "sentiment", "risk")}
    result = compute_comprehensive_score(dims, strategy="aggressive")
    assert result["strategy"] == "aggressive"


def test_risk_penalty_reduces_score():
    dims_no_risk = {d: {"status": "available", "score": 100, "confidence": 1.0,
                        "risks": []}
                    for d in ("technical", "fundamental", "valuation", "capital_flow",
                              "news", "sector", "sentiment", "risk")}
    dims_w_risk = {d: {"status": "available", "score": 100, "confidence": 1.0,
                       "risks": [{"severity": "high"}, {"severity": "medium"}]}
                   for d in ("technical", "fundamental", "valuation", "capital_flow",
                             "news", "sector", "sentiment", "risk")}
    result_no = compute_comprehensive_score(dims_no_risk)
    result_w = compute_comprehensive_score(dims_w_risk)
    assert result_w["score"] <= result_no["score"]


def test_unavailable_when_no_valid():
    result = compute_comprehensive_score({})
    assert result["status"] == "unavailable"

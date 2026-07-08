"""Report object for the A-share research bridge.

``AStockGraphReport`` is the stable, serializable output contract returned
by :class:`AStockGraphRuntime.run()`.  It carries structured section results,
Phase 09 advisory state, and a compatibility adapter that flattens into the
legacy ``TradingAgents`` state shape.

All helper functions in this module operate on ``AStockGraphReport`` or on
the intermediate section payloads produced by the bridge chain.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from tradingagents.astock.phase9_schemas import (
    PortfolioDecision,
    PortfolioDisposition,
    ResearchConclusion,
    ResearchRecommendation,
    RiskDecision,
    RiskLevel,
    RiskVerdict,
    TraderCandidateAction,
    TraderProposal,
)

_DEFAULT_SECTIONS: tuple[str, ...] = (
    "market",
    "news",
    "fundamentals",
    "announcements",
    "research",
)
_RESEARCH_ONLY_SIGNAL = "ResearchOnly"


# ---------------------------------------------------------------------------
# Report helpers (standalone functions)
# ---------------------------------------------------------------------------

def _section_text(section: Mapping[str, Any], fallback: str) -> str:
    summary = section.get("summary") if isinstance(section, Mapping) else None
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    error = section.get("error") if isinstance(section, Mapping) else None
    if isinstance(error, str) and error.strip():
        return error.strip()
    status = section.get("status") if isinstance(section, Mapping) else None
    if isinstance(status, str) and status.strip():
        return status.strip()
    return fallback


def _extract_debate_text(payload: Mapping[str, Any], key: str) -> str:
    if not isinstance(payload, Mapping):
        return ""
    debate_state = payload.get("investment_debate_state")
    if isinstance(debate_state, Mapping):
        value = debate_state.get(key)
        if isinstance(value, str):
            return value
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _is_data_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return True


def _describe_data_shape(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return {"kind": "mapping", "size": len(value), "keys": list(value)[:8]}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {"kind": "sequence", "size": len(value)}
    if value is None:
        return {"kind": "none", "size": 0}
    if isinstance(value, str):
        return {"kind": "string", "size": len(value)}
    return {"kind": type(value).__name__, "size": 1}


def _build_section_results(
    sections_payload: Mapping[str, Any],
    requested_sections: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for section_name in requested_sections:
        section = sections_payload.get(section_name, {}) if isinstance(sections_payload, Mapping) else {}
        source = section.get("source") if isinstance(section, Mapping) else None
        status = section.get("status") if isinstance(section, Mapping) else "unknown"
        summary = _section_text(section, f"{section_name} section unavailable")
        data = section.get("data") if isinstance(section, Mapping) else None
        error = section.get("error") if isinstance(section, Mapping) else None
        results[section_name] = {
            "status": status,
            "source": source,
            "summary": summary,
            "error": error,
            "has_data": _is_data_present(data),
            "data_shape": _describe_data_shape(data),
        }
    return results


def _build_provider_coverage(section_results: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    coverage: Dict[str, Dict[str, Any]] = {}
    for section_name, result in section_results.items():
        coverage[section_name] = {
            "source": result.get("source"),
            "status": result.get("status"),
            "available": result.get("status") == "ok" and result.get("has_data", False),
        }
    return coverage


def _build_missing_data_notes(section_results: Mapping[str, Any]) -> list[str]:
    notes: list[str] = []
    for section_name, result in section_results.items():
        if not result.get("has_data", False):
            summary = result.get("summary") or f"{section_name} unavailable"
            notes.append(f"{section_name}: {summary}")
    return notes


def _build_degradation_notes(
    section_results: Mapping[str, Any],
    missing_sections: Sequence[str],
) -> list[str]:
    notes: list[str] = []
    for section_name in missing_sections:
        result = section_results.get(section_name, {})
        status = result.get("status", "unknown")
        summary = result.get("summary") or f"{section_name} degraded"
        notes.append(f"{section_name} [{status}]: {summary}")
    return notes


def _build_view_text(
    payload: Mapping[str, Any],
    *,
    preferred_keys: Sequence[str],
    fallback: str,
) -> str:
    if not isinstance(payload, Mapping):
        return fallback
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if "investment_debate_state" in payload and isinstance(payload["investment_debate_state"], Mapping):
        debate_state = payload["investment_debate_state"]
        for key in preferred_keys:
            value = debate_state.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _derive_research_recommendation(summary: str) -> ResearchRecommendation:
    lowered = summary.lower()
    if any(token in lowered for token in ("buy", "accumulate", "add")):
        return ResearchRecommendation.BUY_BIAS
    if any(token in lowered for token in ("sell", "reduce", "exit")):
        return ResearchRecommendation.SELL_BIAS
    if "hold" in lowered or "watch" in lowered:
        return ResearchRecommendation.HOLD_BIAS
    return ResearchRecommendation.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Advisory helpers (Phase 09)
# ---------------------------------------------------------------------------

def _make_advisory_id(prefix: str, symbol: str, trade_date: Optional[str]) -> str:
    import re
    compact_symbol = re.sub(r"[^A-Za-z0-9]", "", symbol)
    compact_date = re.sub(r"[^0-9]", "", trade_date or "undated")
    return f"{prefix}-{compact_symbol.lower()}-{compact_date}"


def _build_trader_proposal(
    conclusion: ResearchConclusion,
    *,
    status: str,
    missing_data_notes: Sequence[str],
) -> TraderProposal:
    action_map = {
        ResearchRecommendation.BUY_BIAS: TraderCandidateAction.CONSIDER_BUY,
        ResearchRecommendation.HOLD_BIAS: TraderCandidateAction.HOLD,
        ResearchRecommendation.SELL_BIAS: TraderCandidateAction.CONSIDER_REDUCE,
        ResearchRecommendation.INSUFFICIENT_DATA: TraderCandidateAction.AVOID,
    }
    candidate_action = action_map[conclusion.recommendation]
    degraded = conclusion.recommendation is ResearchRecommendation.INSUFFICIENT_DATA
    entry_zone = None
    position_cap_pct = None
    if candidate_action is TraderCandidateAction.CONSIDER_BUY:
        position_cap_pct = 12.0 if status == "ok" else 6.0
        entry_zone = "Observe support/resistance confirmation before any later simulation step."
    elif candidate_action is TraderCandidateAction.HOLD:
        position_cap_pct = 8.0 if status == "ok" else 5.0
    elif candidate_action is TraderCandidateAction.CONSIDER_REDUCE:
        position_cap_pct = 4.0
        entry_zone = "Use rally strength as an advisory reduce zone; no order path is enabled."

    invalidation_conditions = list(conclusion.uncertainties)
    invalidation_conditions.append("Any later stage must keep actionable=false and execution_signal=ResearchOnly.")
    if degraded:
        invalidation_conditions.append("Provider degradation blocks any stronger advisory action.")

    rationale = (
        f"Trader advisory derived from ResearchConclusion: {conclusion.summary} "
        f"Bull case: {conclusion.bull_case or 'n/a'}. "
        f"Bear case: {conclusion.bear_case or 'n/a'}."
    )
    if missing_data_notes:
        rationale += f" Outstanding data gaps: {'; '.join(missing_data_notes)}."

    return TraderProposal(
        proposal_id=_make_advisory_id("tp", conclusion.symbol, conclusion.trade_date),
        research_conclusion_id=_make_advisory_id("rc", conclusion.symbol, conclusion.trade_date),
        candidate_action=candidate_action,
        rationale=rationale,
        entry_zone=entry_zone,
        invalidation_conditions=invalidation_conditions,
        position_cap_pct=position_cap_pct,
        confidence=0.0 if degraded else max(0.1, min(conclusion.confidence, 0.85)),
    )


def _render_risk_viewpoints(
    proposal: TraderProposal,
    conclusion: ResearchConclusion,
    *,
    status: str,
    missing_data_notes: Sequence[str],
) -> Dict[str, str]:
    shared_gap = "; ".join(missing_data_notes) if missing_data_notes else "no material provider gaps"
    return {
        "aggressive": (
            f"Aggressive Analyst: The proposal is {proposal.candidate_action.value}. "
            f"Upside comes from {conclusion.bull_case or 'the positive research view'}, "
            f"but current data quality is {status}. Gaps: {shared_gap}."
        ),
        "conservative": (
            f"Conservative Analyst: Preserve the research-only boundary. "
            f"Main downside is {conclusion.bear_case or 'unresolved downside risk'}. "
            f"Any missing evidence should cap exposure and block execution."
        ),
        "neutral": (
            f"Neutral Analyst: Balance the bull/bear cases, keep the proposal advisory-only, "
            f"and re-run research when the following gaps are cleared: {shared_gap}."
        ),
    }


def _build_risk_decision(
    proposal: TraderProposal,
    conclusion: ResearchConclusion,
    *,
    status: str,
    missing_data_notes: Sequence[str],
) -> tuple[RiskDecision, Dict[str, str]]:
    viewpoints = _render_risk_viewpoints(
        proposal,
        conclusion,
        status=status,
        missing_data_notes=missing_data_notes,
    )
    degraded = conclusion.recommendation is ResearchRecommendation.INSUFFICIENT_DATA
    if degraded or proposal.candidate_action is TraderCandidateAction.AVOID:
        verdict = RiskVerdict.REJECT_PROPOSAL
        risk_level = RiskLevel.HIGH
    elif status != "ok" or missing_data_notes:
        verdict = RiskVerdict.NEEDS_MORE_DATA
        risk_level = RiskLevel.MEDIUM
    else:
        verdict = RiskVerdict.ALLOW_ADVISORY
        risk_level = RiskLevel.LOW if proposal.confidence >= 0.65 else RiskLevel.MEDIUM

    constraints = [
        "ResearchOnly stop condition remains mandatory.",
        "No signal processing, memory write, or QMT call is allowed.",
    ]
    if proposal.position_cap_pct is not None:
        constraints.append(f"Advisory exposure cap: {proposal.position_cap_pct:.1f}%.")
    if status != "ok":
        constraints.append("Provider gaps require a fresh research pass before any stronger advisory stance.")

    risk_factors = [
        factor
        for factor in (
            conclusion.bear_case,
            "provider coverage incomplete" if missing_data_notes else "",
            "advisory-only runtime cannot validate executable timing",
        )
        if factor
    ]

    decision = RiskDecision(
        proposal_id=proposal.proposal_id,
        verdict=verdict,
        risk_level=risk_level,
        risk_factors=risk_factors,
        constraints=constraints,
        missing_evidence=list(missing_data_notes),
    )
    return decision, viewpoints


def _build_portfolio_decision(
    proposal: TraderProposal,
    risk_decision: RiskDecision,
    conclusion: ResearchConclusion,
) -> PortfolioDecision:
    if risk_decision.verdict is RiskVerdict.REJECT_PROPOSAL:
        disposition = PortfolioDisposition.ADVISORY_REJECTED
        exposure_cap_pct = 0.0
    elif risk_decision.verdict is RiskVerdict.NEEDS_MORE_DATA:
        disposition = PortfolioDisposition.CONTINUE_RESEARCH
        exposure_cap_pct = min(proposal.position_cap_pct or 5.0, 5.0)
    else:
        disposition = PortfolioDisposition.WATCHLIST
        exposure_cap_pct = proposal.position_cap_pct

    review_triggers = list(risk_decision.missing_evidence)
    review_triggers.extend(
        [
            "Material change in five-layer provider coverage.",
            "Research Manager recommendation changes on the next run.",
        ]
    )
    portfolio_notes = (
        f"Portfolio advisory derived from {proposal.candidate_action.value} with "
        f"risk verdict {risk_decision.verdict.value}. Summary: {conclusion.summary}"
    )

    return PortfolioDecision(
        proposal_id=proposal.proposal_id,
        risk_decision_id=_make_advisory_id("rd", conclusion.symbol, conclusion.trade_date),
        disposition=disposition,
        portfolio_notes=portfolio_notes,
        exposure_cap_pct=exposure_cap_pct,
        review_triggers=review_triggers,
    )


# ---------------------------------------------------------------------------
# AStockGraphReport — the stable output contract
# ---------------------------------------------------------------------------

@dataclass
class AStockGraphReport:
    """Stable report object returned by :class:`AStockGraphRuntime`.

    The object is intentionally UI-friendly and serializable. It carries the
    structured upper-layer result plus a compatibility adapter that can be
    flattened into the legacy TradingAgents state shape when needed.
    """

    symbol: str
    normalized_symbol: str
    trade_date: Optional[str]
    source: Optional[str]
    sections_requested: Sequence[str]
    astock_analysis: Dict[str, Any]
    astock_sections: Dict[str, Any]
    bull_output: Dict[str, Any]
    bear_output: Dict[str, Any]
    research_manager_output: Dict[str, Any]
    investment_plan: str
    runtime_trace: Sequence[str]
    llm_prompts: Dict[str, list[str]]
    summary: str
    section_results: Dict[str, Any] = field(default_factory=dict)
    bull_view: str = ""
    bear_view: str = ""
    research_manager_conclusion: str = ""
    provider_coverage: Dict[str, Any] = field(default_factory=dict)
    missing_data_notes: list[str] = field(default_factory=list)
    degradation_notes: list[str] = field(default_factory=list)
    mode: str = "astock_research_bridge"
    status: str = "ok"
    decision_scope: str = "research_only"
    actionable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Phase 09 advisory-only fields (all optional so existing consumers stay
    # unaffected when they are None).
    runtime_profile: Optional[str] = field(default=None)
    research_conclusion: Optional[Dict[str, Any]] = field(default=None)
    trader_proposal: Optional[Dict[str, Any]] = field(default=None)
    risk_decision: Optional[Dict[str, Any]] = field(default=None)
    portfolio_decision: Optional[Dict[str, Any]] = field(default=None)

    @property
    def ticker(self) -> str:
        return self.symbol

    @property
    def runtime_mode(self) -> str:
        return self.mode

    @property
    def analyst_summary(self) -> str:
        return self.summary

    @property
    def final_trade_decision(self) -> str:
        return self.investment_plan or self.research_manager_output.get("investment_plan") or self.summary

    @property
    def execution_signal(self) -> str:
        return _RESEARCH_ONLY_SIGNAL

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "mode": self.mode,
            "status": self.status,
            "decision_scope": self.decision_scope,
            "actionable": self.actionable,
            "execution_signal": self.execution_signal,
            "symbol": self.symbol,
            "normalized_symbol": self.normalized_symbol,
            "trade_date": self.trade_date,
            "source": self.source,
            "sections_requested": list(self.sections_requested),
            "summary": self.summary,
            "analyst_summary": self.summary,
            "ticker": self.symbol,
            "runtime_mode": self.mode,
            "section_results": copy.deepcopy(self.section_results),
            "bull_view": self.bull_view,
            "bear_view": self.bear_view,
            "research_manager_conclusion": self.research_manager_conclusion,
            "provider_coverage": copy.deepcopy(self.provider_coverage),
            "missing_data_notes": list(self.missing_data_notes),
            "degradation_notes": list(self.degradation_notes),
            "astock_analysis": copy.deepcopy(self.astock_analysis),
            "astock_sections": copy.deepcopy(self.astock_sections),
            "bull_output": copy.deepcopy(self.bull_output),
            "bear_output": copy.deepcopy(self.bear_output),
            "research_manager_output": copy.deepcopy(self.research_manager_output),
            "investment_plan": self.investment_plan,
            "final_trade_decision": self.final_trade_decision,
            "runtime_trace": list(self.runtime_trace),
            "llm_prompts": copy.deepcopy(self.llm_prompts),
            "metadata": copy.deepcopy(self.metadata),
        }
        if self.runtime_profile is not None:
            result["runtime_profile"] = self.runtime_profile
        if self.research_conclusion is not None:
            result["research_conclusion"] = copy.deepcopy(self.research_conclusion)
        if self.trader_proposal is not None:
            result["trader_proposal"] = copy.deepcopy(self.trader_proposal)
        if self.risk_decision is not None:
            result["risk_decision"] = copy.deepcopy(self.risk_decision)
        if self.portfolio_decision is not None:
            result["portfolio_decision"] = copy.deepcopy(self.portfolio_decision)
        return result

    def to_legacy_state(self, include_runtime_report: bool = True) -> Dict[str, Any]:
        market_section = self.astock_sections.get("market", {}) if isinstance(self.astock_sections, Mapping) else {}
        news_section = self.astock_sections.get("news", {}) if isinstance(self.astock_sections, Mapping) else {}
        fundamentals_section = (
            self.astock_sections.get("fundamentals", {}) if isinstance(self.astock_sections, Mapping) else {}
        )
        debate_state = {
            "history": self._combine_history(),
            "bull_history": self._extract_bull_history(),
            "bear_history": self._extract_bear_history(),
            "current_response": self._extract_current_response(),
            "count": 2,
            "judge_decision": self.final_trade_decision,
        }
        empty_risk_state = {
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "history": "",
            "judge_decision": "",
        }
        if isinstance(self.metadata.get("phase09_viewpoints"), Mapping):
            viewpoints = self.metadata["phase09_viewpoints"]
            empty_risk_state = {
                "aggressive_history": str(viewpoints.get("aggressive", "")),
                "conservative_history": str(viewpoints.get("conservative", "")),
                "neutral_history": str(viewpoints.get("neutral", "")),
                "history": "\n".join(
                    fragment
                    for fragment in (
                        viewpoints.get("aggressive", ""),
                        viewpoints.get("conservative", ""),
                        viewpoints.get("neutral", ""),
                    )
                    if fragment
                ),
                "judge_decision": (
                    (self.portfolio_decision or {}).get("portfolio_notes", "")
                    if isinstance(self.portfolio_decision, Mapping)
                    else ""
                ),
            }
        return {
            "company_of_interest": self.symbol,
            "trade_date": self.trade_date,
            "curr_date": self.trade_date,
            "asset_type": "stock",
            "mode": self.mode,
            "status": self.status,
            "decision_scope": self.decision_scope,
            "actionable": self.actionable,
            "execution_signal": self.execution_signal,
            "market_report": _section_text(market_section, self.summary),
            "sentiment_report": _section_text(news_section, self.summary),
            "news_report": _section_text(news_section, self.summary),
            "fundamentals_report": _section_text(fundamentals_section, self.summary),
            "investment_debate_state": debate_state,
            "trader_investment_plan": (
                (self.trader_proposal or {}).get("rationale", "")
                if isinstance(self.trader_proposal, Mapping)
                else ""
            ),
            "risk_debate_state": empty_risk_state,
            "investment_plan": self.investment_plan,
            "final_trade_decision": self.final_trade_decision,
            "astock_analysis": copy.deepcopy(self.astock_analysis),
            "astock_sections": copy.deepcopy(self.astock_sections),
            "astock_summary": self.summary,
            "astock_display_report": self.to_dict() if include_runtime_report else None,
            "astock_runtime_report": self.to_dict() if include_runtime_report else None,
            "phase09_advisory": {
                "runtime_profile": self.runtime_profile,
                "decision_scope": self.decision_scope,
                "actionable": self.actionable,
                "execution_signal": self.execution_signal,
                "research_conclusion": copy.deepcopy(self.research_conclusion),
                "trader_proposal": copy.deepcopy(self.trader_proposal),
                "risk_decision": copy.deepcopy(self.risk_decision),
                "portfolio_decision": copy.deepcopy(self.portfolio_decision),
            },
        }

    def _extract_bull_history(self) -> str:
        return _extract_debate_text(self.bull_output, "bull_history")

    def _extract_bear_history(self) -> str:
        return _extract_debate_text(self.bear_output, "bear_history")

    def _extract_current_response(self) -> str:
        return _extract_debate_text(self.research_manager_output, "current_response") or self.final_trade_decision

    def _combine_history(self) -> str:
        fragments = [fragment for fragment in [self._extract_bull_history(), self._extract_bear_history()] if fragment]
        return "\n".join(fragments)

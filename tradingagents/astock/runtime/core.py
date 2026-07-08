"""Core runtime orchestration for the A-share research bridge.

Contains ``AStockGraphRuntime`` (the main execution class),
``build_astock_research_bridge_state`` (state builder), and the
``run_astock_research_bridge`` convenience wrapper.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

from ..analyst import AStockAnalyst
from ..data_sources import normalize_astock_symbol
from ..interface import AStockInterface
from ..phase9_schemas import (
    PortfolioDecision,
    ResearchConclusion,
    ResearchRecommendation,
    RiskDecision,
    RiskLevel,
    RiskVerdict,
    TraderCandidateAction,
    TraderProposal,
    degraded_research_conclusion,
)
from .llm_factory import BridgeLLM
from .report import (
    AStockGraphReport,
    _build_degradation_notes,
    _build_missing_data_notes,
    _build_portfolio_decision,
    _build_provider_coverage,
    _build_risk_decision,
    _build_section_results,
    _build_trader_proposal,
    _build_view_text,
    _derive_research_recommendation,
    _is_data_present,
    _section_text,
)
from ..runtime_profile import (
    RuntimeProfile,
    profile_metadata,
    require_live_research_clients,
    resolve_profile,
)

_DEFAULT_SECTIONS: tuple[str, ...] = (
    "market",
    "news",
    "fundamentals",
    "announcements",
    "research",
)


# ---------------------------------------------------------------------------
# State builder
# ---------------------------------------------------------------------------

def build_astock_research_bridge_state(
    symbol: str,
    *,
    interface: Optional[AStockInterface] = None,
    base_state: Optional[Mapping[str, Any]] = None,
    trade_date: Optional[str] = None,
    source: Optional[str] = None,
    sections: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Create the structured state consumed by the A-share research chain."""

    analyst = AStockAnalyst(
        interface=interface or AStockInterface(),
        sections=tuple(sections) if sections is not None else _DEFAULT_SECTIONS,
    )
    initial_state: Dict[str, Any] = dict(base_state or {})
    initial_state.setdefault("company_of_interest", symbol)
    initial_state.setdefault("asset_type", "stock")
    initial_state.setdefault(
        "instrument_context",
        f"The stock to analyze is `{symbol}`. Use this exact ticker in every tool call, report, and recommendation.",
    )
    if trade_date is not None:
        initial_state["trade_date"] = trade_date
        initial_state.setdefault("curr_date", trade_date)

    if source is not None:
        initial_state.setdefault("astock_source", source)

    astock_bridge = analyst.analyze_state(initial_state)
    analysis = astock_bridge.get("astock_analysis", {})
    sections_payload = astock_bridge.get("astock_sections", {})
    market_section = sections_payload.get("market", {}) if isinstance(sections_payload, Mapping) else {}
    news_section = sections_payload.get("news", {}) if isinstance(sections_payload, Mapping) else {}
    fundamentals_section = (
        sections_payload.get("fundamentals", {}) if isinstance(sections_payload, Mapping) else {}
    )

    initial_state.update(astock_bridge)
    initial_state.setdefault("market_report", _section_text(market_section, "market section unavailable"))
    initial_state.setdefault("sentiment_report", _section_text(news_section, "news section unavailable"))
    initial_state.setdefault("news_report", _section_text(news_section, "news section unavailable"))
    initial_state.setdefault(
        "fundamentals_report",
        _section_text(fundamentals_section, "fundamentals section unavailable"),
    )
    initial_state.setdefault(
        "investment_debate_state",
        {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "count": 0,
        },
    )
    initial_state.setdefault("astock_analysis", analysis)
    return initial_state


# ---------------------------------------------------------------------------
# Main runtime class
# ---------------------------------------------------------------------------

@dataclass
class AStockGraphRuntime:
    """Formal research-only runtime entry for the minimal A-share bridge.

    Phase 09 adds ``runtime_profile`` support.  When the profile is
    ``LIVE_RESEARCH``, real LLM clients are required and BridgeLLM fallback
    is forbidden.
    """

    symbol: str
    interface: Optional[AStockInterface] = None
    base_state: Optional[Mapping[str, Any]] = None
    trade_date: Optional[str] = None
    source: Optional[str] = None
    bull_llm: Optional[Any] = None
    bear_llm: Optional[Any] = None
    research_manager_llm: Optional[Any] = None
    sections: Sequence[str] = field(default_factory=lambda: _DEFAULT_SECTIONS)
    mode: str = "astock_research_bridge"
    runtime_profile: Optional[str] = field(default=None)

    def describe(self) -> Dict[str, Any]:
        """Describe the runtime entrypoint, state flow, and output contract."""

        profile = resolve_profile(
            RuntimeProfile(self.runtime_profile) if self.runtime_profile else None,
            has_bridge_llm=self.bull_llm is None,
            has_real_llm=self.bull_llm is not None,
        )

        return {
            "mode": self.mode,
            "runtime_profile": profile.value,
            "decision_scope": "research_only",
            "actionable": False,
            "entrypoint": "AStockGraphRuntime.run",
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "source": self.source,
            "sections": list(self.sections),
            "state_flow": [
                "AStockAnalyst",
                "Bull Researcher",
                "Bear Researcher",
                "Research Manager",
            ],
            "phase09_state_flow": [
                "ResearchConclusion",
                "TraderProposal (advisory-only)",
                "RiskDecision (three-viewpoint synthesis)",
                "PortfolioDecision (ResearchOnly stop)",
            ],
            "output_fields": [
                "AStockGraphReport",
                "ticker",
                "runtime_mode",
                "runtime_profile",
                "section_results",
                "analyst_summary",
                "bull_view",
                "bear_view",
                "research_manager_conclusion",
                "provider_coverage",
                "missing_data_notes",
                "degradation_notes",
                "astock_analysis",
                "astock_sections",
                "bull_output",
                "bear_output",
                "research_manager_output",
                "investment_plan",
                "research_conclusion",
                "trader_proposal",
                "risk_decision",
                "portfolio_decision",
                "runtime_trace",
            ],
            "fallback_behavior": [
                "missing ASTOCK_IWENCAI_COOKIE degrades to structured empty/partial output",
                "missing provider degrades to structured empty/partial output",
                "empty section data does not stop the graph",
                "research output never becomes an execution signal",
                "live_research fails closed when real LLM clients are missing (no BridgeLLM fallback)",
            ],
            "phase09_stop_condition": "Chain stops after PortfolioDecision; no signal processing, no QMT, no trade-decision memory.",
        }

    def build_state(self) -> Dict[str, Any]:
        """Build the A-share bridge state used by the runtime."""

        return build_astock_research_bridge_state(
            self.symbol,
            interface=self.interface,
            base_state=self.base_state,
            trade_date=self.trade_date,
            source=self.source,
            sections=self.sections,
        )

    def run(self) -> AStockGraphReport:
        """Execute the minimal A-share research bridge with shared logic.

        Phase 09 addition: resolves the active runtime profile, enforces
        live_research client requirements, and populates advisory-only Phase 09
        contracts on the report.
        """

        # Resolve runtime profile
        active_profile = resolve_profile(
            RuntimeProfile(self.runtime_profile) if self.runtime_profile else None,
            has_bridge_llm=self.bull_llm is None
            and self.bear_llm is None
            and self.research_manager_llm is None,
            has_real_llm=self.bull_llm is not None
            or self.bear_llm is not None
            or self.research_manager_llm is not None,
        )

        # live_research: fail closed when real clients are missing
        require_live_research_clients(
            profile=active_profile,
            bull_llm=self.bull_llm,
            bear_llm=self.bear_llm,
            research_manager_llm=self.research_manager_llm,
        )

        state = self.build_state()
        trace = ["AStock Analyst"]

        bull_llm = self.bull_llm or BridgeLLM(
            "Bull Researcher",
            response_content="Bull bridge output from the deterministic runtime helper.",
        )
        bear_llm = self.bear_llm or BridgeLLM(
            "Bear Researcher",
            response_content="Bear bridge output from the deterministic runtime helper.",
        )
        research_manager_llm = self.research_manager_llm or BridgeLLM(
            "Research Manager",
            rationale="The A-share sections were bridged successfully into the research manager.",
            strategic_actions="Use the bridged A-share sections as the next input to trader/risk layers.",
        )

        bull_node = create_bull_researcher(bull_llm)
        bear_node = create_bear_researcher(bear_llm)
        research_manager_node = create_research_manager(research_manager_llm)

        bull_output = bull_node(state)
        trace.append("Bull Researcher")
        state.update(bull_output)

        bear_output = bear_node(state)
        trace.append("Bear Researcher")
        state.update(bear_output)

        research_manager_output = research_manager_node(state)
        trace.append("Research Manager")
        state.update(research_manager_output)

        normalized_symbol = state.get("company_of_interest") or self.symbol
        analysis = state.get("astock_analysis", {})
        sections_payload = state.get("astock_sections", {})
        section_results = _build_section_results(sections_payload, self.sections)
        summary = state.get("astock_summary") or analysis.get("summary") or "A-share bridge completed"
        missing_sections = []
        if isinstance(analysis, Mapping):
            missing_sections = list(analysis.get("missing_sections", []) or [])
        if not missing_sections:
            missing_sections = [name for name, item in section_results.items() if item.get("status") not in {"ok", "available"}]
        status = "ok" if not missing_sections else ("partial" if len(missing_sections) < len(self.sections) else "degraded")
        provider_coverage = _build_provider_coverage(section_results)
        missing_data_notes = _build_missing_data_notes(section_results)
        degradation_notes = _build_degradation_notes(section_results, missing_sections)
        bull_view = _build_view_text(
            bull_output,
            preferred_keys=("summary", "current_response", "bull_history", "content"),
            fallback="Bull view unavailable",
        )
        bear_view = _build_view_text(
            bear_output,
            preferred_keys=("summary", "current_response", "bear_history", "content"),
            fallback="Bear view unavailable",
        )
        research_manager_conclusion = _build_view_text(
            research_manager_output,
            preferred_keys=("investment_plan", "current_response", "judge_decision", "content"),
            fallback="Research manager conclusion unavailable",
        )

        report = AStockGraphReport(
            symbol=self.symbol,
            normalized_symbol=str(normalized_symbol),
            trade_date=self.trade_date,
            source=self.source,
            sections_requested=tuple(self.sections),
            astock_analysis=copy.deepcopy(dict(analysis) if isinstance(analysis, Mapping) else {}),
            section_results=copy.deepcopy(section_results),
            bull_view=bull_view,
            bear_view=bear_view,
            research_manager_conclusion=research_manager_conclusion,
            provider_coverage=copy.deepcopy(provider_coverage),
            missing_data_notes=list(missing_data_notes),
            degradation_notes=list(degradation_notes),
            astock_sections=copy.deepcopy(sections_payload),
            bull_output=copy.deepcopy(bull_output),
            bear_output=copy.deepcopy(bear_output),
            research_manager_output=copy.deepcopy(research_manager_output),
            investment_plan=research_manager_output.get("investment_plan") or "",
            runtime_trace=tuple(trace),
            llm_prompts={
                "bull": list(getattr(bull_llm, "prompts", [])),
                "bear": list(getattr(bear_llm, "prompts", [])),
                "research_manager": list(getattr(research_manager_llm, "prompts", [])),
            },
            summary=str(summary),
            mode=self.mode,
            status=status,
            metadata={
                "state_keys": sorted(state.keys()),
                "bridge_mode": self.mode,
                "missing_sections": missing_sections,
                **profile_metadata(active_profile),
            },
            runtime_profile=active_profile.value,
        )

        # Phase 09: populate ResearchConclusion from research output
        recommendation = research_manager_conclusion or summary
        research_conclusion = degraded_research_conclusion(
            symbol=str(normalized_symbol),
            trade_date=self.trade_date or "",
            reason="missing provider data",
        )
        # Override with populated data when research output is available
        if recommendation and "insufficient" not in recommendation.lower():
            research_conclusion = ResearchConclusion(
                symbol=str(normalized_symbol),
                trade_date=self.trade_date or "",
                summary=recommendation,
                recommendation=_derive_research_recommendation(recommendation),
                bull_case=bull_view,
                bear_case=bear_view,
                uncertainties=list(missing_data_notes),
                provider_coverage=copy.deepcopy(provider_coverage),
                confidence=0.65 if status == "ok" else 0.45,
            )
        report.research_conclusion = research_conclusion.model_dump()

        trader_proposal = _build_trader_proposal(
            research_conclusion,
            status=status,
            missing_data_notes=missing_data_notes,
        )
        report.trader_proposal = trader_proposal.model_dump()
        trace.append("Trader")

        risk_decision, risk_viewpoints = _build_risk_decision(
            trader_proposal,
            research_conclusion,
            status=status,
            missing_data_notes=missing_data_notes,
        )
        report.risk_decision = risk_decision.model_dump()
        trace.extend(["Aggressive Risk Analyst", "Conservative Risk Analyst", "Neutral Risk Analyst"])

        portfolio_decision = _build_portfolio_decision(
            trader_proposal,
            risk_decision,
            research_conclusion,
        )
        report.portfolio_decision = portfolio_decision.model_dump()
        trace.append("Portfolio Manager")
        report.runtime_trace = tuple(trace)
        report.metadata["phase09_viewpoints"] = risk_viewpoints
        report.metadata["phase09_chain_completed"] = True
        return report


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def run_astock_research_bridge(
    symbol: str,
    *,
    interface: Optional[AStockInterface] = None,
    base_state: Optional[Mapping[str, Any]] = None,
    trade_date: Optional[str] = None,
    source: Optional[str] = None,
    sections: Optional[Sequence[str]] = None,
    bull_llm: Optional[Any] = None,
    bear_llm: Optional[Any] = None,
    research_manager_llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """Backward-compatible wrapper over :class:`AStockGraphRuntime`."""

    runtime = AStockGraphRuntime(
        symbol=symbol,
        interface=interface,
        base_state=base_state,
        trade_date=trade_date,
        source=source,
        sections=tuple(sections) if sections is not None else _DEFAULT_SECTIONS,
        bull_llm=bull_llm,
        bear_llm=bear_llm,
        research_manager_llm=research_manager_llm,
    )
    report = runtime.run()
    return {**report.to_dict(), "state": report.to_legacy_state(include_runtime_report=False)}

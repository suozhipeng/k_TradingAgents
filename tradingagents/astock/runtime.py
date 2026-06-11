"""Formal A-share graph runtime entry.

This module owns the shared bridge logic used by both test runs and production
runs for the minimal A-share research path. The bridge remains intentionally
small and read-only:

`AStockAnalyst -> Bull Researcher -> Bear Researcher -> Research Manager`

The same state builder and runtime execution path are used in every caller so
there is no separate test-only helper and no divergent wiring path.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Optional, Sequence

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.schemas import ResearchPlan

from .analyst import AStockAnalyst
from .interface import AStockInterface
from .data_sources import normalize_astock_symbol

_DEFAULT_SECTIONS: tuple[str, ...] = (
    "market",
    "news",
    "fundamentals",
    "announcements",
    "research",
)
_ASTOCK_EXACT = re.compile(r"^\d{6}$")
_ASTOCK_SUFFIXES = (".SH", ".SZ", ".BJ")


def is_astock_symbol(raw: str) -> bool:
    """Return True when the symbol is a mainland A-share ticker."""

    normalized = normalize_astock_symbol(raw)
    return bool(_ASTOCK_EXACT.fullmatch(normalized) or normalized.endswith(_ASTOCK_SUFFIXES))


@dataclass
class BridgeLLM:
    """Tiny deterministic LLM stub used by the runtime bridge verification path."""

    label: str
    response_content: str = ""
    rationale: str = ""
    strategic_actions: str = ""
    prompts: list[str] = field(default_factory=list)
    _structured_schema: type[ResearchPlan] | None = field(default=None, init=False)

    def with_structured_output(self, schema):
        self._structured_schema = schema
        return self

    def invoke(self, prompt: Any):
        self.prompts.append(str(prompt))
        if self._structured_schema is not None:
            return self._structured_schema(
                recommendation="Hold",
                rationale=self.rationale
                or f"{self.label} completed the A-share bridge with the structured analysis handoff.",
                strategic_actions=self.strategic_actions
                or "Keep monitoring the bridged A-share sections and revisit the debate on the next run.",
            )
        return SimpleNamespace(
            content=self.response_content
            or f"{self.label}: processed the bridged A-share context successfully.",
        )


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
    metadata: Dict[str, Any] = field(default_factory=dict)

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "status": self.status,
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
        return {
            "company_of_interest": self.symbol,
            "trade_date": self.trade_date,
            "curr_date": self.trade_date,
            "asset_type": "stock",
            "mode": self.mode,
            "status": self.status,
            "market_report": _section_text(market_section, self.summary),
            "sentiment_report": _section_text(news_section, self.summary),
            "news_report": _section_text(news_section, self.summary),
            "fundamentals_report": _section_text(fundamentals_section, self.summary),
            "investment_debate_state": debate_state,
            "trader_investment_plan": "",
            "risk_debate_state": empty_risk_state,
            "investment_plan": self.investment_plan,
            "final_trade_decision": self.final_trade_decision,
            "astock_analysis": copy.deepcopy(self.astock_analysis),
            "astock_sections": copy.deepcopy(self.astock_sections),
            "astock_summary": self.summary,
            "astock_display_report": self.to_dict() if include_runtime_report else None,
            "astock_runtime_report": self.to_dict() if include_runtime_report else None,
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



def _build_section_results(sections_payload: Mapping[str, Any], requested_sections: Sequence[str]) -> Dict[str, Dict[str, Any]]:
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



def _build_degradation_notes(section_results: Mapping[str, Any], missing_sections: Sequence[str]) -> list[str]:
    notes: list[str] = []
    for section_name in missing_sections:
        result = section_results.get(section_name, {})
        status = result.get("status", "unknown")
        summary = result.get("summary") or f"{section_name} degraded"
        notes.append(f"{section_name} [{status}]: {summary}")
    return notes



def _build_view_text(payload: Mapping[str, Any], *, preferred_keys: Sequence[str], fallback: str) -> str:
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


@dataclass
class AStockGraphRuntime:
    """Formal runtime entry for the minimal A-share research bridge."""

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

    def describe(self) -> Dict[str, Any]:
        """Describe the runtime entrypoint, state flow, and output contract."""

        return {
            "mode": self.mode,
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
            "output_fields": [
                "AStockGraphReport",
                "ticker",
                "runtime_mode",
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
                "runtime_trace",
            ],
            "fallback_behavior": [
                "missing ASTOCK_IWENCAI_COOKIE degrades to structured empty/partial output",
                "missing provider degrades to structured empty/partial output",
                "empty section data does not stop the graph",
            ],
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
        """Execute the minimal A-share research bridge with shared logic."""

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
            astock_analysis=copy.deepcopy(analysis),
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
            },
        )
        return report



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


__all__ = [
    "AStockGraphReport",
    "AStockGraphRuntime",
    "BridgeLLM",
    "build_astock_research_bridge_state",
    "is_astock_symbol",
    "run_astock_research_bridge",
]

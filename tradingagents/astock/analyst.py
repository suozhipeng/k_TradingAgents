"""Minimal A-share analyst entrypoint.

This is intentionally small: it collects market/news/fundamentals through the
stable interface and returns a structured payload that can later be plugged
into LangGraph without changing provider code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence

from .interface import AStockInterface


_DEFAULT_SECTIONS: Sequence[str] = ("market", "news", "fundamentals", "announcements", "research")


@dataclass
class AStockAnalyst:
    """Small deterministic A-share analyst for the initial upper-layer bridge."""

    interface: AStockInterface = field(default_factory=AStockInterface)
    sections: Sequence[str] = _DEFAULT_SECTIONS

    def analyze(
        self,
        symbol: str,
        *,
        trade_date: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        look_back_days: Optional[int] = None,
        freq: Optional[str] = None,
        announcement_query: Optional[str] = None,
        announcement_title: Optional[str] = None,
        research_query: Optional[str] = None,
        research_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self.interface.to_payload(
            symbol,
            sections=self.sections,
            source=source,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            limit=limit,
            look_back_days=look_back_days,
            curr_date=trade_date,
            freq=freq,
            announcement_query=announcement_query,
            announcement_title=announcement_title,
            research_query=research_query,
            research_title=research_title,
        )
        payload["trade_date"] = trade_date
        payload["status_breakdown"] = {
            name: section["status"]
            for name, section in payload.get("sections", {}).items()
            if isinstance(section, dict)
        }
        payload["missing_sections"] = [name for name, status in payload["status_breakdown"].items() if status != "ok"]
        return payload

    def analyze_state(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """LangGraph-friendly state adapter.

        Expected state keys are intentionally small and stable:
        - company_of_interest / symbol / ticker
        - trade_date / curr_date
        - astock_source (optional)
        """

        symbol = (
            state.get("company_of_interest")
            or state.get("symbol")
            or state.get("ticker")
            or state.get("raw_symbol")
        )
        if not symbol:
            raise ValueError("A-stock analyst requires a symbol/company_of_interest/ticker field")
        trade_date = state.get("trade_date") or state.get("curr_date")
        payload = self.analyze(
            str(symbol),
            trade_date=trade_date,
            source=state.get("astock_source"),
            start_date=state.get("start_date"),
            end_date=state.get("end_date"),
            interval=state.get("interval"),
            limit=state.get("limit"),
            look_back_days=state.get("look_back_days"),
            freq=state.get("freq"),
        )
        return {
            "astock_analysis": payload,
            "astock_sections": payload.get("sections", {}),
            "astock_summary": payload.get("summary"),
        }



def create_astock_analyst(interface: Optional[AStockInterface] = None) -> AStockAnalyst:
    return AStockAnalyst(interface=interface or AStockInterface())


def create_astock_analyst_node(interface: Optional[AStockInterface] = None):
    analyst = create_astock_analyst(interface=interface)

    def _node(state: Mapping[str, Any]) -> Dict[str, Any]:
        return analyst.analyze_state(state)

    return _node


__all__ = ["AStockAnalyst", "create_astock_analyst", "create_astock_analyst_node"]

"""Stable A-share interface for upper-layer consumers.

This module is the single import surface that higher layers should depend on.
It wraps the provider router/facade, keeps symbol normalization here, and
returns structured bundles that are easy to pipe into LangGraph later.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .data_sources import AStockDataFacade, AStockResponse, normalize_astock_symbol


_SECTION_OK = "ok"
_SECTION_PARTIAL = "partial"
_SECTION_EMPTY = "empty"
_SECTION_ERROR = "error"


@dataclass(frozen=True)
class AStockSectionBundle:
    """Structured section output returned by the stable interface."""

    section: str
    symbol: str
    raw_symbol: str
    status: str
    responses: Dict[str, Dict[str, Any]]
    capabilities: Tuple[str, ...]
    summary: str
    primary_source: Optional[str] = None
    missing: Tuple[str, ...] = field(default_factory=tuple)
    notes: Tuple[str, ...] = field(default_factory=tuple)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section": self.section,
            "symbol": self.symbol,
            "raw_symbol": self.raw_symbol,
            "status": self.status,
            "responses": copy.deepcopy(self.responses),
            "capabilities": list(self.capabilities),
            "summary": self.summary,
            "primary_source": self.primary_source,
            "missing": list(self.missing),
            "notes": list(self.notes),
            "meta": copy.deepcopy(self.meta),
        }


@dataclass
class AStockInterface:
    """Provider-agnostic stable interface for A-share upper layers."""

    facade: AStockDataFacade = field(default_factory=AStockDataFacade)
    default_market_interval: str = "1d"
    default_news_limit: int = 8
    default_global_news_lookback_days: int = 7
    default_fundamentals_freq: str = "quarterly"

    def normalize_symbol(self, symbol: str) -> str:
        return normalize_astock_symbol(symbol)

    def _response_bundle(
        self,
        section: str,
        symbol: str,
        raw_symbol: str,
        responses: Mapping[str, AStockResponse],
        *,
        notes: Sequence[str] = (),
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> AStockSectionBundle:
        normalized_responses: Dict[str, Dict[str, Any]] = {
            name: response.to_dict() for name, response in responses.items()
        }
        response_values = list(responses.values())
        ok_count = sum(1 for response in response_values if response.status == _SECTION_OK and not response.empty)
        empty_count = sum(1 for response in response_values if response.status == _SECTION_EMPTY or response.empty)
        error_count = sum(1 for response in response_values if response.status == _SECTION_ERROR)

        if ok_count == len(response_values) and response_values:
            status = _SECTION_OK
        elif ok_count > 0:
            status = _SECTION_PARTIAL
        elif empty_count == len(response_values) and response_values:
            status = _SECTION_EMPTY
        elif error_count > 0:
            status = _SECTION_ERROR
        else:
            status = _SECTION_PARTIAL if response_values else _SECTION_EMPTY

        capabilities = tuple(responses.keys())
        missing = tuple(name for name, response in responses.items() if response.empty or response.status != _SECTION_OK)
        primary_source = next((response.source for response in response_values if response.status == _SECTION_OK and response.source), None)
        summary_parts: List[str] = []
        for name, response in responses.items():
            state = response.status
            if response.empty:
                state = _SECTION_EMPTY
            summary_parts.append(f"{name}={state}{f'[{response.source}]' if response.source else ''}")
        summary = "; ".join(summary_parts)
        meta = {
            "section": section,
            "response_count": len(responses),
        }
        if extra_meta:
            meta.update(copy.deepcopy(extra_meta))
        if notes:
            meta["notes"] = list(notes)
        return AStockSectionBundle(
            section=section,
            symbol=symbol,
            raw_symbol=raw_symbol,
            status=status,
            responses=normalized_responses,
            capabilities=capabilities,
            summary=summary,
            primary_source=primary_source,
            missing=missing,
            notes=tuple(notes),
            meta=meta,
        )

    def market_snapshot(
        self,
        symbol: str,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AStockSectionBundle:
        raw_symbol = symbol
        normalized = self.normalize_symbol(symbol)
        effective_interval = interval or self.default_market_interval
        responses = {
            "kline": self.facade.get_kline(
                normalized,
                start_date=start_date,
                end_date=end_date,
                interval=effective_interval,
                source=source,
            ),
            "valuation": self.facade.get_valuation(normalized, source=source),
        }
        return self._response_bundle(
            "market",
            normalized,
            raw_symbol,
            responses,
            extra_meta={
                "start_date": start_date,
                "end_date": end_date,
                "interval": effective_interval,
                "source_hint": source,
            },
        )

    def news_snapshot(
        self,
        symbol: str,
        *,
        limit: Optional[int] = None,
        look_back_days: Optional[int] = None,
        curr_date: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AStockSectionBundle:
        raw_symbol = symbol
        normalized = self.normalize_symbol(symbol)
        responses = {
            "stock_news": self.facade.get_stock_news(normalized, source=source, limit=limit),
            "flash_news": self.facade.get_flash_news(normalized, source=source, limit=limit),
            "global_news": self.facade.get_global_news(
                normalized,
                source=source,
                limit=limit,
                look_back_days=look_back_days or self.default_global_news_lookback_days,
                curr_date=curr_date,
            ),
        }
        return self._response_bundle(
            "news",
            normalized,
            raw_symbol,
            responses,
            extra_meta={
                "limit": limit or self.default_news_limit,
                "look_back_days": look_back_days or self.default_global_news_lookback_days,
                "curr_date": curr_date,
                "source_hint": source,
            },
        )

    def fundamentals_snapshot(
        self,
        symbol: str,
        *,
        curr_date: Optional[str] = None,
        freq: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AStockSectionBundle:
        raw_symbol = symbol
        normalized = self.normalize_symbol(symbol)
        effective_freq = freq or self.default_fundamentals_freq
        responses = {
            "fundamentals": self.facade.get_fundamentals(normalized, source=source, curr_date=curr_date, freq=effective_freq),
            "quarterly_financials": self.facade.get_quarterly_financials(normalized, source=source, freq=effective_freq),
            "f10": self.facade.get_f10(normalized, source=source),
        }
        return self._response_bundle(
            "fundamentals",
            normalized,
            raw_symbol,
            responses,
            extra_meta={
                "curr_date": curr_date,
                "freq": effective_freq,
                "source_hint": source,
            },
        )

    def collect(
        self,
        symbol: str,
        *,
        sections: Sequence[str] = ("market", "news", "fundamentals"),
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        look_back_days: Optional[int] = None,
        curr_date: Optional[str] = None,
        freq: Optional[str] = None,
    ) -> Dict[str, AStockSectionBundle]:
        collected: Dict[str, AStockSectionBundle] = {}
        for section in sections:
            normalized_section = str(section).strip().lower()
            if normalized_section == "market":
                collected[normalized_section] = self.market_snapshot(
                    symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    source=source,
                )
            elif normalized_section == "news":
                collected[normalized_section] = self.news_snapshot(
                    symbol,
                    limit=limit,
                    look_back_days=look_back_days,
                    curr_date=curr_date,
                    source=source,
                )
            elif normalized_section == "fundamentals":
                collected[normalized_section] = self.fundamentals_snapshot(
                    symbol,
                    curr_date=curr_date,
                    freq=freq,
                    source=source,
                )
            else:
                raise ValueError(f"Unsupported A-stock section: {section!r}")
        return collected

    def to_payload(
        self,
        symbol: str,
        *,
        sections: Sequence[str] = ("market", "news", "fundamentals"),
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: Optional[str] = None,
        limit: Optional[int] = None,
        look_back_days: Optional[int] = None,
        curr_date: Optional[str] = None,
        freq: Optional[str] = None,
    ) -> Dict[str, Any]:
        collected = self.collect(
            symbol,
            sections=sections,
            source=source,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            limit=limit,
            look_back_days=look_back_days,
            curr_date=curr_date,
            freq=freq,
        )
        normalized = self.normalize_symbol(symbol)
        if not collected:
            payload = {
                "symbol": normalized,
                "raw_symbol": symbol,
                "status": "empty",
                "sections": {},
                "capabilities": [],
                "source_hint": source,
            }
            payload["summary"] = self.describe(payload)
            return payload
        payload = {
            "symbol": normalized,
            "raw_symbol": symbol,
            "status": _SECTION_OK if all(bundle.status == _SECTION_OK for bundle in collected.values()) else _SECTION_PARTIAL,
            "sections": {name: bundle.to_dict() for name, bundle in collected.items()},
            "capabilities": [cap for bundle in collected.values() for cap in bundle.capabilities],
            "source_hint": source,
        }
        if any(bundle.status == _SECTION_EMPTY for bundle in collected.values()):
            payload["status"] = _SECTION_EMPTY if all(bundle.status == _SECTION_EMPTY for bundle in collected.values()) else _SECTION_PARTIAL
        if any(bundle.status == _SECTION_ERROR for bundle in collected.values()):
            payload["status"] = _SECTION_ERROR if all(bundle.status == _SECTION_ERROR for bundle in collected.values()) else _SECTION_PARTIAL
        payload["summary"] = self.describe(payload)
        return payload

    def describe(self, payload: Mapping[str, Any]) -> str:
        sections = payload.get("sections", {})
        if not isinstance(sections, dict) or not sections:
            return f"A-stock analysis for {payload.get('symbol')} has no collected sections."
        parts: List[str] = []
        for name in ("market", "news", "fundamentals"):
            bundle = sections.get(name)
            if not isinstance(bundle, dict):
                continue
            parts.append(f"{name}:{bundle.get('status', 'unknown')}[{bundle.get('summary', '')}]")
        return " | ".join(parts)


__all__ = ["AStockInterface", "AStockSectionBundle"]

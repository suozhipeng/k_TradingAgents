"""Typed request/response schema for the A-share data router."""

from __future__ import annotations

import logging

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
logger = logging.getLogger(__name__)


_PRIVATE_KEYS = frozenset(("meta", "notes", "raw", "raw_payload", "source_payload", "provider_payload"))


def _freeze(value: Any) -> Any:
    """Turn nested containers into a stable, hashable representation."""
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(val)) for key, val in value.items()))
    if isinstance(value, (list, tuple, set)):  # type: ignore[arg-type]
        return tuple(_freeze(item) for item in value)
    return value


def _coerce_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if "." in text or "e" in text.lower():
                return float(text)
            return int(text)
        except ValueError:
            return value
    return value


def _as_records(payload: Any) -> List[Any]:
    """Best-effort conversion of a payload into a list of records."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, tuple):
        return list(payload)
    if isinstance(payload, dict):
        if "records" in payload and isinstance(payload["records"], list):
            return payload["records"]
        if "items" in payload and isinstance(payload["items"], list):
            return payload["items"]
        if "rows" in payload and isinstance(payload["rows"], list):
            return payload["rows"]
        if "bars" in payload and isinstance(payload["bars"], list):
            return payload["bars"]
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        # A single record is still useful as a one-item list.
        return [payload]
    if hasattr(payload, "to_dict"):
        try:
            records = payload.to_dict(orient="records")
            if isinstance(records, list):
                return records
        except Exception:
            pass
    return [payload]


def _dedupe_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate history rows by date-like keys, keeping the last row."""
    seen: Dict[Any, Dict[str, Any]] = {}
    order: List[Any] = []
    for record in records:
        if not isinstance(record, dict):
            key = id(record)
            seen[key] = {"value": record}
            order.append(key)
            continue
        key = record.get("date") or record.get("datetime") or record.get("trade_date") or record.get("time")
        if key is None:
            key = id(record)
        if key not in seen:
            order.append(key)
        seen[key] = record
    return [copy.deepcopy(seen[key]) for key in order]


def _normalize_bar(record: Any) -> Dict[str, Any]:
    if not isinstance(record, dict):
        return {"value": record}

    alias_map = {
        "date": ("date", "trade_date", "datetime", "time"),
        "open": ("open", "Open", "open_price", "o"),
        "high": ("high", "High", "high_price", "h"),
        "low": ("low", "Low", "low_price", "l"),
        "close": ("close", "Close", "close_price", "c", "last", "latest"),
        "volume": ("volume", "Volume", "vol", "turnover_volume"),
        "amount": ("amount", "amt", "turnover", "turnover_amount"),
        "turnover_rate": ("turnover_rate", "turnover", "turnoverRatio", "turnover_ratio"),
        "pe": ("pe", "PE", "pe_ttm", "pe_ratio"),
        "pb": ("pb", "PB", "pb_ratio"),
        "market_cap": ("market_cap", "marketCap", "total_market_value", "total_mv"),
    }

    normalized: Dict[str, Any] = {}
    for target, aliases in alias_map.items():
        for alias in aliases:
            if alias in record and record[alias] is not None:
                value = record[alias]
                if target in ("open", "high", "low", "close", "volume", "amount", "turnover_rate", "pe", "pb", "market_cap"):
                    value = _coerce_number(value)
                normalized[target] = value
                break

    for key, value in record.items():
        if key in _PRIVATE_KEYS or key in normalized:
            continue
        normalized[key] = copy.deepcopy(value)

    return normalized


def _normalize_items(items: Iterable[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append({k: copy.deepcopy(v) for k, v in item.items() if k not in _PRIVATE_KEYS})
        else:
            normalized.append({"value": copy.deepcopy(item)})
    return normalized


@dataclass(frozen=True)
class AStockRequest:
    """Normalized request envelope for every router call."""

    capability: str
    raw_symbol: str
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    interval: str = "1d"
    limit: Optional[int] = None
    page: Optional[int] = None
    query: Optional[str] = None
    fields: Tuple[str, ...] = field(default_factory=tuple)
    source_hint: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def cache_key(self) -> Tuple[Any, ...]:
        return (
            self.capability,
            self.symbol,
            self.start_date,
            self.end_date,
            self.interval,
            self.limit,
            self.page,
            self.query,
            tuple(self.fields),
            tuple(sorted((str(key), _freeze(value)) for key, value in self.extras.items())),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "raw_symbol": self.raw_symbol,
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "interval": self.interval,
            "limit": self.limit,
            "page": self.page,
            "query": self.query,
            "fields": list(self.fields),
            "source_hint": self.source_hint,
            "extras": copy.deepcopy(self.extras),
        }


@dataclass(frozen=True)
class AStockResponse:
    """Stable result envelope returned by the router and facade."""

    status: str
    capability: str
    symbol: str
    raw_symbol: str
    source: Optional[str] = None
    sources_tried: Tuple[str, ...] = field(default_factory=tuple)
    data: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    cached: bool = False
    empty: bool = False
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    request: Optional[Dict[str, Any]] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def with_cached(self, cached: bool) -> "AStockResponse":
        return AStockResponse(
            status=self.status,
            capability=self.capability,
            symbol=self.symbol,
            raw_symbol=self.raw_symbol,
            source=self.source,
            sources_tried=self.sources_tried,
            data=copy.deepcopy(self.data),
            meta=copy.deepcopy(self.meta),
            cached=cached,
            empty=self.empty,
            error_code=self.error_code,
            error_message=self.error_message,
            request=copy.deepcopy(self.request),
            notes=self.notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status,
            "capability": self.capability,
            "symbol": self.symbol,
            "raw_symbol": self.raw_symbol,
            "source": self.source,
            "sources_tried": list(self.sources_tried),
            "cached": self.cached,
            "empty": self.empty,
            "meta": copy.deepcopy(self.meta),
            "notes": list(self.notes),
            "request": copy.deepcopy(self.request),
        }
        payload["data"] = copy.deepcopy(self.data)
        if self.error_code or self.error_message:
            payload["error"] = {
                "code": self.error_code,
                "message": self.error_message,
            }
        else:
            payload["error"] = None
        return payload

    @classmethod
    def ok(
        cls,
        *,
        capability: str,
        symbol: str,
        raw_symbol: str,
        source: Optional[str],
        data: Optional[Dict[str, Any]],
        meta: Optional[Dict[str, Any]] = None,
        sources_tried: Sequence[str] = (),
        cached: bool = False,
        request: Optional[AStockRequest] = None,
        notes: Sequence[str] = (),
    ) -> "AStockResponse":
        return cls(
            status="ok",
            capability=capability,
            symbol=symbol,
            raw_symbol=raw_symbol,
            source=source,
            sources_tried=tuple(sources_tried),
            data=copy.deepcopy(data),
            meta=copy.deepcopy(meta or {}),
            cached=cached,
            empty=False,
            error_code=None,
            error_message=None,
            request=request.to_dict() if request else None,
            notes=tuple(notes),
        )

    @classmethod
    def empty_result(
        cls,
        *,
        capability: str,
        symbol: str,
        raw_symbol: str,
        error_code: str,
        error_message: str,
        source: Optional[str] = None,
        sources_tried: Sequence[str] = (),
        request: Optional[AStockRequest] = None,
        meta: Optional[Dict[str, Any]] = None,
        notes: Sequence[str] = (),
    ) -> "AStockResponse":
        return cls(
            status="empty",
            capability=capability,
            symbol=symbol,
            raw_symbol=raw_symbol,
            source=source,
            sources_tried=tuple(sources_tried),
            data=None,
            meta=copy.deepcopy(meta or {}),
            cached=False,
            empty=True,
            error_code=error_code,
            error_message=error_message,
            request=request.to_dict() if request else None,
            notes=tuple(notes),
        )

    @classmethod
    def error_result(
        cls,
        *,
        capability: str,
        symbol: str,
        raw_symbol: str,
        error_code: str,
        error_message: str,
        source: Optional[str] = None,
        sources_tried: Sequence[str] = (),
        request: Optional[AStockRequest] = None,
        meta: Optional[Dict[str, Any]] = None,
        notes: Sequence[str] = (),
    ) -> "AStockResponse":
        return cls(
            status="error",
            capability=capability,
            symbol=symbol,
            raw_symbol=raw_symbol,
            source=source,
            sources_tried=tuple(sources_tried),
            data=None,
            meta=copy.deepcopy(meta or {}),
            cached=False,
            empty=False,
            error_code=error_code,
            error_message=error_message,
            request=request.to_dict() if request else None,
            notes=tuple(notes),
        )


def normalize_capability_payload(
    capability: str,
    payload: Any,
    request: AStockRequest,
    source: str,
    *,
    include_raw: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], bool]:
    """Normalize a provider payload into stable data/meta tuples.

    Returns:
        ``(data, meta, empty)``
    """
    raw_meta: Dict[str, Any] = {}
    payload_notes: List[str] = []
    if isinstance(payload, dict):
        raw_meta = copy.deepcopy(payload.get("meta", {})) if isinstance(payload.get("meta", {}), dict) else {}
        raw_notes = payload.get("notes", ())
        if isinstance(raw_notes, str):
            payload_notes = [raw_notes]
        elif isinstance(raw_notes, (list, tuple)):
            payload_notes = [str(item) for item in raw_notes]

    meta: Dict[str, Any] = {
        "source": source,
        "capability": capability,
        "normalized_symbol": request.symbol,
        "raw_symbol": request.raw_symbol,
    }
    if request.start_date:
        meta["start_date"] = request.start_date
    if request.end_date:
        meta["end_date"] = request.end_date
    if request.interval:
        meta["interval"] = request.interval
    if request.query:
        meta["query"] = request.query
    if request.limit is not None:
        meta["limit"] = request.limit
    if request.page is not None:
        meta["page"] = request.page
    if raw_meta:
        meta["provider_meta"] = raw_meta
        meta.update({key: copy.deepcopy(value) for key, value in raw_meta.items() if key not in meta})
    if payload_notes:
        meta["provider_notes"] = payload_notes

    if isinstance(payload, AStockResponse):
        return payload.data, meta, payload.empty

    if payload is None:
        return None, meta, True

    if capability == "kline":
        bars_payload: Any = None
        if isinstance(payload, dict):
            bars_payload = payload.get("bars")
            if bars_payload is None:
                bars_payload = payload.get("records")
            if bars_payload is None:
                bars_payload = payload.get("rows")
            if bars_payload is None:
                bars_payload = payload.get("data")
        else:
            bars_payload = payload

        bars = _as_records(bars_payload)
        normalized_bars = _dedupe_records([_normalize_bar(record) for record in bars])
        data = {
            "bars": normalized_bars,
            "count": len(normalized_bars),
            "symbol": request.symbol,
            "raw_symbol": request.raw_symbol,
            "interval": request.interval,
        }
        if request.start_date:
            data["start_date"] = request.start_date
        if request.end_date:
            data["end_date"] = request.end_date
        return data, meta, len(normalized_bars) == 0

    if isinstance(payload, dict):
        normalized = {k: copy.deepcopy(v) for k, v in payload.items() if k not in _PRIVATE_KEYS}
        if "items" in normalized:
            items = _normalize_items(_as_records(normalized["items"]))
            data = {
                "items": items,
                "count": len(items),
            }
            for key in ("total", "page", "pages", "source_url", "url"):
                if key in normalized:
                    data[key] = copy.deepcopy(normalized[key])
            if request.query:
                data["query"] = request.query
            return data, meta, len(items) == 0

        if "bars" in normalized:
            bars = _dedupe_records([_normalize_bar(record) for record in _as_records(normalized["bars"])])
            data = {
                "bars": bars,
                "count": len(bars),
                "symbol": request.symbol,
                "raw_symbol": request.raw_symbol,
            }
            return data, meta, len(bars) == 0

        for metric_key in ("pe", "pb", "market_cap", "turnover_rate", "volume", "amount"):
            if metric_key in normalized:
                normalized[metric_key] = _coerce_number(normalized[metric_key])
        data = normalized or None
        return data, meta, data is None

    if isinstance(payload, list):
        items = _normalize_items(payload)
        data = {"items": items, "count": len(items)}
        return data, meta, len(items) == 0

    data = {"value": copy.deepcopy(payload)}
    return data, meta, False

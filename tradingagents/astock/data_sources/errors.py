"""Unified error types for the A-share data access layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class AStockDataError(Exception):
    """Base class for all normalized A-share data access failures."""

    error_code = "ASTOCK_DATA_ERROR"

    def __init__(self, message: str, *, source: Optional[str] = None, capability: Optional[str] = None):
        super(AStockDataError, self).__init__(message)
        self.source = source
        self.capability = capability


class AStockNoDataError(AStockDataError):
    """Raised by adapters when the source has no rows/items for the request."""

    error_code = "NO_DATA_AVAILABLE"

    def __init__(self, symbol: str, canonical: Optional[str] = None, detail: str = "", *, source: Optional[str] = None, capability: Optional[str] = None):
        self.symbol = symbol
        self.canonical = canonical or symbol
        self.detail = detail
        message = "No market data for {0!r}".format(symbol)
        if canonical and canonical != symbol:
            message += " (queried as {0!r})".format(canonical)
        if detail:
            message += ": {0}".format(detail)
        super(AStockNoDataError, self).__init__(message, source=source, capability=capability)


class AStockSourceUnavailableError(AStockDataError):
    """Raised when a source adapter is missing, disabled, or misconfigured."""

    error_code = "SOURCE_UNAVAILABLE"

    def __init__(self, source: str, detail: str = "", *, capability: Optional[str] = None):
        self.source = source
        self.detail = detail
        message = "Source {0!r} unavailable".format(source)
        if detail:
            message += ": {0}".format(detail)
        super(AStockSourceUnavailableError, self).__init__(message, source=source, capability=capability)


class AStockSchemaError(AStockDataError):
    """Raised when a source returns payload that cannot be normalized."""

    error_code = "SCHEMA_ERROR"


@dataclass(frozen=True)
class AStockRouteNote:
    """Human-readable notes emitted by the router for diagnostics."""

    source: str
    message: str
    detail: str = ""

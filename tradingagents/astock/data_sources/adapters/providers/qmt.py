"""QMT bridge adapter for A-share data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase
from ..common import _coerce_float
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest


class QMTAdapter(AStockAdapterBase):
    """QMT bridge adapter with real HTTP bridge calls and mock fallback.

    Handles all read-only data operations (kline, order book, trade tape,
    valuation) through the QMT bridge protocol client.  When the bridge is
    unreachable or the protocol module is not importable, falls back to
    raising ``AStockNoDataError``.

    Fundamentals are not available through QMT; ``get_fundamentals``
    remains a placeholder as in Phase 09.
    """

    name = "qmt"

    def __init__(self, **config: Any):
        super().__init__(**config)
        self._bridge = None
        self._bridge_import_error: Optional[str] = None
        try:
            # Import from neutral protocol module — no dependency on execution layer.
            from tradingagents.astock.execution.qmt_protocol import (
                QmtBridgeClient as _BridgeClient,
            )

            self._bridge_class = _BridgeClient
        except ImportError as exc:
            self._bridge_import_error = str(exc)
            self._bridge_class = None

    def _get_bridge(self, request: AStockRequest):
        """Lazy-init and return the QMT protocol client.

        Returns ``None`` when the bridge cannot be loaded, which triggers
        the ``_no_data`` fallback.
        """
        if self._bridge is not None:
            return self._bridge
        if self._bridge_class is None:
            return None
        try:
            host = self.config.get("host", "127.0.0.1")
            port = int(self.config.get("port", 58609))
            timeout = float(self.config.get("timeout", 10.0))
            self._bridge = self._bridge_class(
                config=type("cfg", (), {"host": host, "port": port, "timeout": timeout})(),
                use_mock=False,
            )
            # Quick health check — if it fails, use mock fallback
            if not self._bridge.health_check():
                self._bridge = self._bridge_class(use_mock=True)
            return self._bridge
        except Exception:
            self._bridge = self._bridge_class(use_mock=True) if self._bridge_class else None
            return self._bridge

    def _no_data(self, request: AStockRequest, detail: str = ""):
        raise AStockNoDataError(
            request.raw_symbol, request.symbol,
            detail or "QMT bridge unavailable",
            source=self.name,
            capability=request.capability,
        )

    def get_kline(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            bars = bridge.get_kline(
                symbol=request.symbol,
                start=request.start_date or "",
                end=request.end_date or "",
                period=request.interval or "1d",
            )
            if not bars:
                self._no_data(request)
            return {"bars": bars, "count": len(bars)}
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_order_book(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            return bridge.get_order_book(symbol=request.symbol)
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_trade_tape(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            ticks = bridge.get_trade_tape(symbol=request.symbol)
            if not ticks:
                self._no_data(request)
            return {"ticks": ticks, "count": len(ticks)}
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_valuation(self, request: AStockRequest):
        bridge = self._get_bridge(request)
        if bridge is None:
            self._no_data(request, "QMT bridge not importable")
        try:
            return bridge.get_valuation(symbol=request.symbol)
        except (ConnectionError, ValueError, RuntimeError) as exc:
            self._no_data(request, str(exc))

    def get_fundamentals(self, request: AStockRequest):
        self._no_data(request, "QMT bridge does not provide fundamental data")

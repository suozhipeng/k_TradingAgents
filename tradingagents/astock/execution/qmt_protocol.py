"""Shared QMT bridge protocol types.

This module is intentionally neutral — it has **no imports from
``execution/qmt_bridge``** so that ``data_sources`` can depend on it
without pulling in the execution layer.

Both ``data_sources.adapters.providers.qmt`` (read-only data adapter)
and ``execution.qmt_bridge`` (order execution) import from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QmtBridgeConfig:
    """Configuration for the QMT HTTP bridge connection.

    Attributes
    ----------
    host : str
        Bridge host (default 127.0.0.1).
    port : int
        Bridge port (default 58609).
    timeout : float
        HTTP request timeout in seconds (default 10.0).
    """

    host: str = "127.0.0.1"
    port: int = 58609
    timeout: float = 10.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class QmtBridgeClient:
    """Minimal QMT bridge protocol client (read-only + execution).

    This class implements the wire protocol that both the data adapter
    and the execution layer need.  Real HTTP calls are delegated to
    ``execution.qmt_bridge.operations`` at runtime; mock mode returns
    deterministic data without network calls.
    """

    def __init__(
        self,
        config: Optional[QmtBridgeConfig] = None,
        use_mock: bool = False,
    ) -> None:
        self._config = config or QmtBridgeConfig()
        self._use_mock = use_mock

    # -- public properties --------------------------------------------------

    @property
    def config(self) -> QmtBridgeConfig:
        """Return the bridge configuration (read-only)."""
        return self._config

    @property
    def is_mock(self) -> bool:
        """Return True if this bridge is in mock mode."""
        return self._use_mock

    # -- public API (delegates to _do_* which is overridden by subclasses) ---

    def health_check(self) -> bool:
        """Ping the QMT bridge."""
        if self._use_mock:
            return True
        return self._do_health_check()

    def get_kline(
        self,
        symbol: str,
        start: str = "",
        end: str = "",
        period: str = "1d",
    ) -> List[Dict[str, Any]]:
        """Retrieve historical kline data."""
        return self._do_get_kline(symbol, start, end, period)

    def get_order_book(self, symbol: str) -> Dict[str, Any]:
        """Retrieve the current order book."""
        return self._do_get_order_book(symbol)

    def get_trade_tape(self, symbol: str) -> List[Dict[str, Any]]:
        """Retrieve recent trade tape."""
        return self._do_get_trade_tape(symbol)

    def get_valuation(self, symbol: str) -> Dict[str, Any]:
        """Retrieve current valuation snapshot."""
        return self._do_get_valuation(symbol)

    def place_order(
        self,
        symbol: str,
        direction: str,
        price: float,
        volume: int,
        order_type: str = "limit",
    ) -> Dict[str, Any]:
        """Place an order through the QMT bridge."""
        return self._do_place_order(symbol, direction, price, volume, order_type)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        return self._do_cancel_order(order_id)

    def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieve current positions."""
        return self._do_get_positions()

    def get_account_info(self) -> Dict[str, Any]:
        """Retrieve account information."""
        return self._do_get_account_info()

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Raw protocol request — for tests that verify the bridge protocol."""
        if self._use_mock:
            raise RuntimeError("QMT bridge raw request is unavailable in mock mode")
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    # -- internal dispatch (overridden by execution.qmt_bridge.client) ------

    # These methods are overridden by the real client in
    # ``execution.qmt_bridge.client``.  The base class provides mock-mode
    # defaults so that the data adapter can use this class directly without
    # pulling in the execution-layer transport code.

    def _do_health_check(self) -> bool:
        if self._use_mock:
            return True
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_kline(
        self, symbol: str, start: str, end: str, period: str
    ) -> List[Dict[str, Any]]:
        if self._use_mock:
            return []
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_order_book(self, symbol: str) -> Dict[str, Any]:
        if self._use_mock:
            return {}
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_trade_tape(self, symbol: str) -> List[Dict[str, Any]]:
        if self._use_mock:
            return []
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_valuation(self, symbol: str) -> Dict[str, Any]:
        if self._use_mock:
            return {}
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_place_order(
        self, symbol: str, direction: str, price: float, volume: int, order_type: str
    ) -> Dict[str, Any]:
        if self._use_mock:
            return {"order_id": "mock"}
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_cancel_order(self, order_id: str) -> bool:
        if self._use_mock:
            return True
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_positions(self) -> List[Dict[str, Any]]:
        if self._use_mock:
            return []
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _do_get_account_info(self) -> Dict[str, Any]:
        if self._use_mock:
            return {}
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Raw protocol request — for tests that verify the bridge protocol."""
        if self._use_mock:
            raise RuntimeError("QMT bridge raw request is unavailable in mock mode")
        raise RuntimeError("QmtBridgeClient not initialised — missing transport layer")


__all__ = [
    "QmtBridgeConfig",
    "QmtBridgeClient",
]

"""HTTP bridge protocol and client for QMT (迅投) controlled execution.

Architecture
------------
    Python (this process)  ──HTTP JSON──>  localhost:58609  ──>  QMT Bridge Script (Python 3.6.8)
                                                                    │
                                                                    ├── xtdata → Mini QMT (:58610) — read-only data
                                                                    └── xttrader → Full QMT         — order placement

The bridge protocol is a simple request/response JSON-RPC-style protocol:

    Request:  {"method": "kline", "params": {...}, "id": "uuid"}
    Response: {"result": {...}, "error": None}  or  {"result": None, "error": "..."}

This module provides the client side only.  The bridge server is a separate
process (not part of this repository).

Mock mode
---------
When ``use_mock=True`` is passed during construction, all methods return
deterministic, self-consistent fake data without making any HTTP calls.
This is used for unit testing and when QMT is not available.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..qmt_protocol import QmtBridgeClient as _BaseClient
from ..qmt_protocol import QmtBridgeConfig

from .operations import (
    DEFAULT_QMT_HOST,
    DEFAULT_QMT_PORT,
    DEFAULT_QMT_TIMEOUT,
    op_cancel_order,
    op_get_account_info,
    op_get_kline,
    op_get_order_book,
    op_get_positions,
    op_get_trade_tape,
    op_get_valuation,
    op_health_check,
    op_place_order,
    _send_request,
)

_logger = logging.getLogger(__name__)


class QmtBridge(_BaseClient):
    """HTTP JSON-RPC-style client for the QMT bridge server.

    Parameters
    ----------
    config : QmtBridgeConfig
        Connection parameters.
    use_mock : bool
        If True, return deterministic mock data without network calls.
    """

    def __init__(
        self,
        config: Optional[QmtBridgeConfig] = None,
        use_mock: bool = False,
    ) -> None:
        super().__init__(config=config, use_mock=use_mock)
        # Bind transport methods so base-class hooks work.
        self._transport_config = config or QmtBridgeConfig()

    # -- health check -------------------------------------------------------

    def _do_health_check(self) -> bool:
        if self._use_mock:
            return True
        return op_health_check(self._transport_config.base_url, self._transport_config.timeout)

    # -- read-only data methods ----------------------------------------------

    def _do_get_kline(
        self, symbol: str, start: str, end: str, period: str
    ) -> List[Dict[str, Any]]:
        return op_get_kline(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, symbol, start=start, end=end, period=period,
        )

    def _do_get_order_book(self, symbol: str) -> Dict[str, Any]:
        return op_get_order_book(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, symbol,
        )

    def _do_get_trade_tape(self, symbol: str) -> List[Dict[str, Any]]:
        return op_get_trade_tape(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, symbol,
        )

    def _do_get_valuation(self, symbol: str) -> Dict[str, Any]:
        return op_get_valuation(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, symbol,
        )

    # -- execution methods --------------------------------------------------

    def _do_place_order(
        self, symbol: str, direction: str, price: float, volume: int, order_type: str
    ) -> Dict[str, Any]:
        return op_place_order(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, symbol, direction, price, volume, order_type,
        )

    def _do_cancel_order(self, order_id: str) -> bool:
        return op_cancel_order(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock, order_id,
        )

    def _do_get_positions(self) -> List[Dict[str, Any]]:
        return op_get_positions(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock,
        )

    def _do_get_account_info(self) -> Dict[str, Any]:
        return op_get_account_info(
            self._transport_config.base_url, self._transport_config.timeout,
            self._use_mock,
        )

    # -- raw protocol request (compatibility hook) --------------------------

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a raw request through the bridge client.

        Kept as a narrow compatibility hook for callers/tests that verify the
        bridge protocol directly.
        """
        if self._use_mock:
            raise RuntimeError("QMT bridge raw request is unavailable in mock mode")
        return _send_request(self._transport_config.base_url, self._transport_config.timeout, method, params)


__all__ = [
    "QmtBridge",
    "DEFAULT_QMT_HOST",
    "DEFAULT_QMT_PORT",
    "DEFAULT_QMT_TIMEOUT",
]

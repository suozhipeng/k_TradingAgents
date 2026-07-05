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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
)

_logger = logging.getLogger(__name__)


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

    host: str = DEFAULT_QMT_HOST
    port: int = DEFAULT_QMT_PORT
    timeout: float = DEFAULT_QMT_TIMEOUT

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class QmtBridge:
    """HTTP JSON-RPC-style client for the QMT bridge server.

    Parameters
    ----------
    config : QmtBridgeConfig
        Connection parameters.
    use_mock : bool
        If True, return deterministic mock data without network calls.
    """

    def __init__(self, config: Optional[QmtBridgeConfig] = None, use_mock: bool = False) -> None:
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

    # -- health check -------------------------------------------------------

    def health_check(self) -> bool:
        """Ping the QMT bridge.

        Returns
        -------
        bool
            True if the bridge responds successfully.
        """
        if self._use_mock:
            return True
        return op_health_check(self._config.base_url, self._config.timeout)

    # -- read-only data methods (also available in mock mode) ----------------

    def get_kline(
        self, symbol: str, start: str = "", end: str = "", period: str = "1d"
    ) -> List[Dict[str, Any]]:
        """Retrieve historical kline (candlestick) data.

        Parameters
        ----------
        symbol : str
            Stock symbol (e.g. ``000001.SZ``).
        start : str
            Start date (``YYYY-MM-DD``).  Empty = earliest available.
        end : str
            End date (``YYYY-MM-DD``).  Empty = latest available.
        period : str
            Bar period (``1m``, ``5m``, ``15m``, ``30m``, ``60m``, ``1d``, ``1w``, ``1mo``).

        Returns
        -------
        list[dict]
        """
        return op_get_kline(
            self._config.base_url, self._config.timeout,
            self._use_mock, symbol, start=start, end=end, period=period,
        )

    def get_order_book(self, symbol: str) -> Dict[str, Any]:
        """Retrieve the current order book (level-2 snapshot).

        Parameters
        ----------
        symbol : str
            Stock symbol.

        Returns
        -------
        dict
        """
        return op_get_order_book(
            self._config.base_url, self._config.timeout, self._use_mock, symbol,
        )

    def get_trade_tape(self, symbol: str) -> List[Dict[str, Any]]:
        """Retrieve recent trade tape (tick-by-tick transaction log).

        Parameters
        ----------
        symbol : str
            Stock symbol.

        Returns
        -------
        list[dict]
        """
        return op_get_trade_tape(
            self._config.base_url, self._config.timeout, self._use_mock, symbol,
        )

    def get_valuation(self, symbol: str) -> Dict[str, Any]:
        """Retrieve current valuation snapshot for a symbol.

        Parameters
        ----------
        symbol : str
            Stock symbol.

        Returns
        -------
        dict
        """
        return op_get_valuation(
            self._config.base_url, self._config.timeout, self._use_mock, symbol,
        )

    # -- execution methods (only available in real mode + controlled execution layer)

    def place_order(
        self,
        symbol: str,
        direction: str,
        price: float,
        volume: int,
        order_type: str = "limit",
    ) -> Dict[str, Any]:
        """Place an order through the QMT bridge.

        Parameters
        ----------
        symbol : str
            Stock symbol.
        direction : str
            ``"buy"`` or ``"sell"``.
        price : float
            Order price.
        volume : int
            Number of shares.
        order_type : str
            ``"limit"`` or ``"market"``.

        Returns
        -------
        dict
            Order confirmation with ``order_id``.
        """
        return op_place_order(
            self._config.base_url, self._config.timeout, self._use_mock,
            symbol, direction, price, volume, order_type,
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.

        Parameters
        ----------
        order_id : str
            The order ID to cancel.

        Returns
        -------
        bool
            True if cancelled successfully.
        """
        return op_cancel_order(
            self._config.base_url, self._config.timeout, self._use_mock, order_id,
        )

    def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieve current positions.

        Returns
        -------
        list[dict]
        """
        return op_get_positions(
            self._config.base_url, self._config.timeout, self._use_mock,
        )

    def get_account_info(self) -> Dict[str, Any]:
        """Retrieve account information.

        Returns
        -------
        dict
        """
        return op_get_account_info(
            self._config.base_url, self._config.timeout, self._use_mock,
        )


__all__ = [
    "QmtBridgeConfig",
    "QmtBridge",
    "DEFAULT_QMT_HOST",
    "DEFAULT_QMT_PORT",
    "DEFAULT_QMT_TIMEOUT",
]

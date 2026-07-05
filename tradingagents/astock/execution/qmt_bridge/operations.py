"""Operations for QmtBridge - all capability method implementations.

This module contains the mock data helpers and the operation functions
that the QmtBridge class delegates to.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.request import Request as HTTPRequest, urlopen as _default_urlopen
from urllib.error import URLError
from urllib.parse import urljoin

_logger = logging.getLogger(__name__)

# Default bridge endpoint
DEFAULT_QMT_HOST = "127.0.0.1"
DEFAULT_QMT_PORT = 58609
DEFAULT_QMT_TIMEOUT = 10.0

# Public patch point used by the package facade and compatibility tests.
urlopen = _default_urlopen


def _resolve_urlopen():
    package = sys.modules.get(__package__)
    return getattr(package, "urlopen", urlopen)


def _mock_kline(symbol: str, period: str = "1d", count: int = 100) -> List[Dict[str, Any]]:
    """Generate deterministic mock kline bars."""
    base_price = 10.0 if "600" in symbol or "000" in symbol else 100.0
    bars: List[Dict[str, Any]] = []
    for i in range(count):
        date = f"2024-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"
        open_p = round(base_price + i * 0.05, 2)
        high_p = round(open_p + 0.3, 2)
        low_p = round(open_p - 0.2, 2)
        close_p = round(open_p + 0.1, 2)
        volume = 1_000_000 + i * 10_000
        bars.append(
            {
                "symbol": symbol,
                "date": date,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": volume,
                "period": period,
            }
        )
    return bars


def _mock_order_book(symbol: str) -> Dict[str, Any]:
    """Generate deterministic mock order book (level-2 style snapshot)."""
    return {
        "symbol": symbol,
        "time": "2024-06-14 14:30:00",
        "bid_prices": [10.01, 10.00, 9.99, 9.98, 9.97],
        "bid_volumes": [1000, 2000, 1500, 800, 600],
        "ask_prices": [10.02, 10.03, 10.04, 10.05, 10.06],
        "ask_volumes": [1200, 1800, 900, 700, 500],
    }


def _mock_trade_tape(symbol: str, count: int = 20) -> List[Dict[str, Any]]:
    """Generate deterministic mock trade tape ticks."""
    ticks: List[Dict[str, Any]] = []
    base_price = 10.0
    for i in range(count):
        ticks.append(
            {
                "symbol": symbol,
                "time": f"2024-06-14 14:{(i // 60):02d}:{(i % 60):02d}",
                "price": round(base_price + i * 0.01, 2),
                "volume": 1000 + i * 100,
                "direction": "buy" if i % 2 == 0 else "sell",
            }
        )
    return ticks


def _mock_valuation(symbol: str) -> Dict[str, Any]:
    """Generate deterministic mock valuation snapshot."""
    return {
        "symbol": symbol,
        "name": f"Stock-{symbol}",
        "last_price": 10.05,
        "open_price": 10.00,
        "high_price": 10.12,
        "low_price": 9.95,
        "pre_close": 9.98,
        "volume": 5_000_000,
        "amount": 50_250_000.0,
        "change_pct": 0.70,
        "pe_ttm": 15.2,
        "pb": 1.8,
        "market_cap": 10_000_000_000.0,
        "turnover_rate": 0.5,
    }


def _mock_positions() -> List[Dict[str, Any]]:
    """Generate deterministic mock positions."""
    return [
        {"symbol": "000001.SZ", "name": "平安银行", "volume": 1000, "available": 1000, "cost_price": 10.50, "current_price": 10.80, "pnl": 300.0, "pnl_pct": 2.86},
        {"symbol": "600519.SH", "name": "贵州茅台", "volume": 100, "available": 100, "cost_price": 1800.0, "current_price": 1850.0, "pnl": 5000.0, "pnl_pct": 2.78},
    ]


def _mock_account_info() -> Dict[str, Any]:
    """Generate deterministic mock account info."""
    return {
        "account_id": "MOCK-ACCT-001",
        "total_asset": 1_500_000.0,
        "cash": 500_000.0,
        "market_value": 1_000_000.0,
        "frozen_cash": 0.0,
        "available_cash": 500_000.0,
        "margin": 0.0,
    }


# ---------------------------------------------------------------------------
# Operation functions - called by QmtBridge methods
# ---------------------------------------------------------------------------


def _send_request(
    base_url: str,
    timeout: float,
    method: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send an HTTP JSON request to the QMT bridge and return the result.

    Parameters
    ----------
    base_url : str
        Bridge base URL (e.g. ``http://127.0.0.1:58609``).
    timeout : float
        Request timeout in seconds.
    method : str
        RPC method name.
    params : dict, optional
        Method parameters.

    Returns
    -------
    dict
        The ``result`` field from the bridge response.

    Raises
    ------
    ConnectionError
        When the bridge is unreachable.
    ValueError
        When the bridge returns an error response.
    """
    payload = {
        "method": method,
        "params": params or {},
        "id": str(uuid.uuid4()),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = urljoin(base_url, "/api/v1/qmt")

    req = HTTPRequest(
        url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with _resolve_urlopen()(req, timeout=int(timeout)) as resp:
            raw = resp.read().decode("utf-8")
    except URLError as exc:
        raise ConnectionError(f"QMT bridge unreachable at {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ConnectionError(f"QMT bridge timeout after {timeout}s at {url}") from exc

    try:
        response = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"QMT bridge returned invalid JSON: {exc}") from exc

    if response.get("error"):
        raise ValueError(f"QMT bridge error for method {method!r}: {response['error']}")

    result = response.get("result")
    if result is None:
        return {}

    return result  # type: ignore[return-value]


def op_health_check(base_url: str, timeout: float) -> bool:
    """Ping the QMT bridge.

    Returns
    -------
    bool
        True if the bridge responds successfully.
    """
    try:
        _send_request(base_url, timeout, "health_check")
        return True
    except (ConnectionError, ValueError):
        return False


def op_get_kline(
    base_url: str,
    timeout: float,
    use_mock: bool,
    symbol: str,
    start: str = "",
    end: str = "",
    period: str = "1d",
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
    if use_mock:
        return _mock_kline(symbol, period=period)
    params: Dict[str, Any] = {"symbol": symbol, "period": period}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return _send_request(base_url, timeout, "kline", params)  # type: ignore[return-value]


def op_get_order_book(
    base_url: str, timeout: float, use_mock: bool, symbol: str
) -> Dict[str, Any]:
    """Retrieve the current order book (level-2 snapshot).

    Parameters
    ----------
    symbol : str
        Stock symbol.

    Returns
    -------
    dict
    """
    if use_mock:
        return _mock_order_book(symbol)
    return _send_request(base_url, timeout, "order_book", {"symbol": symbol})  # type: ignore[return-value]


def op_get_trade_tape(
    base_url: str, timeout: float, use_mock: bool, symbol: str
) -> List[Dict[str, Any]]:
    """Retrieve recent trade tape (tick-by-tick transaction log).

    Parameters
    ----------
    symbol : str
        Stock symbol.

    Returns
    -------
    list[dict]
    """
    if use_mock:
        return _mock_trade_tape(symbol)
    return _send_request(base_url, timeout, "trade_tape", {"symbol": symbol})  # type: ignore[return-value]


def op_get_valuation(
    base_url: str, timeout: float, use_mock: bool, symbol: str
) -> Dict[str, Any]:
    """Retrieve current valuation snapshot for a symbol.

    Parameters
    ----------
    symbol : str
        Stock symbol.

    Returns
    -------
    dict
    """
    if use_mock:
        return _mock_valuation(symbol)
    return _send_request(base_url, timeout, "valuation", {"symbol": symbol})  # type: ignore[return-value]


def op_place_order(
    base_url: str,
    timeout: float,
    use_mock: bool,
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
    if use_mock:
        return {
            "order_id": f"mock-{uuid.uuid4().hex[:12]}",
            "symbol": symbol,
            "direction": direction,
            "price": price,
            "volume": volume,
            "status": "filled",
            "filled_volume": volume,
            "filled_price": price,
        }
    return _send_request(
        base_url, timeout, "place_order",
        {
            "symbol": symbol,
            "direction": direction,
            "price": price,
            "volume": volume,
            "order_type": order_type,
        },
    )  # type: ignore[return-value]


def op_cancel_order(
    base_url: str, timeout: float, use_mock: bool, order_id: str
) -> bool:
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
    if use_mock:
        return True
    result = _send_request(base_url, timeout, "cancel_order", {"order_id": order_id})
    return bool(result.get("cancelled", True))


def op_get_positions(
    base_url: str, timeout: float, use_mock: bool
) -> List[Dict[str, Any]]:
    """Retrieve current positions.

    Returns
    -------
    list[dict]
    """
    if use_mock:
        return _mock_positions()
    return _send_request(base_url, timeout, "get_positions")  # type: ignore[return-value]


def op_get_account_info(
    base_url: str, timeout: float, use_mock: bool
) -> Dict[str, Any]:
    """Retrieve account information.

    Returns
    -------
    dict
    """
    if use_mock:
        return _mock_account_info()
    return _send_request(base_url, timeout, "get_account_info")  # type: ignore[return-value]

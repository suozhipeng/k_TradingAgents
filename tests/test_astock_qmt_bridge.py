"""Tests for the QMT bridge client (qmt_bridge.py).

Uses the same direct importlib module-loading pattern as the existing
Phase 10 tests to match the repo convention.

All network calls are mocked via ``unittest.mock.patch.object`` on the
loaded module; mock mode (``use_mock=True``) is tested against deterministic
fake data.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Direct module imports
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"
_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load a module from the execution package with correct package context."""
    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", "tradingagents.astock.execution"):
        if parent not in sys.modules:
            pkg_spec = importlib.util.spec_from_loader(parent, loader=None, is_package=True)
            parent_mod = importlib.util.module_from_spec(pkg_spec)
            parent_mod.__path__ = []
            sys.modules[parent] = parent_mod
    exec_pkg = sys.modules[_PKG_PARENT]
    exec_pkg.__path__ = [_EXEC]

    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=exec_pkg.__path__
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_qb = _load_submodule("qmt_bridge")

QmtBridgeConfig = _qb.QmtBridgeConfig
QmtBridge = _qb.QmtBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(data: Dict[str, Any], status: int = 200) -> MagicMock:
    """Create a mock HTTP response object that works as a context manager."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.status = status
    # Make the mock work with ``with urlopen(...) as resp:``
    # by returning *self* from __enter__
    resp.__enter__.return_value = resp
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQmtBridgeConfig(unittest.TestCase):
    """QmtBridgeConfig creation and defaults."""

    def test_default_config(self) -> None:
        cfg = QmtBridgeConfig()
        self.assertEqual(cfg.host, "127.0.0.1")
        self.assertEqual(cfg.port, 58609)
        self.assertEqual(cfg.timeout, 10.0)
        self.assertEqual(cfg.base_url, "http://127.0.0.1:58609")

    def test_custom_config(self) -> None:
        cfg = QmtBridgeConfig(host="10.0.0.1", port=9999, timeout=5.0)
        self.assertEqual(cfg.host, "10.0.0.1")
        self.assertEqual(cfg.port, 9999)
        self.assertEqual(cfg.timeout, 5.0)
        self.assertEqual(cfg.base_url, "http://10.0.0.1:9999")


class TestQmtBridgeInit(unittest.TestCase):
    """QmtBridge construction."""

    def test_init_default(self) -> None:
        bridge = QmtBridge()
        self.assertFalse(bridge.is_mock)
        self.assertIsInstance(bridge.config, QmtBridgeConfig)

    def test_init_mock_mode(self) -> None:
        bridge = QmtBridge(use_mock=True)
        self.assertTrue(bridge.is_mock)

    def test_init_custom_config(self) -> None:
        cfg = QmtBridgeConfig(port=9999)
        bridge = QmtBridge(config=cfg)
        self.assertEqual(bridge.config.port, 9999)


class TestQmtBridgeHealthCheck(unittest.TestCase):
    """health_check behaviour in real and mock mode."""

    def test_mock_health_check_always_true(self) -> None:
        bridge = QmtBridge(use_mock=True)
        self.assertTrue(bridge.health_check())

    @patch.object(_qb, "urlopen")
    def test_real_health_check_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"status": "ok"}, "error": None})
        bridge = QmtBridge()
        self.assertTrue(bridge.health_check())

    @patch.object(_qb, "urlopen")
    def test_real_health_check_failure(self, mock_urlopen: MagicMock) -> None:
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("connection refused")
        bridge = QmtBridge()
        self.assertFalse(bridge.health_check())

    @patch.object(_qb, "urlopen")
    def test_real_health_check_error_response(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": None, "error": "bridge busy"})
        bridge = QmtBridge()
        self.assertFalse(bridge.health_check())


class TestQmtBridgeMockMode(unittest.TestCase):
    """Deterministic mock data in mock mode."""

    def setUp(self) -> None:
        self.bridge = QmtBridge(use_mock=True)

    def test_mock_kline_structure(self) -> None:
        bars = self.bridge.get_kline("000001.SZ", period="1d")
        self.assertIsInstance(bars, list)
        self.assertGreater(len(bars), 0)
        bar = bars[0]
        self.assertIn("symbol", bar)
        self.assertIn("date", bar)
        self.assertIn("open", bar)
        self.assertIn("high", bar)
        self.assertIn("low", bar)
        self.assertIn("close", bar)
        self.assertIn("volume", bar)
        self.assertEqual(bar["symbol"], "000001.SZ")

    def test_mock_kline_default_count(self) -> None:
        bars = self.bridge.get_kline("600519.SH")
        self.assertGreaterEqual(len(bars), 50)

    def test_mock_kline_deterministic(self) -> None:
        bars1 = self.bridge.get_kline("000001.SZ")
        bars2 = self.bridge.get_kline("000001.SZ")
        self.assertEqual(len(bars1), len(bars2))
        self.assertEqual(bars1[0]["date"], bars2[0]["date"])
        self.assertEqual(bars1[0]["close"], bars2[0]["close"])

    def test_mock_order_book_structure(self) -> None:
        ob = self.bridge.get_order_book("000001.SZ")
        self.assertIn("symbol", ob)
        self.assertIn("bid_prices", ob)
        self.assertIn("ask_prices", ob)
        self.assertIn("bid_volumes", ob)
        self.assertIn("ask_volumes", ob)
        self.assertEqual(len(ob["bid_prices"]), 5)
        self.assertEqual(len(ob["ask_prices"]), 5)

    def test_mock_trade_tape_structure(self) -> None:
        ticks = self.bridge.get_trade_tape("000001.SZ")
        self.assertIsInstance(ticks, list)
        self.assertGreater(len(ticks), 0)
        tick = ticks[0]
        self.assertIn("symbol", tick)
        self.assertIn("time", tick)
        self.assertIn("price", tick)
        self.assertIn("volume", tick)
        self.assertIn("direction", tick)

    def test_mock_valuation_structure(self) -> None:
        val = self.bridge.get_valuation("000001.SZ")
        self.assertIn("symbol", val)
        self.assertIn("last_price", val)
        self.assertIn("volume", val)
        self.assertIn("pe_ttm", val)
        self.assertEqual(val["symbol"], "000001.SZ")

    def test_mock_place_order(self) -> None:
        result = self.bridge.place_order("000001.SZ", "buy", 10.50, 1000)
        self.assertIn("order_id", result)
        self.assertTrue(result["order_id"].startswith("mock-"))
        self.assertEqual(result["symbol"], "000001.SZ")
        self.assertEqual(result["direction"], "buy")
        self.assertEqual(result["status"], "filled")

    def test_mock_cancel_order(self) -> None:
        self.assertTrue(self.bridge.cancel_order("mock-order-123"))

    def test_mock_positions(self) -> None:
        positions = self.bridge.get_positions()
        self.assertIsInstance(positions, list)
        self.assertGreater(len(positions), 0)
        self.assertIn("symbol", positions[0])
        self.assertIn("volume", positions[0])

    def test_mock_account_info(self) -> None:
        info = self.bridge.get_account_info()
        self.assertIn("account_id", info)
        self.assertIn("total_asset", info)
        self.assertIn("cash", info)
        self.assertEqual(info["account_id"], "MOCK-ACCT-001")


class TestQmtBridgeRealModeRequestFormat(unittest.TestCase):
    """Verify that real-mode methods construct correct HTTP requests."""

    def setUp(self) -> None:
        self.bridge = QmtBridge()

    @patch.object(_qb, "urlopen")
    def test_get_kline_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": [{"date": "2024-01-02", "close": 10.0}], "error": None})
        self.bridge.get_kline("000001.SZ", start="2024-01-01", end="2024-01-31", period="1d")

        call_args = mock_urlopen.call_args
        self.assertIsNotNone(call_args)
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "kline")
        self.assertEqual(body["params"]["symbol"], "000001.SZ")
        self.assertEqual(body["params"]["period"], "1d")
        self.assertEqual(body["params"]["start"], "2024-01-01")
        self.assertEqual(body["params"]["end"], "2024-01-31")
        self.assertIn("id", body)

    @patch.object(_qb, "urlopen")
    def test_get_order_book_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"symbol": "000001.SZ"}, "error": None})
        self.bridge.get_order_book("000001.SZ")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "order_book")
        self.assertEqual(body["params"]["symbol"], "000001.SZ")

    @patch.object(_qb, "urlopen")
    def test_get_trade_tape_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": [], "error": None})
        self.bridge.get_trade_tape("000001.SZ")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "trade_tape")
        self.assertEqual(body["params"]["symbol"], "000001.SZ")

    @patch.object(_qb, "urlopen")
    def test_place_order_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"order_id": "123"}, "error": None})
        self.bridge.place_order("000001.SZ", "buy", 10.50, 1000, order_type="limit")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "place_order")
        self.assertEqual(body["params"]["symbol"], "000001.SZ")
        self.assertEqual(body["params"]["direction"], "buy")
        self.assertEqual(body["params"]["price"], 10.50)
        self.assertEqual(body["params"]["volume"], 1000)
        self.assertEqual(body["params"]["order_type"], "limit")

    @patch.object(_qb, "urlopen")
    def test_place_order_market_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"order_id": "124"}, "error": None})
        self.bridge.place_order("000001.SZ", "sell", 0.0, 500, order_type="market")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["params"]["order_type"], "market")
        self.assertEqual(body["params"]["direction"], "sell")

    @patch.object(_qb, "urlopen")
    def test_get_valuation_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"symbol": "000001.SZ"}, "error": None})
        self.bridge.get_valuation("000001.SZ")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "valuation")
        self.assertEqual(body["params"]["symbol"], "000001.SZ")

    @patch.object(_qb, "urlopen")
    def test_cancel_order_request_format(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": {"cancelled": True}, "error": None})
        self.bridge.cancel_order("ord-456")

        call_args = mock_urlopen.call_args
        req: Any = call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(body["method"], "cancel_order")
        self.assertEqual(body["params"]["order_id"], "ord-456")


class TestQmtBridgeErrorHandling(unittest.TestCase):
    """Error response handling."""

    @patch.object(_qb, "urlopen")
    def test_error_response(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": None, "error": "symbol not found"})
        bridge = QmtBridge()
        with self.assertRaises(ValueError) as ctx:
            bridge.get_kline("INVALID")
        self.assertIn("symbol not found", str(ctx.exception))

    @patch.object(_qb, "urlopen")
    def test_timeout_handling(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError("timed out")
        bridge = QmtBridge(config=QmtBridgeConfig(timeout=1.0))
        with self.assertRaises(ConnectionError) as ctx:
            bridge.get_kline("000001.SZ")
        self.assertIn("timeout", str(ctx.exception).lower())

    @patch.object(_qb, "urlopen")
    def test_invalid_json_response(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.read.return_value = b"not json"
        resp.__enter__.return_value = resp  # context manager support
        mock_urlopen.return_value = resp
        bridge = QmtBridge()
        with self.assertRaises(ValueError) as ctx:
            bridge.get_kline("000001.SZ")
        self.assertIn("invalid json", str(ctx.exception).lower())

    @patch.object(_qb, "urlopen")
    def test_http_error_handling(self, mock_urlopen: MagicMock) -> None:
        from urllib.error import HTTPError

        mock_urlopen.side_effect = HTTPError(
            url="http://127.0.0.1:58609/api/v1/qmt",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        bridge = QmtBridge()
        with self.assertRaises(ConnectionError):
            bridge.get_kline("000001.SZ")

    def test_mock_mode_raises_on_real_request(self) -> None:
        bridge = QmtBridge(use_mock=True)
        with self.assertRaises(RuntimeError) as ctx:
            bridge._request("some_method")
        self.assertIn("mock mode", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()

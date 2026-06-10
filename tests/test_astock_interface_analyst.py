import json
import unittest

from tradingagents.astock import (
    AStockAnalyst,
    AStockInterface,
    AStockResponse,
    build_astock_tools,
    create_astock_analyst_node,
)


class FakeFacade:
    def __init__(self):
        self.calls = []

    def _record(self, name, symbol, **kwargs):
        self.calls.append((name, symbol, kwargs))

    def get_kline(self, symbol, **kwargs):
        self._record("get_kline", symbol, **kwargs)
        return AStockResponse.ok(
            capability="kline",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"bars": [{"date": "2026-06-01", "close": 1.0}]},
            meta={"source_function": "fake.kline"},
        )

    def get_valuation(self, symbol, **kwargs):
        self._record("get_valuation", symbol, **kwargs)
        return AStockResponse.ok(
            capability="valuation",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"pe": 10.5, "pb": 1.2, "market_cap": 1000, "turnover_rate": 2.1},
            meta={"field_sources": {"pe": "akshare.fixture"}},
            notes=("valuation-supplement:tencent",),
        )

    def get_stock_news(self, symbol, **kwargs):
        self._record("get_stock_news", symbol, **kwargs)
        return AStockResponse.ok(
            capability="stock_news",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"items": [{"title": "news-1"}]},
        )

    def get_flash_news(self, symbol, **kwargs):
        self._record("get_flash_news", symbol, **kwargs)
        return AStockResponse.ok(
            capability="flash_news",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="tencent",
            data={"items": [{"title": "flash-1"}]},
        )

    def get_global_news(self, symbol, **kwargs):
        self._record("get_global_news", symbol, **kwargs)
        return AStockResponse.ok(
            capability="global_news",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"items": [{"title": "global-1"}]},
        )

    def get_fundamentals(self, symbol, **kwargs):
        self._record("get_fundamentals", symbol, **kwargs)
        return AStockResponse.ok(
            capability="fundamentals",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"items": [{"period": "2026-03-31", "revenue": 123}]},
        )

    def get_quarterly_financials(self, symbol, **kwargs):
        self._record("get_quarterly_financials", symbol, **kwargs)
        return AStockResponse.ok(
            capability="quarterly_financials",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="akshare",
            data={"items": [{"period": "2026-03-31", "net_profit": 456}]},
        )

    def get_f10(self, symbol, **kwargs):
        self._record("get_f10", symbol, **kwargs)
        return AStockResponse.ok(
            capability="f10",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="mootdx",
            data={"items": [{"name": "basic"}]},
        )


class AStockInterfaceAndAnalystTests(unittest.TestCase):
    def setUp(self):
        self.facade = FakeFacade()
        self.interface = AStockInterface(facade=self.facade)

    def test_interface_collects_structured_bundles(self):
        payload = self.interface.to_payload("600519", curr_date="2026-06-10")

        self.assertEqual(payload["symbol"], "600519.SH")
        self.assertEqual(payload["status"], "ok")
        self.assertIn("market", payload["sections"])
        self.assertIn("news", payload["sections"])
        self.assertIn("fundamentals", payload["sections"])
        self.assertIn("kline=ok[akshare]", payload["sections"]["market"]["summary"])
        self.assertEqual(payload["sections"]["market"]["responses"]["kline"]["data"]["bars"][0]["date"], "2026-06-01")
        self.assertEqual(payload["sections"]["fundamentals"]["responses"]["f10"]["source"], "mootdx")

    def test_tools_return_json_and_keep_structure(self):
        tools = build_astock_tools(self.interface)
        market_tool = next(tool for tool in tools if tool.name == "astock_market_snapshot")
        news_tool = next(tool for tool in tools if tool.name == "astock_news_snapshot")

        market_payload = json.loads(market_tool.invoke({"symbol": "600519", "start_date": "2026-06-01"}))
        news_payload = json.loads(news_tool.invoke({"symbol": "600519", "limit": 3}))

        self.assertEqual(market_payload["symbol"], "600519.SH")
        self.assertEqual(news_payload["sections"]["news"]["responses"]["flash_news"]["source"], "tencent")
        self.assertNotIn("provider", market_tool.invoke({"symbol": "600519"}).lower())
        self.assertEqual([name for name, *_ in self.facade.calls][:2], ["get_kline", "get_valuation"])

    def test_minimal_analyst_returns_state_update(self):
        analyst = AStockAnalyst(interface=self.interface)
        result = analyst.analyze_state({"company_of_interest": "600519", "trade_date": "2026-06-10"})

        self.assertIn("astock_analysis", result)
        self.assertIn("astock_sections", result)
        self.assertEqual(result["astock_analysis"]["symbol"], "600519.SH")
        self.assertEqual(result["astock_analysis"]["status_breakdown"]["market"], "ok")
        self.assertEqual(result["astock_analysis"]["status"], "ok")
        self.assertEqual(result["astock_summary"], result["astock_analysis"]["summary"])

    def test_node_adapter_accepts_common_state_keys(self):
        node = create_astock_analyst_node(self.interface)
        result = node({"ticker": "000001.SZ", "curr_date": "2026-06-10"})

        self.assertEqual(result["astock_analysis"]["symbol"], "000001.SZ")
        self.assertIn("news", result["astock_sections"])


if __name__ == "__main__":
    unittest.main()

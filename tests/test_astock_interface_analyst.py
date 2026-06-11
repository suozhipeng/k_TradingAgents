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

    def get_announcement_summary(self, symbol, **kwargs):
        self._record("get_announcement_summary", symbol, **kwargs)
        return AStockResponse.ok(
            capability="announcement_summary",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="cninfo",
            data={"items": [{"title": "announcement-1"}]},
        )

    def get_announcement_full(self, symbol, **kwargs):
        self._record("get_announcement_full", symbol, **kwargs)
        return AStockResponse.ok(
            capability="announcement_full",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="cninfo",
            data={"items": [{"title": "announcement-1", "pdf_url": "https://example.com/a.pdf"}]},
        )

    def get_research_list(self, symbol, **kwargs):
        self._record("get_research_list", symbol, **kwargs)
        return AStockResponse.ok(
            capability="research_list",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="iwencai",
            data={"items": [{"title": "research-1"}]},
        )

    def download_research_pdf(self, symbol, **kwargs):
        self._record("download_research_pdf", symbol, **kwargs)
        return AStockResponse.ok(
            capability="download_research_pdf",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="iwencai",
            data={"title": "research-1", "pdf_url": "https://example.com/r.pdf"},
        )

    def get_institution_expectation(self, symbol, **kwargs):
        self._record("get_institution_expectation", symbol, **kwargs)
        return AStockResponse.ok(
            capability="institution_expectation",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="iwencai",
            data={"items": [{"title": "expectation-1"}]},
        )

    def search_research(self, symbol, **kwargs):
        self._record("search_research", symbol, **kwargs)
        return AStockResponse.ok(
            capability="search_research",
            symbol=symbol,
            raw_symbol=kwargs.get("raw_symbol", symbol),
            source="iwencai",
            data={"items": [{"title": "search-1"}]},
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
        self.assertIn("announcements", payload["sections"])
        self.assertIn("research", payload["sections"])
        self.assertIn("kline=ok[akshare]", payload["sections"]["market"]["summary"])
        self.assertEqual(payload["sections"]["market"]["responses"]["kline"]["data"]["bars"][0]["date"], "2026-06-01")
        self.assertEqual(payload["sections"]["fundamentals"]["responses"]["f10"]["source"], "mootdx")
        self.assertEqual(payload["sections"]["announcements"]["responses"]["announcement_summary"]["source"], "cninfo")
        self.assertEqual(payload["sections"]["research"]["responses"]["download_research_pdf"]["data"]["pdf_url"], "https://example.com/r.pdf")

    def test_tools_return_json_and_keep_structure(self):
        tools = build_astock_tools(self.interface)
        market_tool = next(tool for tool in tools if tool.name == "astock_market_snapshot")
        news_tool = next(tool for tool in tools if tool.name == "astock_news_snapshot")
        research_tool = next(tool for tool in tools if tool.name == "astock_research_snapshot")
        announcements_tool = next(tool for tool in tools if tool.name == "astock_announcements_snapshot")

        market_payload = json.loads(market_tool.invoke({"symbol": "600519", "start_date": "2026-06-01"}))
        news_payload = json.loads(news_tool.invoke({"symbol": "600519", "limit": 3}))
        research_payload = json.loads(research_tool.invoke({"symbol": "600519", "query": "贵州茅台"}))
        announcements_payload = json.loads(announcements_tool.invoke({"symbol": "600519", "title": "定期报告"}))

        self.assertEqual(market_payload["symbol"], "600519.SH")
        self.assertEqual(news_payload["sections"]["news"]["responses"]["flash_news"]["source"], "tencent")
        self.assertEqual(research_payload["sections"]["research"]["responses"]["download_research_pdf"]["source"], "iwencai")
        self.assertEqual(announcements_payload["sections"]["announcements"]["responses"]["announcement_full"]["source"], "cninfo")
        self.assertNotIn("provider", market_tool.invoke({"symbol": "600519"}).lower())
        self.assertEqual([name for name, *_ in self.facade.calls][:4], ["get_kline", "get_valuation", "get_stock_news", "get_flash_news"])

    def test_minimal_analyst_returns_state_update(self):
        analyst = AStockAnalyst(interface=self.interface)
        result = analyst.analyze_state({"company_of_interest": "600519", "trade_date": "2026-06-10"})

        self.assertIn("astock_analysis", result)
        self.assertIn("astock_sections", result)
        self.assertEqual(result["astock_analysis"]["symbol"], "600519.SH")
        self.assertEqual(result["astock_analysis"]["status_breakdown"]["market"], "ok")
        self.assertEqual(result["astock_analysis"]["status_breakdown"]["announcements"], "ok")
        self.assertEqual(result["astock_analysis"]["status_breakdown"]["research"], "ok")
        self.assertEqual(result["astock_analysis"]["status"], "ok")
        self.assertEqual(result["astock_summary"], result["astock_analysis"]["summary"])

    def test_node_adapter_accepts_common_state_keys(self):
        node = create_astock_analyst_node(self.interface)
        result = node({"ticker": "000001.SZ", "curr_date": "2026-06-10"})

        self.assertEqual(result["astock_analysis"]["symbol"], "000001.SZ")
        self.assertIn("news", result["astock_sections"])

    def test_research_and_announcements_degrade_when_sources_are_empty(self):
        class EmptyResearchFacade(FakeFacade):
            def get_research_list(self, symbol, **kwargs):
                self._record("get_research_list", symbol, **kwargs)
                return AStockResponse.empty_result(
                    capability="research_list",
                    symbol=symbol,
                    raw_symbol=kwargs.get("raw_symbol", symbol),
                    error_code="NO_DATA_AVAILABLE",
                    error_message="missing cookie or no data",
                    source="iwencai",
                )

            def download_research_pdf(self, symbol, **kwargs):
                self._record("download_research_pdf", symbol, **kwargs)
                return AStockResponse.empty_result(
                    capability="download_research_pdf",
                    symbol=symbol,
                    raw_symbol=kwargs.get("raw_symbol", symbol),
                    error_code="NO_DATA_AVAILABLE",
                    error_message="missing cookie or no data",
                    source="iwencai",
                )

            def get_institution_expectation(self, symbol, **kwargs):
                self._record("get_institution_expectation", symbol, **kwargs)
                return AStockResponse.empty_result(
                    capability="institution_expectation",
                    symbol=symbol,
                    raw_symbol=kwargs.get("raw_symbol", symbol),
                    error_code="NO_DATA_AVAILABLE",
                    error_message="missing cookie or no data",
                    source="iwencai",
                )

            def search_research(self, symbol, **kwargs):
                self._record("search_research", symbol, **kwargs)
                return AStockResponse.empty_result(
                    capability="search_research",
                    symbol=symbol,
                    raw_symbol=kwargs.get("raw_symbol", symbol),
                    error_code="NO_DATA_AVAILABLE",
                    error_message="missing cookie or no data",
                    source="iwencai",
                )

        analyst = AStockAnalyst(interface=AStockInterface(facade=EmptyResearchFacade()))
        result = analyst.analyze_state({"symbol": "600519"})

        self.assertIn("research", result["astock_sections"])
        self.assertIn("announcements", result["astock_sections"])
        self.assertIn(result["astock_analysis"]["status_breakdown"]["research"], {"empty", "partial"})
        self.assertIn(result["astock_analysis"]["status_breakdown"]["announcements"], {"ok", "partial"})
        self.assertIn("astock_summary", result)

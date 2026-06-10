import unittest

from tradingagents.astock.data_sources import (
    AStockCachePolicy,
    AStockDataError,
    AStockDataFacade,
    AStockDataRouter,
    AStockNoDataError,
    InMemoryAStockCache,
    AStockResponse,
    AStockSourceUnavailableError,
    CAPABILITY_TO_METHOD,
    DEFAULT_ROUTE_POLICY,
    normalize_astock_symbol,
)


class FakeAdapter:
    def __init__(self, name, behaviors):
        self.name = name
        self.behaviors = behaviors
        self.calls = []

    def get_kline(self, request):
        self.calls.append(("get_kline", request.symbol, request.start_date, request.end_date, request.interval))
        return self.behaviors["get_kline"](request)

    def __getattr__(self, method_name):
        if method_name not in self.behaviors:
            raise AttributeError(method_name)

        def _method(request):
            self.calls.append((method_name, request.capability, request.symbol))
            behavior = self.behaviors[method_name]
            return behavior(request)

        return _method


class FailingCache:
    def get(self, *_args, **_kwargs):
        raise RuntimeError("cache unavailable")

    def set(self, *_args, **_kwargs):
        raise RuntimeError("cache unavailable")

    def get_history_range(self, *_args, **_kwargs):
        raise RuntimeError("cache unavailable")

    def set_history_range(self, *_args, **_kwargs):
        raise RuntimeError("cache unavailable")


class AStockDataSourceTests(unittest.TestCase):
    def test_normalize_astock_symbol_maps_exchange_suffix(self):
        self.assertEqual(normalize_astock_symbol("600519"), "600519.SH")
        self.assertEqual(normalize_astock_symbol("000001"), "000001.SZ")
        self.assertEqual(normalize_astock_symbol("830899"), "830899.BJ")
        self.assertEqual(normalize_astock_symbol("600519.sh"), "600519.SH")

    def test_router_falls_back_and_returns_stable_schema(self):
        primary = FakeAdapter(
            "akshare",
            {
                "get_kline": lambda request: (_ for _ in ()).throw(
                    AStockNoDataError(request.symbol, request.symbol, "empty")
                )
            },
        )
        fallback = FakeAdapter(
            "mootdx",
            {
                "get_kline": lambda request: {
                    "bars": [
                        {"date": "2026-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
                    ],
                    "meta": {"source_payload": True},
                }
            },
        )
        router = AStockDataRouter(
            adapters={"akshare": primary, "mootdx": fallback},
            cache=InMemoryAStockCache(),
            route_policy={"kline": ["akshare", "mootdx"]},
        )

        response = router.get_kline("600519", start_date="2026-01-01", end_date="2026-01-31", interval="1d")

        self.assertIsInstance(response, AStockResponse)
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.source, "mootdx")
        self.assertEqual(response.symbol, "600519.SH")
        self.assertEqual(response.sources_tried, ("akshare", "mootdx"))
        self.assertEqual(response.data["bars"][0]["date"], "2026-01-02")
        self.assertNotIn("source_payload", response.data)
        payload = response.to_dict()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["capability"], "kline")
        self.assertEqual(payload["source"], "mootdx")
        self.assertIn("meta", payload)

    def test_router_turns_all_no_data_into_empty_semantics(self):
        def no_data(request):
            raise AStockNoDataError(request.symbol, request.symbol, "no rows")

        adapter = FakeAdapter("akshare", {"get_kline": no_data})
        router = AStockDataRouter(
            adapters={"akshare": adapter},
            cache=InMemoryAStockCache(),
            route_policy={"kline": ["akshare"]},
        )

        response = router.get_kline("FAKE", start_date="2026-01-01", end_date="2026-01-31")

        self.assertTrue(response.empty)
        self.assertEqual(response.status, "empty")
        self.assertEqual(response.error_code, "NO_DATA_AVAILABLE")
        self.assertIn("NO_DATA_AVAILABLE", response.error_message)
        self.assertIsNone(response.data)

    def test_history_cache_dedupes_and_cache_failures_do_not_poison_flow(self):
        adapter = FakeAdapter(
            "akshare",
            {
                "get_kline": lambda request: {
                    "bars": [
                        {"date": "2026-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
                        {"date": "2026-01-03", "open": 1.5, "high": 2.5, "low": 1, "close": 2.0, "volume": 20},
                    ],
                    "meta": {"rows": 2},
                }
            },
        )
        router = AStockDataRouter(
            adapters={"akshare": adapter},
            cache=InMemoryAStockCache(),
            route_policy={"kline": ["akshare"]},
        )

        first = router.get_kline("600519", start_date="2026-01-01", end_date="2026-01-31")
        second = router.get_kline("600519", start_date="2026-01-01", end_date="2026-01-31")

        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(first.data, second.data)
        self.assertTrue(second.cached)
        self.assertEqual(first.data["bars"][0]["date"], "2026-01-02")

        noisy_router = AStockDataRouter(
            adapters={"akshare": adapter},
            cache=FailingCache(),
            route_policy={"kline": ["akshare"]},
        )
        noisy = noisy_router.get_kline("000001", start_date="2026-01-01", end_date="2026-01-31")
        self.assertEqual(noisy.status, "ok")
        self.assertEqual(noisy.symbol, "000001.SZ")

    def test_facade_exposes_unified_entry_points(self):
        facade = AStockDataFacade(
            router=AStockDataRouter(
                adapters={},
                cache=InMemoryAStockCache(),
                route_policy={"kline": []},
            )
        )
        self.assertTrue(hasattr(facade, "get_kline"))
        self.assertTrue(hasattr(facade, "get_announcement_full"))
        self.assertTrue(hasattr(facade, "query"))

    def test_all_five_layer_interface_mappings_are_callable(self):
        expected = {
            "kline": "get_kline",
            "order_book": "get_order_book",
            "trade_tape": "get_trade_tape",
            "pe_pb": "get_valuation",
            "market_cap": "get_valuation",
            "turnover_rate": "get_valuation",
            "research_list": "get_research_list",
            "download_research_pdf": "download_research_pdf",
            "institution_expectation": "get_institution_expectation",
            "search_research": "search_research",
            "stock_news": "get_stock_news",
            "flash_news": "get_flash_news",
            "global_news": "get_global_news",
            "quarterly_financials": "get_quarterly_financials",
            "f10": "get_f10",
            "fundamentals": "get_fundamentals",
            "announcement_full": "get_announcement_full",
            "announcement_summary": "get_announcement_summary",
        }
        for capability, method_name in expected.items():
            self.assertEqual(CAPABILITY_TO_METHOD[capability], method_name)
            self.assertIn(capability, DEFAULT_ROUTE_POLICY)
        for method_name in (
            "get_pe_pb",
            "get_market_cap",
            "get_turnover_rate",
            "get_quarterly_financials",
            "get_announcement_summary",
        ):
            self.assertTrue(hasattr(AStockDataFacade, method_name))

    def test_metric_interfaces_route_to_valuation_without_vendor_leakage(self):
        adapter = FakeAdapter(
            "akshare",
            {
                "get_valuation": lambda request: {
                    "pe": "10.5",
                    "pb": "1.2",
                    "market_cap": "100000",
                    "turnover_rate": "2.1",
                    "meta": {"field_sources": {"pe": "akshare.fixture"}},
                    "notes": ["valuation-supplement:tencent"],
                    "raw_payload": {"vendor": "akshare"},
                }
            },
        )
        router = AStockDataRouter(adapters={"akshare": adapter}, route_policy={"pe_pb": ["akshare"]})

        response = router.get_pe_pb("600519")

        self.assertEqual(response.status, "ok")
        self.assertEqual(response.capability, "pe_pb")
        self.assertEqual(response.data["pe"], 10.5)
        self.assertEqual(response.data["pb"], 1.2)
        self.assertEqual(response.meta["field_sources"]["pe"], "akshare.fixture")
        self.assertIn("valuation-supplement:tencent", response.notes)
        self.assertNotIn("raw_payload", response.data)
        self.assertEqual(adapter.calls[0][0], "get_valuation")

    def test_snapshot_and_summary_cache_have_separate_ttl_semantics(self):
        now = [1000.0]
        cache = InMemoryAStockCache(
            policy=AStockCachePolicy(history_ttl_seconds=None, snapshot_ttl_seconds=1, summary_ttl_seconds=10),
            clock=lambda: now[0],
        )
        adapter = FakeAdapter(
            "akshare",
            {
                "get_valuation": lambda request: {"pe": 10 + len(adapter.calls)},
                "get_stock_news": lambda request: {"items": [{"title": "n%d" % len(adapter.calls)}]},
            },
        )
        router = AStockDataRouter(
            adapters={"akshare": adapter},
            cache=cache,
            route_policy={"pe_pb": ["akshare"], "stock_news": ["akshare"]},
        )

        first_snapshot = router.get_pe_pb("600519")
        first_summary = router.get_stock_news("600519")
        now[0] += 2
        second_snapshot = router.get_pe_pb("600519")
        second_summary = router.get_stock_news("600519")

        self.assertFalse(first_snapshot.cached)
        self.assertFalse(second_snapshot.cached)
        self.assertTrue(second_summary.cached)
        self.assertEqual(first_summary.data, second_summary.data)

    def test_unified_error_semantics_include_source_and_capability(self):
        adapter = FakeAdapter(
            "akshare",
            {
                "get_stock_news": lambda request: (_ for _ in ()).throw(
                    AStockSourceUnavailableError("akshare", "network down", capability=request.capability)
                )
            },
        )
        router = AStockDataRouter(adapters={"akshare": adapter}, route_policy={"stock_news": ["akshare"]})

        response = router.get_stock_news("600519")

        self.assertEqual(response.status, "error")
        self.assertEqual(response.error_code, "SOURCE_UNAVAILABLE")
        self.assertEqual(response.source, "akshare")
        self.assertIn("network down", response.error_message)
        self.assertEqual(response.request["capability"], "stock_news")

    def test_blueprint_payload_exports_data_entrypoint_boundary(self):
        from tradingagents.astock.blueprint import build_blueprint_payload

        payload = build_blueprint_payload()

        self.assertIn("data_entrypoint", payload)
        self.assertEqual(payload["data_entrypoint"]["class"], "AStockDataFacade")
        self.assertIn("TODO", " ".join(payload["data_entrypoint"]["todo"]))


if __name__ == "__main__":
    unittest.main()

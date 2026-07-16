import json
import time
from pathlib import Path

import pandas as pd
import pytest

from tradingagents.astock.data_sources.adapters import (
    AkshareAdapter,
    CninfoAdapter,
    IwencaiAdapter,
    MootdxAdapter,
    TencentFinanceAdapter,
)
from tradingagents.astock.data_sources.schema import AStockRequest
from tradingagents.astock.data_sources.errors import AStockSourceUnavailableError
from tradingagents.astock.data_sources.router import AStockDataFacade, DEFAULT_ROUTE_POLICY


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "astock_providers"


def load_json(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_text(name):
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, *, text=None, json_data=None, status_code=200, encoding="utf-8"):
        self._text = text
        self._json_data = json_data
        self.status_code = status_code
        self.encoding = encoding

    @property
    def text(self):
        return self._text

    @property
    def content(self):
        return (self._text or "").encode(self.encoding, errors="ignore")

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        handler = self.routes[url]
        return handler(url, kwargs)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        handler = self.routes[url]
        return handler(url, kwargs)


class FakeAkshareModule:
    def stock_zh_a_daily(self, **kwargs):
        return pd.DataFrame(load_json("akshare_kline.json"))

    def stock_zh_a_hist(self, **kwargs):
        return pd.DataFrame(load_json("akshare_kline.json"))

    def stock_zh_a_spot_em(self):
        return pd.DataFrame(load_json("akshare_spot.json"))

    def stock_news_em(self, symbol):
        assert symbol == "600519"
        return pd.DataFrame(load_json("akshare_news.json"))

    def stock_research_report_em(self, symbol):
        assert symbol == "600519"
        return pd.DataFrame(load_json("akshare_research.json"))

    def stock_financial_analysis_indicator(self, symbol, start_year="1900"):
        assert symbol == "600519"
        return pd.DataFrame(load_json("akshare_financials.json"))

    def stock_profit_forecast_em(self, symbol=""):
        return pd.DataFrame(load_json("iwencai_expectation.json"))


class PartialAkshareModule(FakeAkshareModule):
    def stock_zh_a_spot_em(self):
        row = dict(load_json("akshare_spot.json")[0])
        row["市盈率-动态"] = None
        row["市净率"] = None
        row["总市值"] = None
        row["换手率"] = None
        return pd.DataFrame([row])


class FakeWencaiModule:
    def get(self, **kwargs):
        query = kwargs["query"]
        if "机构预期" in query:
            return pd.DataFrame(load_json("iwencai_expectation.json"))
        return pd.DataFrame(load_json("iwencai_search.json"))


class FakeMootdxClient:
    def bars(self, symbol="000001", frequency=9, start=0, offset=800, **kwargs):
        return pd.DataFrame(load_json("mootdx_bars.json"))

    def quotes(self, symbol=None, **kwargs):
        return pd.DataFrame(load_json("mootdx_quotes.json"))

    def transactions(self, symbol="", start=0, offset=800, date="20170209", **kwargs):
        return pd.DataFrame(load_json("mootdx_transactions.json"))

    def finance(self, symbol="000001", **kwargs):
        return load_json("mootdx_finance.json")


@pytest.mark.unit
class TestProviderFixtures:
    def test_kline_policy_prefers_the_bounded_mootdx_path(self):
        assert DEFAULT_ROUTE_POLICY["kline"][0] == "mootdx"

    def test_data_facade_fetch_uses_the_capability_router(self):
        class Router:
            def query(self, capability, symbol, **kwargs):
                return capability, symbol, kwargs

        assert AStockDataFacade(router=Router()).fetch(
            "kline", "600519.SH", start_date="2026-07-01", interval="1d",
        ) == ("kline", "600519.SH", {"start_date": "2026-07-01", "interval": "1d"})

    def test_akshare_adapter_enforces_hard_provider_deadline(self, monkeypatch):
        class SlowAkshareModule:
            def stock_zh_a_hist(self, **kwargs):
                time.sleep(1)

        monkeypatch.setattr(
            "tradingagents.astock.data_sources.adapters.providers.akshare._random_sleep",
            lambda *_args: None,
        )
        adapter = AkshareAdapter(module=SlowAkshareModule(), timeout=0.1)
        request = AStockRequest(
            capability="kline", raw_symbol="600519", symbol="600519.SH",
        )

        started = time.monotonic()
        with pytest.raises(AStockSourceUnavailableError, match="exceeded"):
            adapter.get_kline(request)
        assert time.monotonic() - started < 0.5

    def test_akshare_adapter_parses_market_research_news_and_financials(self):
        adapter = AkshareAdapter(module=FakeAkshareModule())
        kline_request = AStockRequest(capability="kline", raw_symbol="600519", symbol="600519.SH", start_date="2026-06-01", end_date="2026-06-10")
        valuation_request = AStockRequest(capability="pe_pb", raw_symbol="600519", symbol="600519.SH")
        news_request = AStockRequest(capability="stock_news", raw_symbol="600519", symbol="600519.SH")
        research_request = AStockRequest(capability="research_list", raw_symbol="600519", symbol="600519.SH")
        financial_request = AStockRequest(capability="quarterly_financials", raw_symbol="600519", symbol="600519.SH")

        kline = adapter.get_kline(kline_request)
        valuation = adapter.get_valuation(valuation_request)
        news = adapter.get_stock_news(news_request)
        research = adapter.get_research_list(research_request)
        financials = adapter.get_quarterly_financials(financial_request)

        assert kline["bars"][0]["date"] == "2026-06-09"
        assert kline["bars"][1]["close"] == 1275.88
        assert valuation["pe"] == 19.38
        assert valuation["pb"] == 14.64
        assert valuation["market_cap"] == 15949.54
        assert valuation["turnover_rate"] == 0.31
        assert news["items"][0]["title"] == "贵州茅台发布年度分红公告"
        assert research["items"][0]["pdf_url"].startswith("https://pdf.dfcfw.com/")
        assert financials["items"][0]["period"] == "2026-03-31"

    def test_akshare_valuation_supplement_is_explicit_and_tracked(self):
        class FakeTencentAdapter:
            def get_valuation(self, request):
                return {
                    "pe": 20.1,
                    "pb": 10.2,
                    "market_cap": 123.4,
                    "turnover_rate": 0.5,
                    "timestamp": "2026-06-10 16:14:01",
                }

        request = AStockRequest(capability="pe_pb", raw_symbol="600519", symbol="600519.SH")
        pure = AkshareAdapter(module=PartialAkshareModule())
        pure_payload = pure.get_valuation(request)
        assert pure_payload["pe"] is None
        assert pure_payload["meta"]["tencent_supplement_enabled"] is False
        assert pure_payload["meta"]["field_sources"]["price"] == "akshare.stock_zh_a_spot_em"

        supplemented = AkshareAdapter(
            module=PartialAkshareModule(),
            allow_tencent_valuation_supplement=True,
            tencent_adapter=FakeTencentAdapter(),
        )
        supplemented_payload = supplemented.get_valuation(request)
        assert supplemented_payload["pe"] == 20.1
        assert supplemented_payload["meta"]["tencent_supplement_enabled"] is True
        assert supplemented_payload["meta"]["provider"] == "akshare+tencent"
        assert supplemented_payload["meta"]["field_sources"]["pe"] == "tencent.qt.gtimg.cn"
        assert "valuation-supplement:tencent" in supplemented_payload["notes"]

    def test_tencent_adapter_parses_snapshot_order_book_trade_tape_and_turnover(self):
        session = FakeSession(
            {
                "https://qt.gtimg.cn/q=sh600519": lambda _url, _kwargs: FakeResponse(text=load_text("tencent_snapshot.txt"), encoding="gbk"),
                "https://stock.gtimg.cn/data/index.php?appn=detail&action=data&c=sh600519&p=1": lambda _url, _kwargs: FakeResponse(text=load_text("tencent_trades.txt"), encoding="gbk"),
            }
        )
        adapter = TencentFinanceAdapter(session=session)
        request = AStockRequest(capability="order_book", raw_symbol="600519", symbol="600519.SH")
        trade_request = AStockRequest(capability="trade_tape", raw_symbol="600519", symbol="600519.SH")
        valuation_request = AStockRequest(capability="turnover_rate", raw_symbol="600519", symbol="600519.SH")

        order_book = adapter.get_order_book(request)
        trades = adapter.get_trade_tape(trade_request)
        valuation = adapter.get_valuation(valuation_request)

        assert order_book["name"] == "贵州茅台"
        assert order_book["price"] == 1275.88
        assert order_book["bids"][0]["price"] == 1275.88
        assert order_book["asks"][0]["volume"] == 9
        assert trades["items"][0]["side"] == "neutral"
        assert trades["items"][2]["side"] == "buy"
        assert valuation["turnover_rate"] == 0.31
        assert valuation["market_cap"] == 15949.54

    def test_cninfo_adapter_parses_summary_and_full_detail(self):
        session = FakeSession(
            {
                "https://www.cninfo.com.cn/new/data/sse_stock.json": lambda _url, _kwargs: FakeResponse(json_data=load_json("cninfo_stock_list.json")),
                "https://www.cninfo.com.cn/new/hisAnnouncement/query": lambda _url, _kwargs: FakeResponse(json_data=load_json("cninfo_announcements.json")),
            }
        )
        adapter = CninfoAdapter(session=session)
        summary_request = AStockRequest(capability="announcement_summary", raw_symbol="600519", symbol="600519.SH", limit=2)
        full_request = AStockRequest(capability="announcement_full", raw_symbol="600519", symbol="600519.SH", extras={"announcement_id": "1225347653"})

        summary = adapter.get_announcement_summary(summary_request)
        full = adapter.get_announcement_full(full_request)

        assert summary["count"] == 2
        assert summary["items"][0]["announcement_id"] == "1225347653"
        assert summary["items"][0]["pdf_url"].startswith("https://static.cninfo.com.cn/")
        assert full["announcement_id"] == "1225347653"
        assert full["download_url"].endswith("1225347653.PDF")

    def test_mootdx_adapter_parses_kline_quotes_trades_and_f10(self):
        adapter = MootdxAdapter(client=FakeMootdxClient())
        request = AStockRequest(capability="kline", raw_symbol="600519", symbol="600519.SH")
        order_request = AStockRequest(capability="order_book", raw_symbol="600519", symbol="600519.SH")
        trade_request = AStockRequest(capability="trade_tape", raw_symbol="600519", symbol="600519.SH")
        f10_request = AStockRequest(capability="f10", raw_symbol="600519", symbol="600519.SH")

        kline = adapter.get_kline(request)
        order_book = adapter.get_order_book(order_request)
        trades = adapter.get_trade_tape(trade_request)
        f10 = adapter.get_f10(f10_request)

        assert kline["bars"][1]["close"] == 1275.88
        assert order_book["bids"][0]["price"] == 1275.88
        assert trades["items"][0]["time"] == "09:33:31"
        assert f10["code"] == "600519"
        assert f10["industry"] == "酿酒行业"

    def test_mootdx_kline_honours_incremental_date_window(self):
        adapter = MootdxAdapter(client=FakeMootdxClient())
        request = AStockRequest(
            capability="kline", raw_symbol="600519", symbol="600519.SH",
            start_date="2026-06-10", end_date="2026-06-10",
        )

        kline = adapter.get_kline(request)

        assert [str(bar["date"])[:10] for bar in kline["bars"]] == ["2026-06-10"]

    def test_iwencai_adapter_parses_search_and_expectation(self):
        adapter = IwencaiAdapter(wencai_module=FakeWencaiModule(), cookie="test-cookie")
        search_request = AStockRequest(capability="search_research", raw_symbol="白酒龙头 分红", symbol="600519.SH", query="白酒龙头 分红")
        expectation_request = AStockRequest(capability="institution_expectation", raw_symbol="600519", symbol="600519.SH", query="贵州茅台 机构预期")

        search = adapter.search_research(search_request)
        expectation = adapter.get_institution_expectation(expectation_request)

        assert search["count"] == 2
        assert search["items"][0]["symbol"] == "600519.SH"
        assert expectation["items"][0]["institution_count"] == 38
        assert expectation["items"][0]["consensus_rating"] == "买入"

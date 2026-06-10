import json
import os

import pytest

from tradingagents.astock.data_sources import (
    AStockDataFacade,
    AkshareAdapter,
    CninfoAdapter,
    IwencaiAdapter,
    MootdxAdapter,
    TencentFinanceAdapter,
)


RUN_LIVE = os.getenv("ASTOCK_RUN_LIVE_TESTS") == "1"
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not RUN_LIVE, reason="set ASTOCK_RUN_LIVE_TESTS=1 to enable live provider checks")]


def _emit(label, response):
    data = response.data or {}
    if isinstance(data, dict):
        if "items" in data and isinstance(data["items"], list):
            record_count = len(data["items"])
            fields = sorted(data["items"][0].keys()) if data["items"] else []
        elif "bars" in data and isinstance(data["bars"], list):
            record_count = len(data["bars"])
            fields = sorted(data["bars"][0].keys()) if data["bars"] else []
        else:
            record_count = 1 if data else 0
            fields = sorted(data.keys())
    else:
        record_count = 0
        fields = []
    meta = response.meta or {}
    print(json.dumps({
        "label": label,
        "source": response.source,
        "status": response.status,
        "record_count": record_count,
        "fields": fields,
        "provider": meta.get("provider"),
        "field_sources": meta.get("field_sources", {}),
        "notes": list(response.notes),
    }, ensure_ascii=False))


@pytest.fixture(scope="module")
def akshare_facade():
    return AStockDataFacade(
        adapters={
            "akshare": AkshareAdapter(timeout=10, allow_tencent_valuation_supplement=True),
        }
    )


@pytest.fixture(scope="module")
def tencent_facade():
    return AStockDataFacade(adapters={"tencent": TencentFinanceAdapter(timeout=10, retries=1)})


@pytest.fixture(scope="module")
def cninfo_facade():
    return AStockDataFacade(adapters={"cninfo": CninfoAdapter(timeout=10)})


@pytest.fixture(scope="module")
def mootdx_facade():
    return AStockDataFacade(adapters={"mootdx": MootdxAdapter(timeout=5)})


@pytest.fixture(scope="module")
def iwencai_facade():
    return AStockDataFacade(adapters={"iwencai": IwencaiAdapter(retry=1, sleep=0.1)})


@pytest.mark.parametrize("symbol", ["600519.SH", "000001.SZ"])
def test_live_akshare_core_capabilities(akshare_facade, symbol):
    kline = akshare_facade.get_kline(symbol, source="akshare", start_date="20250101", end_date="20250630")
    valuation = akshare_facade.get_pe_pb(symbol, source="akshare")
    financials = akshare_facade.get_quarterly_financials(symbol, source="akshare")
    _emit(f"akshare-kline-{symbol}", kline)
    _emit(f"akshare-valuation-{symbol}", valuation)
    _emit(f"akshare-financials-{symbol}", financials)
    assert kline.status == "ok"
    assert valuation.status == "ok"
    assert financials.status in {"ok", "empty"}


def test_live_akshare_news_and_research(akshare_facade):
    news = akshare_facade.get_stock_news("600519.SH", source="akshare")
    research = akshare_facade.get_research_list("600519.SH", source="akshare")
    _emit("akshare-news-600519.SH", news)
    _emit("akshare-research-600519.SH", research)
    assert news.status in {"ok", "empty"}
    assert research.status in {"ok", "empty"}


@pytest.mark.parametrize("symbol", ["600519.SH", "000001.SZ"])
def test_live_tencent_snapshot_and_trades(tencent_facade, symbol):
    order_book = tencent_facade.get_order_book(symbol, source="tencent")
    trade_tape = tencent_facade.get_trade_tape(symbol, source="tencent")
    turnover = tencent_facade.get_turnover_rate(symbol, source="tencent")
    _emit(f"tencent-order-book-{symbol}", order_book)
    _emit(f"tencent-trade-tape-{symbol}", trade_tape)
    _emit(f"tencent-turnover-{symbol}", turnover)
    assert order_book.status == "ok"
    assert trade_tape.status == "ok"
    assert turnover.status == "ok"


def test_live_cninfo_announcements(cninfo_facade):
    summary = cninfo_facade.get_announcement_summary("600519.SH", source="cninfo", limit=5)
    _emit("cninfo-summary-600519.SH", summary)
    assert summary.status == "ok"
    announcement_id = (summary.data or {}).get("items", [{}])[0].get("announcement_id")
    full = cninfo_facade.get_announcement_full("600519.SH", source="cninfo", extras={"announcement_id": announcement_id})
    _emit("cninfo-full-600519.SH", full)
    assert full.status == "ok"


def test_live_mootdx_if_available(mootdx_facade):
    pytest.importorskip("mootdx")
    kline = mootdx_facade.get_kline("600519.SH", source="mootdx")
    order_book = mootdx_facade.get_order_book("600519.SH", source="mootdx")
    trade_tape = mootdx_facade.get_trade_tape("600519.SH", source="mootdx")
    f10 = mootdx_facade.get_f10("600519.SH", source="mootdx")
    responses = [
        ("mootdx-kline-600519.SH", kline),
        ("mootdx-order-book-600519.SH", order_book),
        ("mootdx-trade-tape-600519.SH", trade_tape),
        ("mootdx-f10-600519.SH", f10),
    ]
    for label, response in responses:
        _emit(label, response)
    errors = [response.error_message for _label, response in responses if response.status == "error"]
    if errors:
        pytest.skip("mootdx connected/imported but endpoint unavailable: " + " | ".join(str(item) for item in errors[:2]))
    assert kline.status == "ok"
    assert order_book.status == "ok"
    assert trade_tape.status in {"ok", "empty"}
    assert f10.status in {"ok", "empty"}


def test_live_iwencai_if_configured(iwencai_facade):
    if not os.getenv("ASTOCK_IWENCAI_COOKIE"):
        pytest.skip("ASTOCK_IWENCAI_COOKIE not configured")
    search = iwencai_facade.search_research("600519.SH", source="iwencai", query="白酒龙头 分红")
    expectation = iwencai_facade.get_institution_expectation("600519.SH", source="iwencai", query="贵州茅台 机构预期")
    _emit("iwencai-search", search)
    _emit("iwencai-expectation", expectation)
    assert search.status == "ok"
    assert expectation.status == "ok"

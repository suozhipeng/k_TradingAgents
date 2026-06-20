from __future__ import annotations

from tradingagents.astock.api.routes_tv import _tv_resolution


def test_tv_resolution_accepts_klinechart_numeric_periods() -> None:
    assert _tv_resolution("5") == "5m"
    assert _tv_resolution("1440") == "1d"
    assert _tv_resolution("10080") == "1w"
    assert _tv_resolution("43200") == "1mo"


def test_tv_resolution_accepts_tradingview_aliases() -> None:
    assert _tv_resolution("D") == "1d"
    assert _tv_resolution("1W") == "1w"
    assert _tv_resolution("1M") == "1mo"

"""LangChain-compatible A-share tools built on the stable interface."""

from __future__ import annotations

import json
from typing import Annotated, List, Optional, Sequence

try:  # pragma: no cover - optional dependency
    from langchain_core.tools import tool
except Exception:  # pragma: no cover - fallback when langchain is absent
    def tool(name):
        def _decorator(fn):
            fn.name = name or fn.__name__

            def _invoke(payload):
                if isinstance(payload, dict):
                    return fn(**payload)
                return fn(payload)

            fn.invoke = _invoke
            return fn

        return _decorator

from .interface import AStockInterface


def _dump_payload(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_astock_tools(interface: Optional[AStockInterface] = None):
    """Create a minimal A-share toolset for Analyst/Graph consumption."""

    astock_interface = interface or AStockInterface()

    @tool("astock_market_snapshot")
    def astock_market_snapshot(
        symbol: Annotated[str, "A-share symbol, e.g. 600519.SH or 000001.SZ"],
        start_date: Annotated[Optional[str], "Start date yyyy-mm-dd"] = None,
        end_date: Annotated[Optional[str], "End date yyyy-mm-dd"] = None,
        interval: Annotated[Optional[str], "K-line interval, default 1d"] = None,
        source: Annotated[Optional[str], "Optional source hint"] = None,
    ) -> str:
        """Return a JSON encoded market snapshot for one A-share symbol."""
        return _dump_payload(
            astock_interface.to_payload(
                symbol,
                sections=("market",),
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                source=source,
            )
        )

    @tool("astock_news_snapshot")
    def astock_news_snapshot(
        symbol: Annotated[str, "A-share symbol, e.g. 600519.SH or 000001.SZ"],
        limit: Annotated[Optional[int], "Maximum number of news items"] = None,
        look_back_days: Annotated[Optional[int], "Look-back window in days"] = None,
        curr_date: Annotated[Optional[str], "Current analysis date yyyy-mm-dd"] = None,
        source: Annotated[Optional[str], "Optional source hint"] = None,
    ) -> str:
        """Return a JSON encoded news snapshot for one A-share symbol."""
        return _dump_payload(
            astock_interface.to_payload(
                symbol,
                sections=("news",),
                limit=limit,
                look_back_days=look_back_days,
                curr_date=curr_date,
                source=source,
            )
        )

    @tool("astock_fundamentals_snapshot")
    def astock_fundamentals_snapshot(
        symbol: Annotated[str, "A-share symbol, e.g. 600519.SH or 000001.SZ"],
        curr_date: Annotated[Optional[str], "Current analysis date yyyy-mm-dd"] = None,
        freq: Annotated[Optional[str], "Report frequency, quarterly or annual"] = None,
        source: Annotated[Optional[str], "Optional source hint"] = None,
    ) -> str:
        """Return a JSON encoded fundamentals snapshot for one A-share symbol."""
        return _dump_payload(
            astock_interface.to_payload(
                symbol,
                sections=("fundamentals",),
                curr_date=curr_date,
                freq=freq,
                source=source,
            )
        )

    @tool("astock_announcements_snapshot")
    def astock_announcements_snapshot(
        symbol: Annotated[str, "A-share symbol, e.g. 600519.SH or 000001.SZ"],
        query: Annotated[Optional[str], "Announcement keyword/query"] = None,
        title: Annotated[Optional[str], "Announcement title hint"] = None,
        limit: Annotated[Optional[int], "Maximum number of announcement rows"] = None,
        source: Annotated[Optional[str], "Optional source hint"] = None,
    ) -> str:
        """Return a JSON encoded announcements snapshot for one A-share symbol."""
        return _dump_payload(
            astock_interface.to_payload(
                symbol,
                sections=("announcements",),
                announcement_query=query,
                announcement_title=title,
                limit=limit,
                source=source,
            )
        )

    @tool("astock_research_snapshot")
    def astock_research_snapshot(
        symbol: Annotated[str, "A-share symbol, e.g. 600519.SH or 000001.SZ"],
        query: Annotated[Optional[str], "Research keyword/query"] = None,
        title: Annotated[Optional[str], "Research title hint"] = None,
        limit: Annotated[Optional[int], "Maximum number of research rows"] = None,
        source: Annotated[Optional[str], "Optional source hint"] = None,
    ) -> str:
        """Return a JSON encoded research snapshot for one A-share symbol."""
        return _dump_payload(
            astock_interface.to_payload(
                symbol,
                sections=("research",),
                research_query=query,
                research_title=title,
                limit=limit,
                source=source,
            )
        )

    return [astock_market_snapshot, astock_news_snapshot, astock_fundamentals_snapshot, astock_announcements_snapshot, astock_research_snapshot]


__all__ = ["build_astock_tools"]

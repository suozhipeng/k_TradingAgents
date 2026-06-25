"""Research context schema — Phase 33 structured context for AI research.

This module formalizes the ad-hoc ``_gather_context()`` dict used by the
AI Agent API into a typed Pydantic model.  Each data source carries its
own ``source``, ``freshness``, and ``quality`` metadata so AI outputs
can cite provenance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DataSourceMeta(BaseModel):
    """Provenance metadata for a data source used in research context."""

    source: str = ""
    """Data provider name (e.g. ``"eastmoney"``, ``"sina"``, ``"internal_api"``)."""

    freshness: Optional[str] = None
    """ISO timestamp or relative age (e.g. ``"2026-06-25T10:00:00"``)."""

    quality: str = "unknown"
    """Data quality tag: ``"live"``, ``"recent"``, ``"stale"``, ``"fallback"``."""

    note: str = ""
    """Optional note (reason for fallback, known issue, etc.)."""


class StockInfoData(BaseModel):
    """Stock basic information from the TV / stock-info endpoint.

    Wraps the raw dict with provenance metadata.
    """

    raw: dict[str, Any] = Field(default_factory=dict)
    """Raw response from the stock-info API."""

    meta: DataSourceMeta = Field(default_factory=DataSourceMeta)


class MarketSummaryData(BaseModel):
    """Market overview/summary for a symbol.

    Wraps the raw dict with provenance metadata.
    """

    raw: dict[str, Any] = Field(default_factory=dict)
    """Raw response from the market/summary API."""

    meta: DataSourceMeta = Field(default_factory=DataSourceMeta)


class KlineData(BaseModel):
    """Latest K-line data for a symbol.

    Wraps the raw dict with provenance metadata.
    """

    raw: dict[str, Any] = Field(default_factory=dict)
    """Raw response from the kline API (bars, etc.)."""

    meta: DataSourceMeta = Field(default_factory=DataSourceMeta)


class ResearchContext(BaseModel):
    """Structured context for an AI research task.

    Replaces the ad-hoc ``dict`` returned by ``_gather_context()``.
    Each data source carries provenance metadata so AI outputs can
    cite source and freshness.

    Extend as new data sources are added (news, announcements, reports,
    fundamental data, backtest results, portfolio positions, etc.).
    """

    symbol: str = ""
    """Target stock symbol."""

    gathered_at: str = ""
    """ISO timestamp when context was gathered."""

    stock_info: StockInfoData = Field(default_factory=StockInfoData)
    """Stock basic information."""

    market_summary: MarketSummaryData = Field(default_factory=MarketSummaryData)
    """Market overview/summary."""

    kline_latest: KlineData = Field(default_factory=KlineData)
    """Latest K-line data."""

    # ── Future extensions (reserved fields, not yet wired) ──
    # news: list[NewsItemData] = []
    # announcements: list[AnnouncementData] = []
    # reports: list[ResearchReportData] = []
    # fundamentals: FundamentalData | None = None
    # backtest_results: list[BacktestResultSummary] = []
    # portfolio_risk: PortfolioRiskSnapshot | None = None

    @classmethod
    def from_gathered_dict(
        cls,
        symbol: str,
        raw_context: dict[str, Any],
        gathered_at: str | None = None,
    ) -> ResearchContext:
        """Build a ``ResearchContext`` from the ad-hoc dict returned by
        ``_gather_context()``.

        Parameters
        ----------
        symbol : str
            Target stock symbol.
        raw_context : dict
            The ad-hoc dict with ``stock_info``, ``market_summary``,
            ``kline_latest`` keys.
        gathered_at : str, optional
            ISO timestamp; defaults to ``datetime.now().isoformat()``.
        """
        now = gathered_at or datetime.now().isoformat()

        def _meta(source: str = "internal_api") -> DataSourceMeta:
            return DataSourceMeta(source=source, freshness=now, quality="live")

        return cls(
            symbol=symbol,
            gathered_at=now,
            stock_info=StockInfoData(
                raw=raw_context.get("stock_info") or {},
                meta=_meta(),
            ),
            market_summary=MarketSummaryData(
                raw=raw_context.get("market_summary") or {},
                meta=_meta(),
            ),
            kline_latest=KlineData(
                raw=raw_context.get("kline_latest") or {},
                meta=_meta(),
            ),
        )


__all__ = [
    "DataSourceMeta",
    "StockInfoData",
    "MarketSummaryData",
    "KlineData",
    "ResearchContext",
]

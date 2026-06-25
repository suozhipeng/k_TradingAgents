"""AStock schema definitions — structured data models for the system."""

from .optimization import OptimizeResult
from .report_archive import ReportArchive, ReportFormat, ReportItem, ResearchConclusionSummary
from .research_context import (
    DataSourceMeta,
    KlineData,
    MarketSummaryData,
    ResearchContext,
    StockInfoData,
)

__all__ = [
    "OptimizeResult",
    "DataSourceMeta",
    "StockInfoData",
    "MarketSummaryData",
    "KlineData",
    "ResearchContext",
    "ReportArchive",
    "ReportFormat",
    "ReportItem",
    "ResearchConclusionSummary",
]

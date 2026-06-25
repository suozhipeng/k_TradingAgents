"""AStock schema definitions — structured data models for the system."""
from __future__ import annotations

from .ops_audit import AuditEvent, TaskRun, TaskType
from .optimization import OptimizeResult
from .portfolio import Attribution, Portfolio, RiskExposure
from .report_archive import ReportArchive, ReportFormat, ReportItem, ResearchConclusionSummary
from .research_context import (
    DataSourceMeta,
    KlineData,
    MarketSummaryData,
    ResearchContext,
    StockInfoData,
)
from .research_task import ResearchAudit, ResearchTask, ResearchTaskStatus
from .trading_execution import Fill, Order, OrderSide, OrderStatus, OrderTradeMode, Position, Reconciliation

__all__ = [
    # Phase 32
    "OptimizeResult",
    # Phase 33
    "ResearchTaskStatus",
    "ResearchTask",
    "ResearchAudit",
    # Phase 34
    "DataSourceMeta",
    "StockInfoData",
    "MarketSummaryData",
    "KlineData",
    "ResearchContext",
    # Phase 33 Research
    "ReportArchive",
    "ReportFormat",
    "ReportItem",
    "ResearchConclusionSummary",
    # Phase 35
    "OrderStatus",
    "OrderSide",
    "OrderTradeMode",
    "Order",
    "Fill",
    "Position",
    "Reconciliation",
    # Phase 36
    "Portfolio",
    "RiskExposure",
    "Attribution",
    # Phase 37
    "TaskType",
    "TaskRun",
    "AuditEvent",
]

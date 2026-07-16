"""ORM models package for AStock Pro.

All SQLAlchemy declarative models are organised into logical groups:

- ``base``       – ``DeclarativeBase`` subclass
- ``reference``  – SecurityMaster, TradingCalendar, etc.
- ``market_data`` – KlineBar, Valuation, TechnicalIndicator, etc.
- ``events``     – CorporateAction, BacktestResult, PaperTrade, etc.
- ``governance`` – DataSource, AuditLog, ApiKey, etc.

Importing this package side-effects-registers all model classes with
``Base.metadata`` so that ``Base.metadata.create_all(engine)`` works.
"""

from __future__ import annotations

# Ensure all models are registered with Base.metadata
from .base import Base  # noqa: F401
from . import reference  # noqa: F401
from . import market_data  # noqa: F401
from . import events  # noqa: F401
from . import governance  # noqa: F401

# Re-export all model classes for convenient imports
from .reference import (
    DatabaseStorageProfile,
    SecurityMaster,
    TradingCalendar,
    SecurityStatusHistory,
    IndustryClassificationHistory,
    SuspensionEvent,
    PriceLimitRule,
)
from .market_data import (
    KlineBar,
    Valuation,
    AdjustFactor,
    OrderBookSnapshot,
    TradeTape,
    MarketIndicator,
    TechnicalIndicator,
)
from .events import (
    CorporateAction,
    ResearchReport,
    NewsItem,
    Announcement,
    BacktestResult,
    PaperTrade,
)
from .governance import (
    DataSource,
    DataQualityCheck,
    DataSnapshot,
    DataPartition,
    DataIngestionJob,
    DataIngestionJobEvent,
    MigrationVersion,
    AuditLog,
    ApiKey,
    DataQualityRule,
    DataQuarantine,
    NotificationChannel,
    Watchlist,
)

__all__ = [
    "Base",
    # reference
    "DatabaseStorageProfile",
    "SecurityMaster",
    "TradingCalendar",
    "SecurityStatusHistory",
    "IndustryClassificationHistory",
    "SuspensionEvent",
    "PriceLimitRule",
    # market_data
    "KlineBar",
    "Valuation",
    "AdjustFactor",
    "OrderBookSnapshot",
    "TradeTape",
    "MarketIndicator",
    "TechnicalIndicator",
    # events
    "CorporateAction",
    "ResearchReport",
    "NewsItem",
    "Announcement",
    "BacktestResult",
    "PaperTrade",
    # governance
    "DataSource",
    "DataQualityCheck",
    "DataSnapshot",
    "DataPartition",
    "DataIngestionJob",
    "DataIngestionJobEvent",
    "MigrationVersion",
    "AuditLog",
    "ApiKey",
    "DataQualityRule",
    "DataQuarantine",
    "NotificationChannel",
    "Watchlist",
]

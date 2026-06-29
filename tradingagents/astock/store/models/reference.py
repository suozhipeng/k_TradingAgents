"""Core reference data models for AStock Pro.

Contains: DatabaseStorageProfile, SecurityMaster, TradingCalendar,
SecurityStatusHistory, IndustryClassificationHistory, SuspensionEvent,
PriceLimitRule.
"""

from __future__ import annotations

import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DatabaseStorageProfile(Base):
    __tablename__ = "database_storage_profiles"
    profile_name: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)
    read_write_model: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class SecurityMaster(Base):
    __tablename__ = "security_master"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    raw_symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)
    board: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, default="CNY")
    list_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    delist_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String, default="active")
    is_st: Mapped[bool | None] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"
    exchange: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    session_open: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    session_close: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    session_break_json: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class SecurityStatusHistory(Base):
    __tablename__ = "security_status_history"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    effective_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    is_st: Mapped[bool | None] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class IndustryClassificationHistory(Base):
    __tablename__ = "industry_classification_history"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    effective_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    classification: Mapped[str] = mapped_column(String, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    industry_code: Mapped[str | None] = mapped_column(String, nullable=True)
    industry_name: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class SuspensionEvent(Base):
    __tablename__ = "suspension_events"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    start_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class PriceLimitRule(Base):
    __tablename__ = "price_limit_rules"
    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    exchange: Mapped[str | None] = mapped_column(String, nullable=True)
    board: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    up_limit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    down_limit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

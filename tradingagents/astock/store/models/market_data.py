"""Market data models for AStock Pro.

Contains: KlineBar, Valuation, AdjustFactor, OrderBookSnapshot, TradeTape,
MarketIndicator, TechnicalIndicator.
"""

from __future__ import annotations

import datetime
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class KlineBar(Base):
    __tablename__ = "kline_bars"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    bar_time: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    interval: Mapped[str] = mapped_column(String, primary_key=True, default="1d")
    adjust: Mapped[str] = mapped_column(String, primary_key=True, default="none")
    trade_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[str | None] = mapped_column(String, default="normal")
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Valuation(Base):
    __tablename__ = "valuations"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class AdjustFactor(Base):
    __tablename__ = "adjust_factors"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    adjust: Mapped[str] = mapped_column(String, primary_key=True)
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class OrderBookSnapshot(Base):
    __tablename__ = "order_book_snapshots"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    bid_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class TradeTape(Base):
    __tablename__ = "trade_tape"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class MarketIndicator(Base):
    __tablename__ = "market_indicators"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    ma_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_60: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ma_5: Mapped[float | None] = mapped_column(Float, nullable=True)


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    bar_time: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    interval: Mapped[str] = mapped_column(String, primary_key=True)
    indicator: Mapped[str] = mapped_column(String, primary_key=True)
    params_hash: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    params_json: Mapped[str | None] = mapped_column(String, nullable=True)
    value_json: Mapped[str] = mapped_column(String, nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

"""Corporate events and alternative data models for AStock Pro.

Contains: CorporateAction, ResearchReport, NewsItem, Announcement,
BacktestResult, PaperTrade.
"""

from __future__ import annotations

import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    action_id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    action_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ex_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    cash_dividend: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_dividend_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    split_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    rights_issue_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ResearchReport(Base):
    __tablename__ = "research_reports"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    report_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    title: Mapped[str] = mapped_column(String, primary_key=True)
    institution: Mapped[str | None] = mapped_column(String, nullable=True)
    analyst: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class NewsItem(Base):
    __tablename__ = "news_items"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    publish_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    url: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class Announcement(Base):
    __tablename__ = "announcements"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    publish_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    url: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    params_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    trade_id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    trade_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String, nullable=True)
    actionable: Mapped[bool | None] = mapped_column(Boolean, default=False)
    decision_scope: Mapped[str | None] = mapped_column(String, default="paper_trading_only")
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

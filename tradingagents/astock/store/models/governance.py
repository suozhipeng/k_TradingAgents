"""Data governance and infrastructure models for AStock Pro.

Contains: DataSource, DataQualityCheck, DataSnapshot, DataPartition,
DataIngestionJob, DataIngestionJobEvent, MigrationVersion, AuditLog,
ApiKey, DataQualityRule, DataQuarantine, NotificationChannel.
"""

from __future__ import annotations

import datetime
from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DataSource(Base):
    __tablename__ = "data_sources"
    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer, default=100)
    license_status: Mapped[str | None] = mapped_column(String, default="unknown")
    rate_limit_json: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_required: Mapped[bool | None] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"
    check_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    interval: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    rule_version: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    missing_count: Mapped[int | None] = mapped_column(BigInteger, default=0)
    invalid_count: Mapped[int | None] = mapped_column(BigInteger, default=0)
    duplicate_count: Mapped[int | None] = mapped_column(BigInteger, default=0)
    fallback_path_json: Mapped[str | None] = mapped_column(String, nullable=True)
    details_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    interval: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    row_count: Mapped[int | None] = mapped_column(BigInteger, default=0)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    quality: Mapped[str | None] = mapped_column(String, default="normal")
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataPartition(Base):
    __tablename__ = "data_partitions"
    partition_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    interval: Mapped[str | None] = mapped_column(String, nullable=True)
    partition_key: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    storage_tier: Mapped[str | None] = mapped_column(String, default="hot")
    uri: Mapped[str | None] = mapped_column(String, nullable=True)
    row_count: Mapped[int | None] = mapped_column(BigInteger, default=0)
    status: Mapped[str | None] = mapped_column(String, default="active")
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataIngestionJob(Base):
    __tablename__ = "data_ingestion_jobs"
    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str | None] = mapped_column(String, default="queued")
    target_table: Mapped[str | None] = mapped_column(String, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    total_rows: Mapped[int | None] = mapped_column(BigInteger, default=0)
    processed_rows: Mapped[int | None] = mapped_column(BigInteger, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataIngestionJobEvent(Base):
    __tablename__ = "data_ingestion_job_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    event_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    status: Mapped[str] = mapped_column(String, nullable=False)
    processed_rows: Mapped[int | None] = mapped_column(BigInteger, default=0)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(String, nullable=True)


class MigrationVersion(Base):
    __tablename__ = "migration_versions"
    version_id: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_by: Mapped[str | None] = mapped_column(String, nullable=True)
    applied_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, default=0)
    status: Mapped[str | None] = mapped_column(String, default="applied")
    rollback_sql: Mapped[str | None] = mapped_column(String, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    detail_json: Mapped[str | None] = mapped_column(String, nullable=True)
    old_value_json: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value_json: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, default="success")
    event_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ApiKey(Base):
    __tablename__ = "api_keys"
    key_id: Mapped[str] = mapped_column(String, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String, nullable=False)
    key_prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, default="readonly")
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    allowed_capabilities: Mapped[str | None] = mapped_column(String, nullable=True)
    rate_limit: Mapped[int | None] = mapped_column(Integer, default=100)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"
    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_interval: Mapped[str | None] = mapped_column(String, nullable=True)
    check_sql: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str | None] = mapped_column(String, default="warn")
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int | None] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_count: Mapped[int | None] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DataQuarantine(Base):
    __tablename__ = "data_quarantine"
    quarantine_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_dataset: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    interval: Mapped[str | None] = mapped_column(String, nullable=True)
    bar_time: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    trade_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    original_values_json: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str | None] = mapped_column(String, default="warn")
    resolution: Mapped[str | None] = mapped_column(String, default="unresolved")
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    name: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="generic")
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool | None] = mapped_column(Boolean, default=True)
    config_json: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Watchlist(Base):
    __tablename__ = "watchlist"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String, default="manual")

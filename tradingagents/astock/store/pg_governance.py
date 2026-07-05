"""Snapshots, ingestion jobs, audit log, API key, quality rule, and quarantine APIs."""

from __future__ import annotations

from .pg_common import *


class PGGovernanceMixin:
    """Snapshots, ingestion jobs, audit log, API key, quality rule, and quarantine APIs."""

    async def store_data_snapshot(self, snapshot: dict[str, Any]) -> int:
        data = dict(snapshot)
        if "snapshot_id" not in data:
            data["snapshot_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_snapshots", [data])

    async def store_data_quality_check(self, check: dict[str, Any]) -> int:
        data = dict(check)
        if "check_id" not in data:
            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        if "fallback_path_json" not in data and isinstance(data.get("fallback_path"), list):
            data["fallback_path_json"] = json.dumps(data.pop("fallback_path"), ensure_ascii=False)
        return await self.insert_table_rows("data_quality_checks", [data])

    async def store_data_partition(self, partition: dict[str, Any]) -> int:
        data = dict(partition)
        if "partition_id" not in data:
            data["partition_id"] = uuid.uuid4().hex
        return await self.insert_table_rows("data_partitions", [data])

    async def store_ingestion_job(self, job: dict[str, Any]) -> int:
        data = dict(job)
        if "job_id" not in data:
            data["job_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_ingestion_jobs", [data])

    async def store_ingestion_job_event(self, event: dict[str, Any]) -> int:
        data = dict(event)
        if "event_id" not in data:
            data["event_id"] = uuid.uuid4().hex
        if "metadata_json" not in data and isinstance(data.get("metadata"), dict):
            data["metadata_json"] = json.dumps(data.pop("metadata"), ensure_ascii=False, sort_keys=True)
        return await self.insert_table_rows("data_ingestion_job_events", [data])

    # ---- audit log ----------------------------------------------------------

    async def store_audit_log(
        self,
        event_type: str,
        action: str,
        *,
        actor: str | None = None,
        actor_ip: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        detail: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> str:
        """Write an audit event to the audit_log table. Returns the event_id."""
        event_id = uuid.uuid4().hex
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "actor": actor,
            "actor_ip": actor_ip,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "detail_json": json.dumps(detail, ensure_ascii=False) if detail else None,
            "old_value_json": json.dumps(old_value, ensure_ascii=False) if old_value else None,
            "new_value_json": json.dumps(new_value, ensure_ascii=False) if new_value else None,
            "outcome": outcome,
        }
        pk_cols = ["event_id"]
        columns = list(record.keys())
        sql = self._build_upsert_sql("audit_log", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return event_id

    async def query_audit_log(
        self,
        *,
        actor: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: dict[str, Any] = {}
        if actor:
            sql += " AND actor = :actor"
            params["actor"] = actor
        if resource_type:
            sql += " AND resource_type = :resource_type"
            params["resource_type"] = resource_type
        if resource_id:
            sql += " AND resource_id = :resource_id"
            params["resource_id"] = resource_id
        if event_type:
            sql += " AND event_type = :event_type"
            params["event_type"] = event_type
        sql += " ORDER BY event_time DESC LIMIT :limit"
        params["limit"] = limit

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- API keys -----------------------------------------------------------

    async def add_api_key(
        self,
        *,
        key_hash: str,
        key_prefix: str = "",
        label: str = "",
        role: str = "readonly",
        owner: str = "",
        allowed_capabilities: str = "",
        rate_limit: int = 100,
        expires_at: str | None = None,
    ) -> str:
        """Register an API key hash. Returns key_id."""
        key_id = uuid.uuid4().hex
        record = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "label": label,
            "role": role,
            "owner": owner,
            "allowed_capabilities": allowed_capabilities,
            "rate_limit": rate_limit,
            "expires_at": expires_at,
            "is_active": True,
        }
        columns = list(record.keys())
        pk_cols = ["key_id"]
        sql = self._build_upsert_sql("api_keys", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return key_id

    async def revoke_api_key(self, key_id: str) -> None:
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(
                    text("UPDATE api_keys SET is_active = FALSE WHERE key_id = :kid"),
                    {"kid": key_id},
                )
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(
                    text("UPDATE api_keys SET is_active = FALSE WHERE key_id = :kid"),
                    {"kid": key_id},
                )
                await session.commit()

    async def validate_api_key(self, key_hash: str) -> dict[str, Any] | None:
        """Check if a key hash is valid and active. Returns key record or None."""
        sql = (
            "SELECT key_id, role, allowed_capabilities, rate_limit, expires_at "
            "FROM api_keys WHERE key_hash = :kh AND (is_active IS NULL OR is_active = TRUE) "
            "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
        )
        params = {"kh": key_hash}

        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql), params).fetchone()
                if row is None:
                    return None
                record = {
                    "key_id": str(row[0]),
                    "role": str(row[1]),
                    "allowed_capabilities": str(row[2]) if row[2] else "",
                    "rate_limit": int(row[3]) if row[3] else 100,
                }
                conn.execute(
                    text("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = :kid"),
                    {"kid": record["key_id"]},
                )
                conn.commit()
                return record
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                row = result.fetchone()
                if row is None:
                    return None
                record = {
                    "key_id": str(row[0]),
                    "role": str(row[1]),
                    "allowed_capabilities": str(row[2]) if row[2] else "",
                    "rate_limit": int(row[3]) if row[3] else 100,
                }
                await conn.execute(
                    text("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_id = :kid"),
                    {"kid": record["key_id"]},
                )
                await conn.commit()
                return record

    # ---- data quality rules -------------------------------------------------

    async def store_quality_rule(
        self,
        *,
        rule_name: str,
        description: str = "",
        scope_dataset: str = "",
        scope_interval: str = "",
        check_sql: str = "",
        severity: str = "warn",
        is_active: bool = True,
        cooldown_minutes: int = 0,
    ) -> str:
        """Register a data quality rule. Returns rule_id."""
        rule_id = uuid.uuid4().hex
        record = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "description": description,
            "scope_dataset": scope_dataset,
            "scope_interval": scope_interval,
            "check_sql": check_sql,
            "severity": severity,
            "is_active": is_active,
            "cooldown_minutes": cooldown_minutes,
        }
        columns = list(record.keys())
        pk_cols = ["rule_id"]
        sql = self._build_upsert_sql("data_quality_rules", columns, pk_cols)

        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(text(sql), record)
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(text(sql), record)
                await session.commit()
        return rule_id

    async def run_quality_rule(
        self, rule_id: str, *, dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute a single quality rule and store results.

        Returns ``{rule_id, status, matched, failed, details}``.
        """
        sql_rule = (
            "SELECT rule_name, check_sql, severity FROM data_quality_rules "
            "WHERE rule_id = :rid AND is_active = TRUE"
        )
        params = {"rid": rule_id}

        if self._sync:
            with self._sync_engine.connect() as conn:
                row = conn.execute(text(sql_rule), params).fetchone()
                if row is None:
                    raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
                rule_name, check_sql_str, severity = str(row[0]), str(row[1] or ""), str(row[2])
                if not check_sql_str:
                    raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")
                try:
                    result = conn.execute(text(check_sql_str))
                    result_rows = result.fetchall()
                    row_count = len(result_rows)
                    failed = row_count
                    status = "pass" if failed == 0 else severity
                except Exception as exc:
                    status = "error"
                    failed = -1
                    row_count = 0
                    _ = exc

                quarantined = 0
                if not dry_run and failed > 0 and status != "error":
                    for r in result_rows:
                        q_symbol = str(r[0]) if r else ""
                        self._store_quarantine_sync(
                            source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                            symbol=q_symbol,
                            reason=f"Quality rule {rule_name} failed",
                            rule_id=rule_id,
                            original_values=dict(r._mapping) if hasattr(r, "_mapping") else {},
                            severity=severity,
                        )
                        quarantined += 1

                conn.execute(
                    text(
                        "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
                        "last_result = :status, failure_count = failure_count + :fc "
                        "WHERE rule_id = :rid"
                    ),
                    {"status": status, "fc": max(failed, 0), "rid": rule_id},
                )
                conn.commit()

                # Store quality check
                check_data = {
                    "dataset": rule_name,
                    "rule_version": rule_id,
                    "status": status,
                    "invalid_count": max(failed, 0),
                    "details": {"rows_checked": row_count, "severity": severity},
                }
                self._store_quality_check_sync(check_data)

                return {
                    "rule_id": rule_id,
                    "status": status,
                    "matched": row_count,
                    "failed": failed,
                    "quarantined": quarantined,
                }
        else:
            async with self._async_engine.connect() as conn:
                row = await conn.execute(text(sql_rule), params)
                row_data = row.fetchone()
                if row_data is None:
                    raise ValueError(f"Quality rule {rule_id!r} not found or inactive")
                rule_name, check_sql_str, severity = (
                    str(row_data[0]),
                    str(row_data[1] or ""),
                    str(row_data[2]),
                )
                if not check_sql_str:
                    raise ValueError(f"Quality rule {rule_id!r} has no check_sql defined")
                try:
                    result = await conn.execute(text(check_sql_str))
                    result_rows = result.fetchall()
                    row_count = len(result_rows)
                    failed = row_count
                    status = "pass" if failed == 0 else severity
                except Exception as exc:
                    status = "error"
                    failed = -1
                    row_count = 0
                    _ = exc

                quarantined = 0
                if not dry_run and failed > 0 and status != "error":
                    for r in result_rows:
                        q_symbol = str(r[0]) if r else ""
                        await self._store_quarantine_async(
                            source_dataset=rule_name.split(":")[0] if ":" in rule_name else "unknown",
                            symbol=q_symbol,
                            reason=f"Quality rule {rule_name} failed",
                            rule_id=rule_id,
                            original_values=dict(r._mapping) if hasattr(r, "_mapping") else {},
                            severity=severity,
                        )
                        quarantined += 1

                await conn.execute(
                    text(
                        "UPDATE data_quality_rules SET last_run_at = CURRENT_TIMESTAMP, "
                        "last_result = :status, failure_count = failure_count + :fc "
                        "WHERE rule_id = :rid"
                    ),
                    {"status": status, "fc": max(failed, 0), "rid": rule_id},
                )
                await conn.commit()

                check_data = {
                    "dataset": rule_name,
                    "rule_version": rule_id,
                    "status": status,
                    "invalid_count": max(failed, 0),
                    "details": {"rows_checked": row_count, "severity": severity},
                }
                await self.store_data_quality_check(check_data)

                return {
                    "rule_id": rule_id,
                    "status": status,
                    "matched": row_count,
                    "failed": failed,
                    "quarantined": quarantined,
                }

    async def run_all_quality_rules(self) -> list[dict[str, Any]]:
        """Run all active quality rules and return results."""
        sql = "SELECT rule_id FROM data_quality_rules WHERE is_active = TRUE"
        if self._sync:
            with self._sync_engine.connect() as conn:
                rule_rows = conn.execute(text(sql)).fetchall()
                results = []
                for (rule_id_val,) in rule_rows:
                    try:
                        results.append(
                            self._run_async(self.run_quality_rule(rule_id_val))
                        )
                    except Exception as exc:
                        results.append({"rule_id": rule_id_val, "status": "error", "error": str(exc)})
                return results
        else:
            async with self._async_engine.connect() as conn:
                rule_rows = await conn.execute(text(sql))
                results = []
                for row in rule_rows.fetchall():
                    rule_id_val = str(row[0])
                    try:
                        results.append(await self.run_quality_rule(rule_id_val))
                    except Exception as exc:
                        results.append({"rule_id": rule_id_val, "status": "error", "error": str(exc)})
                return results

    # ---- data quarantine internal helpers -----------------------------------

    def _store_quarantine_sync(self, **kwargs: Any) -> str:
        quarantine_id = uuid.uuid4().hex
        record = {
            "quarantine_id": quarantine_id,
            "source_dataset": kwargs.get("source_dataset", ""),
            "symbol": kwargs.get("symbol", ""),
            "interval": kwargs.get("interval", ""),
            "bar_time": kwargs.get("bar_time"),
            "trade_date": kwargs.get("trade_date"),
            "reason": kwargs.get("reason", ""),
            "rule_id": kwargs.get("rule_id"),
            "original_values_json": json.dumps(kwargs.get("original_values", {}), ensure_ascii=False),
            "severity": kwargs.get("severity", "warn"),
            "resolution": kwargs.get("resolution", "unresolved"),
        }
        columns = list(record.keys())
        pk_cols = ["quarantine_id"]
        sql = self._build_upsert_sql("data_quarantine", columns, pk_cols)
        with self._sync_engine.connect() as conn:
            conn.execute(text(sql), record)
            conn.commit()
        return quarantine_id

    async def _store_quarantine_async(self, **kwargs: Any) -> str:
        quarantine_id = uuid.uuid4().hex
        record = {
            "quarantine_id": quarantine_id,
            "source_dataset": kwargs.get("source_dataset", ""),
            "symbol": kwargs.get("symbol", ""),
            "interval": kwargs.get("interval", ""),
            "bar_time": kwargs.get("bar_time"),
            "trade_date": kwargs.get("trade_date"),
            "reason": kwargs.get("reason", ""),
            "rule_id": kwargs.get("rule_id"),
            "original_values_json": json.dumps(kwargs.get("original_values", {}), ensure_ascii=False),
            "severity": kwargs.get("severity", "warn"),
            "resolution": kwargs.get("resolution", "unresolved"),
        }
        columns = list(record.keys())
        pk_cols = ["quarantine_id"]
        sql = self._build_upsert_sql("data_quarantine", columns, pk_cols)
        async with self._async_session_factory() as session:
            await session.execute(text(sql), record)
            await session.commit()
        return quarantine_id

    def _store_quality_check_sync(self, check: dict[str, Any]) -> int:
        data = dict(check)
        if "check_id" not in data:
            data["check_id"] = uuid.uuid4().hex
        if "details_json" not in data and isinstance(data.get("details"), dict):
            data["details_json"] = json.dumps(data.pop("details"), ensure_ascii=False, sort_keys=True)
        columns = list(data.keys())
        pk_cols = ["check_id"]
        sql = self._build_upsert_sql("data_quality_checks", columns, pk_cols)
        with self._sync_engine.connect() as conn:
            conn.execute(text(sql), data)
            conn.commit()
        return 1

    # ---- data quarantine public API -----------------------------------------

    async def store_quarantine(
        self,
        *,
        source_dataset: str,
        symbol: str = "",
        interval: str = "",
        bar_time: str | None = None,
        trade_date: str | None = None,
        reason: str = "",
        rule_id: str | None = None,
        original_values: dict[str, Any] | None = None,
        severity: str = "warn",
    ) -> str:
        """Move anomalous data into the quarantine zone. Returns quarantine_id."""
        if self._sync:
            return self._store_quarantine_sync(
                source_dataset=source_dataset,
                symbol=symbol,
                interval=interval,
                bar_time=bar_time,
                trade_date=trade_date,
                reason=reason,
                rule_id=rule_id,
                original_values=original_values,
                severity=severity,
            )
        return await self._store_quarantine_async(
            source_dataset=source_dataset,
            symbol=symbol,
            interval=interval,
            bar_time=bar_time,
            trade_date=trade_date,
            reason=reason,
            rule_id=rule_id,
            original_values=original_values,
            severity=severity,
        )

    async def resolve_quarantine(
        self, quarantine_id: str, *, resolved_by: str = "system"
    ) -> None:
        if self._sync:
            with self._sync_engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE data_quarantine SET resolution = 'resolved', "
                        "resolved_by = :rb, resolved_at = CURRENT_TIMESTAMP "
                        "WHERE quarantine_id = :qid"
                    ),
                    {"rb": resolved_by, "qid": quarantine_id},
                )
                conn.commit()
        else:
            async with self._async_session_factory() as session:
                await session.execute(
                    text(
                        "UPDATE data_quarantine SET resolution = 'resolved', "
                        "resolved_by = :rb, resolved_at = CURRENT_TIMESTAMP "
                        "WHERE quarantine_id = :qid"
                    ),
                    {"rb": resolved_by, "qid": quarantine_id},
                )
                await session.commit()

    async def query_quarantine(
        self,
        *,
        severity: str | None = None,
        resolution: str = "unresolved",
        limit: int = 100,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM data_quarantine WHERE resolution = :resolution"
        params: dict[str, Any] = {"resolution": resolution}
        if severity:
            sql += " AND severity = :severity"
            params["severity"] = severity
        sql += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        if self._sync:
            with self._sync_engine.connect() as conn:
                result = conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()
        else:
            async with self._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=result.keys()) if rows else pd.DataFrame()

    # ---- schema introspection -----------------------------------------------

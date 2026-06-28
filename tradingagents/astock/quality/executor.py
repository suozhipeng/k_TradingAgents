"""
QualityExecutor — full production data quality engine for AStock Pro.

Validates DataFrame payloads against hard-coded built-in rules and
user-defined custom rules from the ``data_quality_rules`` table.

Supports both sync (DuckDB AStockStore) and async (PGStore) back-ends.
Async detection uses ``asyncio.iscoroutinefunction()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BlockedImportError(Exception):
    """Raised when data fails an error-severity quality check and is quarantined."""

    def __init__(self, message: str, violations: list[dict[str, Any]]) -> None:
        self.violations = violations
        super().__init__(message)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a single quality check."""

    passed: bool
    rule_name: str
    severity: str  # 'error' blocks, 'warn' allows with warning
    violations: int = 0
    details: list = field(default_factory=list)
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# QualityExecutor
# ---------------------------------------------------------------------------


class QualityExecutor:
    """Production data quality executor.

    Parameters
    ----------
    store : AStockStore | PGStore
        The database store (sync DuckDB or async SQLAlchemy).
    dry_run : bool
        If True, log actions but do not write to DB.
    """

    # A-share price range bounds
    MIN_PRICE: float = 0.01
    MAX_PRICE: float = 10000.0

    def __init__(self, store: Any, dry_run: bool = False) -> None:
        self._store = store
        self._dry_run = dry_run

    # ------------------------------------------------------------------
    # Public API — kline
    # ------------------------------------------------------------------

    def validate_kline(
        self, symbol: str, df: pd.DataFrame, interval: str = "1d"
    ) -> ValidationResult:
        """Run all built-in checks + custom rules for kline data.

        Returns a combined ``ValidationResult``.  The *passed* field is
        True only when *every* check passed.  The *violations* count is
        the sum across all failing checks.
        """
        t0 = time.monotonic()
        combined = ValidationResult(
            passed=True,
            rule_name="validate_kline",
            severity="error",
            violations=0,
            details=[],
        )

        # Built-in checks
        checks = [
            self._check_non_negative_prices(df),
            self._check_high_low_integrity(df),
            self._check_no_nan_critical(df),
            self._check_price_range(df),
            self._check_volume_integrity(df),
        ]

        # Custom rules
        custom_results = self._run_custom_rules(
            dataset="kline_bars", symbol=symbol, interval=interval, df=df
        )
        checks.extend(custom_results)

        # Merge
        for r in checks:
            if not r.passed:
                combined.passed = False
                combined.violations += r.violations
                combined.details.append(
                    {
                        "rule": r.rule_name,
                        "severity": r.severity,
                        "violations": r.violations,
                    }
                )
                combined.details.extend(r.details)

        combined.duration_ms = (time.monotonic() - t0) * 1000.0
        return combined

    def validate_and_import_kline(
        self,
        symbol: str,
        df: pd.DataFrame,
        interval: str = "1d",
        source: str = "",
    ) -> int:
        """Validate then import kline data.

        * If any **error**-severity check fails -> quarantine + raise
          ``BlockedImportError``.
        * If only warnings -> log warning, proceed with import.
        * If all pass -> import directly.

        Returns the number of rows inserted.
        """
        result = self.validate_kline(symbol, df, interval)
        if not result.passed:
            error_details = [
                d for d in result.details if d.get("severity") == "error"
            ]
            if error_details:
                self._quarantine_batch("kline_bars", symbol, df, result)
                raise BlockedImportError(
                    f"kline data for {symbol} blocked by quality checks: "
                    f"{len(error_details)} error(s) with {result.violations} total violations",
                    violations=error_details,
                )
            else:
                logger.warning(
                    "kline data for %s passed with %d warning(s): %s",
                    symbol,
                    result.violations,
                    [d["rule"] for d in result.details],
                )

        insert_fn = self._store.insert_kline
        if asyncio.iscoroutinefunction(insert_fn):
            rows = asyncio.run(insert_fn(symbol, df, interval, source))
        else:
            rows = insert_fn(symbol, df, interval, source)
        return rows

    # ------------------------------------------------------------------
    # Public API — valuations
    # ------------------------------------------------------------------

    def validate_valuations(self, symbol: str, df: pd.DataFrame) -> ValidationResult:
        """Run quality checks for valuation data."""
        t0 = time.monotonic()
        checks: list[ValidationResult] = []

        if {"open", "high", "low", "close"}.intersection(df.columns):
            checks.append(self._check_non_negative_prices(df))
            checks.append(self._check_high_low_integrity(df))
            checks.append(self._check_price_range(df))

        if "market_cap" in df.columns:
            cap_bad = (df["market_cap"].fillna(0) < 0).sum()
            if cap_bad > 0:
                checks.append(
                    ValidationResult(
                        passed=False,
                        rule_name="check_valuation_market_cap",
                        severity="error",
                        violations=int(cap_bad),
                        details=[
                            {
                                "rule": "check_valuation_market_cap",
                                "message": "market_cap must be >= 0",
                            }
                        ],
                    )
                )

        val_cols = [c for c in ("pe", "pb", "market_cap") if c in df.columns]
        for col in val_cols:
            nan_count = int(df[col].isna().sum())
            if nan_count > 0:
                checks.append(
                    ValidationResult(
                        passed=False,
                        rule_name=f"check_{col}_nan",
                        severity="warn",
                        violations=nan_count,
                        details=[
                            {
                                "rule": f"check_{col}_nan",
                                "message": f"{nan_count} NaN values in {col}",
                            }
                        ],
                    )
                )

        custom_results = self._run_custom_rules(
            dataset="valuations", symbol=symbol, interval="", df=df
        )
        checks.extend(custom_results)

        passed = all(c.passed for c in checks)
        total_violations = sum(c.violations for c in checks)
        details = []
        for c in checks:
            if not c.passed:
                details.append(
                    {
                        "rule": c.rule_name,
                        "severity": c.severity,
                        "violations": c.violations,
                    }
                )
                details.extend(c.details)

        return ValidationResult(
            passed=passed,
            rule_name="validate_valuations",
            severity="error",
            violations=total_violations,
            details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    def validate_and_import_valuations(
        self, symbol: str, df: pd.DataFrame, source: str = ""
    ) -> int:
        """Validate then import valuation data."""
        result = self.validate_valuations(symbol, df)
        if not result.passed:
            error_details = [
                d for d in result.details if d.get("severity") == "error"
            ]
            if error_details:
                self._quarantine_batch("valuations", symbol, df, result)
                raise BlockedImportError(
                    f"valuation data for {symbol} blocked by quality checks: "
                    f"{len(error_details)} error(s) with {result.violations} total violations",
                    violations=error_details,
                )
            else:
                logger.warning(
                    "valuation data for %s passed with %d warning(s): %s",
                    symbol,
                    result.violations,
                    [d["rule"] for d in result.details],
                )

        insert_fn = self._store.insert_valuations
        if asyncio.iscoroutinefunction(insert_fn):
            rows = asyncio.run(insert_fn(symbol, df, source))
        else:
            rows = insert_fn(symbol, df, source)
        return rows

    # ------------------------------------------------------------------
    # Quarantine resolution
    # ------------------------------------------------------------------

    def resolve_quarantine(
        self, quarantine_id: str, resolved_by: str = "admin"
    ) -> bool:
        """Re-validate quarantined data and re-import if valid."""
        t0 = time.monotonic()

        qdf = self._exec_sql(
            'SELECT * FROM data_quarantine WHERE quarantine_id = ?',
            [quarantine_id],
        )
        if qdf is None or qdf.empty:
            logger.error("Quarantine record %s not found", quarantine_id)
            return False

        record = qdf.iloc[0].to_dict()
        source_dataset = record.get("source_dataset", "")
        symbol = record.get("symbol", "")
        interval = record.get("interval", "1d")
        original_json = record.get("original_values_json", "{}")

        try:
            original_data = json.loads(original_json)
        except (json.JSONDecodeError, TypeError):
            logger.error("Invalid original_values_json for quarantine %s", quarantine_id)
            return False

        if isinstance(original_data, dict):
            original_data = [original_data]
        df = pd.DataFrame(original_data)
        if df.empty:
            logger.warning("No data to re-import for quarantine %s", quarantine_id)
            return False

        if source_dataset == "kline_bars":
            result = self.validate_kline(symbol, df, interval=interval)
        elif source_dataset == "valuations":
            result = self.validate_valuations(symbol, df)
        else:
            logger.error("Unknown source_dataset %s for quarantine", source_dataset)
            return False

        if not result.passed:
            logger.warning(
                "Quarantine %s still fails validation (%d violations)",
                quarantine_id, result.violations,
            )
            return False

        try:
            if source_dataset == "kline_bars":
                insert_fn = self._store.insert_kline
                if asyncio.iscoroutinefunction(insert_fn):
                    asyncio.run(insert_fn(symbol, df, interval=interval, source=""))
                else:
                    insert_fn(symbol, df, interval=interval, source="")
            elif source_dataset == "valuations":
                insert_fn = self._store.insert_valuations
                if asyncio.iscoroutinefunction(insert_fn):
                    asyncio.run(insert_fn(symbol, df, source=""))
                else:
                    insert_fn(symbol, df, source="")

            if not self._dry_run:
                self._exec_sql(
                    "UPDATE data_quarantine SET resolution = 'resolved', "
                    "resolved_by = ?, resolved_at = datetime('now') "
                    "WHERE quarantine_id = ?",
                    [resolved_by, quarantine_id],
                )

            elapsed = (time.monotonic() - t0) * 1000
            logger.info("Quarantine %s resolved by %s in %.0f ms", quarantine_id, resolved_by, elapsed)
            return True
        except Exception as exc:
            logger.error("Failed to re-import quarantined data %s: %s", quarantine_id, exc)
            return False

    # ------------------------------------------------------------------
    # Built-in check #1 — non-negative prices
    # ------------------------------------------------------------------

    def _check_non_negative_prices(self, df: pd.DataFrame) -> ValidationResult:
        """open, high, low, close must all be >= 0."""
        t0 = time.monotonic()
        price_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
        if not price_cols:
            return ValidationResult(
                passed=True, rule_name="non_negative_prices", severity="error",
                violations=0, duration_ms=(time.monotonic() - t0) * 1000.0,
            )

        violations = 0
        details: list[dict] = []
        for col in price_cols:
            bad_mask = df[col] < 0
            bad_count = int(bad_mask.sum())
            if bad_count > 0:
                violations += bad_count
                details.append({
                    "rule": "non_negative_prices",
                    "column": col,
                    "violations": bad_count,
                    "sample": df.loc[bad_mask, col].head(5).to_dict(),
                })

        return ValidationResult(
            passed=violations == 0, rule_name="non_negative_prices", severity="error",
            violations=violations, details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Built-in check #2 — high/low integrity
    # ------------------------------------------------------------------

    def _check_high_low_integrity(self, df: pd.DataFrame) -> ValidationResult:
        """For each row: high >= low, high >= close, high >= open,
        low <= open, low <= close."""
        t0 = time.monotonic()
        cols = {"open", "high", "low", "close"}
        if not cols.issubset(df.columns):
            return ValidationResult(
                passed=True, rule_name="high_low_integrity", severity="error",
                violations=0, duration_ms=(time.monotonic() - t0) * 1000.0,
            )

        violations = 0
        details: list[dict] = []
        checks_map = {
            "high >= low": df["high"] < df["low"],
            "high >= close": df["high"] < df["close"],
            "high >= open": df["high"] < df["open"],
            "low <= open": df["low"] > df["open"],
            "low <= close": df["low"] > df["close"],
        }
        for label, mask in checks_map.items():
            count = int(mask.sum())
            if count > 0:
                violations += count
                details.append({
                    "rule": "high_low_integrity",
                    "check": label,
                    "violations": count,
                })

        return ValidationResult(
            passed=violations == 0, rule_name="high_low_integrity", severity="error",
            violations=violations, details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Built-in check #3 — no NaN in critical columns
    # ------------------------------------------------------------------

    def _check_no_nan_critical(self, df: pd.DataFrame) -> ValidationResult:
        """No NaN in bar_time, open, high, low, close, volume."""
        t0 = time.monotonic()
        critical_cols = [
            c for c in ("bar_time", "open", "high", "low", "close", "volume")
            if c in df.columns
        ]
        if not critical_cols:
            return ValidationResult(
                passed=True, rule_name="no_nan_critical", severity="error",
                violations=0, duration_ms=(time.monotonic() - t0) * 1000.0,
            )

        violations = 0
        details: list[dict] = []
        for col in critical_cols:
            nan_count = int(df[col].isna().sum())
            if nan_count > 0:
                violations += nan_count
                details.append({
                    "rule": "no_nan_critical",
                    "column": col,
                    "violations": nan_count,
                })

        return ValidationResult(
            passed=violations == 0, rule_name="no_nan_critical", severity="error",
            violations=violations, details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Built-in check #4 — price range (A-share)
    # ------------------------------------------------------------------

    def _check_price_range(self, df: pd.DataFrame) -> ValidationResult:
        """A-share price range: 0.01 to 10000."""
        t0 = time.monotonic()
        price_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
        if not price_cols:
            return ValidationResult(
                passed=True, rule_name="price_range", severity="error",
                violations=0, duration_ms=(time.monotonic() - t0) * 1000.0,
            )

        violations = 0
        details: list[dict] = []
        for col in price_cols:
            col_data = df[col].dropna()
            if col_data.empty:
                continue
            out_of_range = (col_data < self.MIN_PRICE) | (col_data > self.MAX_PRICE)
            bad_count = int(out_of_range.sum())
            if bad_count > 0:
                violations += bad_count
                details.append({
                    "rule": "price_range",
                    "column": col,
                    "violations": bad_count,
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                })

        return ValidationResult(
            passed=violations == 0, rule_name="price_range", severity="error",
            violations=violations, details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Built-in check #5 — volume integrity
    # ------------------------------------------------------------------

    def _check_volume_integrity(self, df: pd.DataFrame) -> ValidationResult:
        """volume >= 0, amount >= 0."""
        t0 = time.monotonic()
        violations = 0
        details: list[dict] = []

        if "volume" in df.columns:
            count = int((df["volume"] < 0).sum())
            if count > 0:
                violations += count
                details.append({
                    "rule": "volume_integrity",
                    "column": "volume",
                    "violations": count,
                })
        if "amount" in df.columns:
            count = int((df["amount"] < 0).sum())
            if count > 0:
                violations += count
                details.append({
                    "rule": "volume_integrity",
                    "column": "amount",
                    "violations": count,
                })

        return ValidationResult(
            passed=violations == 0, rule_name="volume_integrity", severity="error",
            violations=violations, details=details,
            duration_ms=(time.monotonic() - t0) * 1000.0,
        )

    # ------------------------------------------------------------------
    # Custom rules from data_quality_rules table
    # ------------------------------------------------------------------

    def _run_custom_rules(
        self, dataset: str, symbol: str, interval: str, df: pd.DataFrame,
    ) -> list[ValidationResult]:
        """Execute user-defined rules from ``data_quality_rules``."""
        results: list[ValidationResult] = []
        try:
            rules = self._fetch_custom_rules(dataset)
        except Exception as exc:
            logger.warning("Failed to fetch custom rules: %s", exc)
            return results

        for rule in rules:
            t0 = time.monotonic()
            rule_id = rule.get("rule_id", "unknown")
            rule_name = rule.get("rule_name", rule_id)
            severity = rule.get("severity", "warn")
            check_sql = rule.get("check_sql", "")
            if not check_sql:
                continue

            try:
                violations = 0
                details: list[dict] = []
                if check_sql.lower().startswith("select"):
                    import duckdb
                    rel = duckdb.from_df(df)
                    violation_df = rel.query("df_violation", check_sql).df()
                    violations = len(violation_df)
                    if violations > 0:
                        details.append({
                            "rule": rule_id, "sql": check_sql,
                            "violations": violations,
                            "sample": violation_df.head(5).to_dict(orient="records"),
                        })
                else:
                    try:
                        violation_mask = df.eval(check_sql)
                        violations = int(violation_mask.sum())
                        if violations > 0:
                            details.append({
                                "rule": rule_id, "query": check_sql,
                                "violations": violations,
                                "sample": df[violation_mask].head(5).to_dict(orient="records"),
                            })
                    except Exception:
                        import duckdb
                        rel = duckdb.from_df(df)
                        full_sql = f"SELECT * FROM df WHERE {check_sql}"
                        violation_df = rel.query("df_rule", full_sql).df()
                        violations = len(violation_df)
                        if violations > 0:
                            details.append({
                                "rule": rule_id, "query": check_sql,
                                "violations": violations,
                                "sample": violation_df.head(5).to_dict(orient="records"),
                            })

                elapsed = (time.monotonic() - t0) * 1000.0
                results.append(ValidationResult(
                    passed=violations == 0, rule_name=rule_name,
                    severity=severity, violations=violations,
                    details=details, duration_ms=elapsed,
                ))
                if not self._dry_run:
                    self._update_rule_run(rule_id, violations == 0, violations)
            except Exception as exc:
                logger.warning("Custom rule %s failed: %s", rule_id, exc)
        return results

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------

    def _quarantine_batch(
        self, dataset: str, symbol: str, df: pd.DataFrame, result: ValidationResult,
    ) -> None:
        """Write violating rows to the ``data_quarantine`` table."""
        if self._dry_run:
            logger.info("[DRY-RUN] Would quarantine %d rows from %s/%s", len(df), dataset, symbol)
            return

        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        quarantine_rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            quarantine_rows.append({
                "quarantine_id": uuid.uuid4().hex,
                "source_dataset": dataset,
                "symbol": symbol,
                "interval": str(row_dict.get("interval", "")),
                "bar_time": row_dict.get("bar_time"),
                "trade_date": row_dict.get("trade_date"),
                "reason": result.rule_name,
                "rule_id": result.rule_name,
                "original_values_json": json.dumps(row_dict, ensure_ascii=False, default=str),
                "severity": "error",
                "resolution": "unresolved",
                "resolved_by": None,
                "resolved_at": None,
                "created_at": now_str,
            })

        logger.info("Quarantining %d rows from %s/%s", len(quarantine_rows), dataset, symbol)
        try:
            insert_fn = self._store.insert_table_rows
            if asyncio.iscoroutinefunction(insert_fn):
                asyncio.run(insert_fn("data_quarantine", quarantine_rows))
            else:
                insert_fn("data_quarantine", quarantine_rows)
        except Exception as exc:
            logger.error("Failed to quarantine batch: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_store(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call a method on the store, handling sync vs async dispatch."""
        fn = getattr(self._store, method, None)
        if fn is None:
            raise AttributeError(f"Store has no method {method!r}")
        if asyncio.iscoroutinefunction(fn):
            return asyncio.run(fn(*args, **kwargs))
        return fn(*args, **kwargs)

    def _exec_sql(
        self, sql: str, params: list | None = None,
    ) -> pd.DataFrame | None:
        """Execute arbitrary SQL against the store (sync or async)."""
        if asyncio.iscoroutinefunction(getattr(self._store, "insert_table_rows", None)):
            # PGStore async path
            return asyncio.run(self._exec_sql_async(sql, params or []))
        # DuckDB sync path
        try:
            if params:
                result = self._store.conn.execute(sql, params)
            else:
                result = self._store.conn.execute(sql)
            return result.fetchdf()
        except Exception as exc:
            logger.debug("_exec_sql failed (sync): %s", exc)
            return None

    async def _exec_sql_async(self, sql: str, params: list) -> pd.DataFrame | None:
        """Execute SQL against async PGStore."""
        from sqlalchemy import text
        try:
            async with self._store._async_engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                rows = result.fetchall()
                if not rows:
                    return pd.DataFrame()
                return pd.DataFrame(rows, columns=result.keys())
        except Exception as exc:
            logger.debug("_exec_sql_async failed: %s", exc)
            return None

    def _fetch_custom_rules(self, dataset: str) -> list[dict[str, Any]]:
        """Fetch active custom rules for *dataset* from the DB."""
        sql = (
            "SELECT * FROM data_quality_rules "
            "WHERE is_active = TRUE "
            "AND (scope_dataset IS NULL OR scope_dataset = ?) "
            "ORDER BY rule_id"
        )
        df = self._exec_sql(sql, [dataset])
        if df is not None and not df.empty:
            return df.to_dict(orient="records")
        return []

    def _update_rule_run(self, rule_id: str, passed: bool, violations: int) -> None:
        """Update last_run_at and failure_count in data_quality_rules."""
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        result_str = "pass" if passed else f"fail({violations})"
        sql = (
            "UPDATE data_quality_rules SET "
            "last_run_at = ?, last_result = ?, "
            "failure_count = CASE WHEN ? THEN 0 ELSE failure_count + 1 END "
            "WHERE rule_id = ?"
        )
        self._exec_sql(sql, [now_str, result_str, passed, rule_id])

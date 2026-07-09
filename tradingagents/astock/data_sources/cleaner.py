"""Unified data cleaning layer for AStock data pipeline.

Applied automatically in ``_helpers.df_to_json`` so every WebUI data query
passes through quality checks before reaching the frontend.

Cleaning rules
--------------
- Price sanity: close/open/high/low 必须 > 0
- Volume sanity: volume ≥ 0
- Change sanity: 单日涨跌幅超过阈值（默认 ±30%）标记为可疑
- Date ordering: 按 trade_date 必须递增
- Null handling: 空值→None（已有 sanitise_records）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

MAX_DAILY_CHANGE_PCT = 30.0  # 单日涨跌幅上限


@dataclass
class CleaningReport:
    """Summary of what was cleaned in a batch."""

    total_rows: int = 0
    rows_removed: int = 0
    rows_flagged: int = 0
    price_zeros: int = 0
    volume_negative: int = 0
    change_outliers: int = 0
    date_disorder: int = 0
    details: list[str] = field(default_factory=list)

    def merge(self, other: CleaningReport) -> None:
        """Merge another report into this one."""
        self.total_rows += other.total_rows
        self.rows_removed += other.rows_removed
        self.rows_flagged += other.rows_flagged
        self.price_zeros += other.price_zeros
        self.volume_negative += other.volume_negative
        self.change_outliers += other.change_outliers
        self.date_disorder += other.date_disorder
        self.details.extend(other.details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "rows_removed": self.rows_removed,
            "rows_flagged": self.rows_flagged,
            "price_zeros": self.price_zeros,
            "volume_negative": self.volume_negative,
            "change_outliers": self.change_outliers,
            "date_disorder": self.date_disorder,
        }

    def has_issues(self) -> bool:
        return self.rows_removed > 0 or self.rows_flagged > 0


def _get(record: dict, *keys: str, default: Any = None) -> Any:
    """Get value from record by trying multiple key aliases."""
    for k in keys:
        v = record.get(k)
        if v is not None:
            return v
    return default


def clean_records(
    records: list[dict[str, Any]],
    symbol: str = "",
    max_change_pct: float = MAX_DAILY_CHANGE_PCT,
) -> tuple[list[dict[str, Any]], CleaningReport]:
    """Clean and validate a list of data records (K-line bars, etc.).

    Parameters
    ----------
    records : list[dict]
        Raw records from store or API.
    symbol : str
        Symbol for logging context.
    max_change_pct : float
        Maximum allowed single-day change % (default 30%%).

    Returns
    -------
    (cleaned_records, report)
    """
    report = CleaningReport(total_rows=len(records))
    cleaned: list[dict[str, Any]] = []
    prev_date: str | None = None

    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            cleaned.append(rec)
            continue

        issues: list[str] = []
        skip = False

        # ── 1. Price sanity ──
        for price_key in ("close", "open", "high", "low"):
            val = _get(rec, price_key, price_key.capitalize())
            if val is not None:
                try:
                    v = float(val)
                    if v <= 0:
                        issues.append(f"{price_key}={v}")
                        report.price_zeros += 1
                        skip = True  # 价格无效，整行剔除
                except (ValueError, TypeError):
                    issues.append(f"{price_key}=invalid({val})")
                    report.price_zeros += 1
                    skip = True

        if skip:
            report.rows_removed += 1
            detail = f"[{symbol}] row {i}: price invalid -> removed ({'; '.join(issues)})"
            report.details.append(detail)
            logger.debug(detail)
            continue

        # ── 2. Volume sanity ──
        vol = _get(rec, "volume", "Volume", "vol")
        if vol is not None:
            try:
                v = float(vol)
                if v < 0:
                    issues.append(f"volume={v}")
                    report.volume_negative += 1
                    rec["volume"] = 0  # 负成交量修正为 0
            except (ValueError, TypeError) as e:
                logger.debug("Operation failed: {0}", e)

        # ── 3. Change outlier detection ──
        close = _get(rec, "close", "Close")
        prev_close = _get(rec, "preclose", "pre_close", "preClose")
        change = _get(rec, "change_pct", "pctChg", "changepercent")

        if change is not None:
            try:
                cp = float(change)
                if abs(cp) > max_change_pct:
                    issues.append(f"change={cp:.2f}% > {max_change_pct}%")
                    report.change_outliers += 1
                    rec["_flagged"] = True  # 标记但不删除
            except (ValueError, TypeError) as e:
                logger.debug("Operation failed: {0}", e)
        elif close is not None and prev_close is not None:
            try:
                cp = (float(close) - float(prev_close)) / float(prev_close) * 100
                if abs(cp) > max_change_pct:
                    issues.append(f"implied_change={cp:.2f}% > {max_change_pct}%")
                    report.change_outliers += 1
                    rec["_flagged"] = True
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.debug("Operation failed: {0}", e)

        # ── 4. Date ordering check ──
        trade_date = _get(rec, "trade_date", "date", "datetime", "time", default="")
        if trade_date and prev_date is not None:
            if trade_date < prev_date:
                issues.append(f"date_disorder: {trade_date} < {prev_date}")
                report.date_disorder += 1
        if trade_date:
            prev_date = str(trade_date)

        if issues:
            report.rows_flagged += 1
            detail = f"[{symbol}] row {i}: {'; '.join(issues)}"
            report.details.append(detail)
            logger.debug(detail)

        cleaned.append(rec)

    return cleaned, report


def clean_kline_bars(
    bars: list[dict[str, Any]],
    symbol: str = "",
) -> tuple[list[dict[str, Any]], CleaningReport]:
    """Convenience wrapper for cleaning K-line bar data."""
    return clean_records(bars, symbol=symbol)


def summary_text(report: CleaningReport) -> str:
    """Short human-readable cleaning summary."""
    if not report.has_issues():
        return ""
    parts = []
    if report.rows_removed:
        parts.append(f"removed {report.rows_removed}")
    if report.price_zeros:
        parts.append(f"zero-price {report.price_zeros}")
    if report.change_outliers:
        parts.append(f"outliers {report.change_outliers}")
    if report.volume_negative:
        parts.append(f"neg-vol {report.volume_negative}")
    if report.date_disorder:
        parts.append(f"disordered {report.date_disorder}")
    return f"🧹 {'; '.join(parts)}" if parts else ""

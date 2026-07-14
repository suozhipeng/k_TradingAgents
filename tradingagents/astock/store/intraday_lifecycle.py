"""Safe hot/cold lifecycle management for intraday K-line data.

Old minute bars are first exported as immutable monthly Parquet partitions.
Only after the exported row count is verified can the corresponding hot-store
rows be deleted.  Callers must explicitly opt in to deletion.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_INTRADAY = ("1m", "5m", "15m", "30m", "60m")
_SAFE_SYMBOL = re.compile(r"[^A-Za-z0-9._-]")


def _refresh_cold_view(conn: Any, archive_root: Path) -> None:
    """Expose verified Parquet minute archives through a stable DuckDB view."""
    pattern = str((archive_root / "interval=*" / "symbol=*" / "month=*" / "bars.parquet").resolve())
    escaped = pattern.replace("'", "''")
    conn.execute(
        "CREATE OR REPLACE VIEW kline_bars_cold AS "
        "SELECT * FROM read_parquet('" + escaped + "', union_by_name=true)"
    )


def archive_intraday_kline(
    store: Any, *, retention_days: int = 180, archive_dir: str | Path = "kline/archive",
    delete_hot_rows: bool = False, today: date | None = None,
) -> dict[str, Any]:
    """Preview or archive minute bars older than the hot-data retention window."""
    raw = getattr(store, "_store", store)
    conn = getattr(raw, "conn", None)
    if conn is None:
        raise RuntimeError("intraday lifecycle requires a DuckDB-backed store")
    cutoff = (today or date.today()) - timedelta(days=max(1, int(retention_days)))
    partitions = conn.execute(
        '''SELECT symbol, "interval", date_trunc('month', bar_time) AS month, count(*) AS rows
           FROM kline_bars
           WHERE "interval" IN ('1m','5m','15m','30m','60m') AND bar_time < ?
           GROUP BY symbol, "interval", month ORDER BY month, symbol''', [cutoff],
    ).fetchall()
    summary = {"cutoff": cutoff.isoformat(), "delete_hot_rows": delete_hot_rows,
               "partitions": [], "rows_archived": 0, "rows_deleted": 0}
    if not delete_hot_rows:
        summary["partitions"] = [
            {"symbol": s, "interval": i, "month": str(m)[:7], "rows": n} for s, i, m, n in partitions
        ]
        summary["rows_eligible"] = sum(p[3] for p in partitions)
        return summary

    root = Path(archive_dir)
    for symbol, interval, month, expected in partitions:
        month_start = month.date() if hasattr(month, "date") else date.fromisoformat(str(month)[:10])
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        target = root / f"interval={interval}" / f"symbol={_SAFE_SYMBOL.sub('_', symbol)}" / f"month={month_start:%Y-%m}"
        target.mkdir(parents=True, exist_ok=True)
        output = target / "bars.parquet"
        if output.exists():
            raise RuntimeError(f"archive already exists, refusing to overwrite: {output}")
        # DuckDB's parquet glob handling ignores dot-prefixed files on some
        # platforms, so keep the verification artifact visibly named.
        temporary = target / f"{uuid.uuid4().hex}.tmp.parquet"
        destination = str(temporary).replace("'", "''")
        conn.execute(
            "COPY (SELECT * FROM kline_bars WHERE symbol = ? AND \"interval\" = ? AND bar_time >= ? AND bar_time < ?) "
            f"TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD)",
            [symbol, interval, month_start, next_month],
        )
        actual = conn.execute("SELECT count(*) FROM read_parquet(?)", [str(temporary)]).fetchone()[0]
        if actual != expected:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"archive verification failed for {symbol} {interval} {month_start:%Y-%m}: {actual} != {expected}")
        temporary.replace(output)
        conn.execute(
            'DELETE FROM kline_bars WHERE symbol = ? AND "interval" = ? AND bar_time >= ? AND bar_time < ?',
            [symbol, interval, month_start, next_month],
        )
        summary["partitions"].append({"symbol": symbol, "interval": interval, "month": f"{month_start:%Y-%m}", "rows": expected, "path": str(output)})
        summary["rows_archived"] += expected
        summary["rows_deleted"] += expected
    if summary["rows_archived"]:
        _refresh_cold_view(conn, root)
        summary["cold_view"] = "kline_bars_cold"
    return summary

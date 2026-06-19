"""Shared helpers for AStock API route files — NaN sanitisation and JSON conversion."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any


def sanitise_records(records: list[dict[str, Any]]) -> None:
    """Replace NaN/Inf with None and format datetimes in-place for valid JSON."""
    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
            elif isinstance(v, datetime):
                if v.hour == 0 and v.minute == 0 and v.second == 0:
                    record[k] = v.strftime("%Y-%m-%d")
                else:
                    record[k] = v.strftime("%Y-%m-%d %H:%M")
            elif hasattr(v, "isoformat"):
                record[k] = v.isoformat()


def df_to_json(df: Any) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame to a list of plain dicts, sanitising NaN/Inf for valid JSON."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    if hasattr(df, "to_dict"):
        records = df.to_dict(orient="records")
        sanitise_records(records)
        return records
    return list(df)

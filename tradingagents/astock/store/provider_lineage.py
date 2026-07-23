"""Field-level lineage — track provider, API, and upstream for every field."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def record_field_lineage(
    conn,
    *,
    provider: str,
    provider_api: str,
    upstream_source: str | None,
    source_symbol: str | None,
    source_field: str,
    normalized_field: str,
    as_of: str,
    quality_tag: str = "normal",
    ingestion_run_id: str | None = None,
) -> str:
    """Insert one field-level lineage record.  Returns lineage_id."""
    conn.execute("""CREATE TABLE IF NOT EXISTS provider_field_lineage (
        lineage_id VARCHAR PRIMARY KEY,
        provider VARCHAR, provider_api VARCHAR, upstream_source VARCHAR,
        source_symbol VARCHAR, source_field VARCHAR, normalized_field VARCHAR,
        as_of VARCHAR, quality_tag VARCHAR, ingestion_run_id VARCHAR,
        raw_hash VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    seed = f"{provider}:{provider_api}:{source_field}:{normalized_field}:{as_of}"
    lineage_id = "l_" + hashlib.sha256(seed.encode()).hexdigest()[:16]
    conn.execute("""DELETE FROM provider_field_lineage WHERE lineage_id = ?""", [lineage_id])
    conn.execute("""INSERT INTO provider_field_lineage
        (lineage_id, provider, provider_api, upstream_source, source_symbol,
         source_field, normalized_field, as_of, quality_tag, ingestion_run_id, raw_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", [
        lineage_id, provider, provider_api, upstream_source, source_symbol,
        source_field, normalized_field, as_of, quality_tag, ingestion_run_id,
        hashlib.sha256(json.dumps({provider_api: as_of}, sort_keys=True).encode()).hexdigest()[:12],
    ])
    conn.commit()
    return lineage_id

"""Cninfo local import — process pre-downloaded official announcement files.

Manifests must contain: announcement_id, symbol, title, announcement_type,
publish_time, source_url, local_path, file_sha256.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def import_announcement(conn, manifest: dict[str, Any],
                        announcing_dir: str | Path | None = None) -> str | None:
    """Import one official announcement from a manifest entry.

    Returns announcement_id on success, None on failure.
    """
    conn.execute("""CREATE TABLE IF NOT EXISTS announcement_documents (
        announcement_id VARCHAR PRIMARY KEY, symbol VARCHAR, title VARCHAR,
        announcement_type VARCHAR, publish_date DATE, report_period VARCHAR,
        source_url VARCHAR, local_path VARCHAR, file_sha256 VARCHAR,
        source VARCHAR DEFAULT 'cninfo', parse_state VARCHAR DEFAULT 'pending',
        imported_at TIMESTAMP
    )""")
    aid = manifest.get("announcement_id")
    if not aid:
        logger.warning("manifest missing announcement_id")
        return None

    local_path = manifest.get("local_path", "")
    file_sha256 = manifest.get("file_sha256", "")
    if local_path and not file_sha256:
        # Compute hash if not provided
        p = Path(local_path)
        if p.is_file():
            file_sha256 = hashlib.sha256(p.read_bytes()).hexdigest()

    conn.execute("DELETE FROM announcement_documents WHERE announcement_id = ?", [aid])
    conn.execute("""INSERT INTO announcement_documents
        (announcement_id, symbol, title, announcement_type, publish_date,
         report_period, source_url, local_path, file_sha256, source)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", [
        aid,
        manifest.get("symbol", ""),
        manifest.get("title", ""),
        manifest.get("announcement_type", ""),
        manifest.get("publish_time", "")[:10],
        manifest.get("report_period", ""),
        manifest.get("source_url", ""),
        local_path,
        file_sha256,
        "cninfo",
    ])
    conn.commit()
    return aid


def import_manifest_directory(conn, manifest_dir: str | Path) -> dict[str, Any]:
    """Import all JSON manifests from a directory. Returns summary."""
    md = Path(manifest_dir)
    if not md.is_dir():
        return {"imported": 0, "failed": 0, "error": f"directory not found: {manifest_dir}"}

    imported = 0
    failed = 0
    for f in sorted(md.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                if import_announcement(conn, entry) is not None:
                    imported += 1
                else:
                    failed += 1
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("failed to import %s: %s", f.name, exc)
            failed += 1
    return {"imported": imported, "failed": failed, "manifest_dir": str(md)}

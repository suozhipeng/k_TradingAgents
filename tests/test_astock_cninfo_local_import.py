"""Tests for Cninfo local import."""

import json
import tempfile
from pathlib import Path

import duckdb

from tradingagents.astock.data_sources.cninfo_importer import (
    import_announcement, import_manifest_directory,
)


def _manifest(symbol="600519.SH"):
    return {
        "announcement_id": f"ann_{symbol}_20260722_001",
        "symbol": symbol,
        "title": "Test announcement",
        "announcement_type": "periodic_report",
        "publish_time": "2026-07-22",
        "report_period": "2026Q2",
        "source_url": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600519",
        "local_path": "",
        "file_sha256": "abc123",
    }


def test_import_announcement():
    conn = duckdb.connect(":memory:")
    aid = import_announcement(conn, _manifest())
    assert aid == "ann_600519.SH_20260722_001"
    assert conn.execute("SELECT COUNT(*) FROM announcement_documents").fetchone()[0] == 1


def test_import_announcement_idempotent():
    conn = duckdb.connect(":memory:")
    import_announcement(conn, _manifest())
    import_announcement(conn, _manifest())
    assert conn.execute("SELECT COUNT(*) FROM announcement_documents").fetchone()[0] == 1


def test_import_manifest_directory():
    conn = duckdb.connect(":memory:")
    with tempfile.TemporaryDirectory() as td:
        manifest_path = Path(td) / "test_manifest.json"
        manifest_path.write_text(json.dumps([
            _manifest("600519.SH"),
            _manifest("000858.SZ"),
        ]))
        result = import_manifest_directory(conn, td)
    assert result["imported"] == 2
    assert conn.execute("SELECT COUNT(*) FROM announcement_documents").fetchone()[0] == 2


def test_import_no_announcement_id():
    conn = duckdb.connect(":memory:")
    result = import_announcement(conn, {"title": "bad"})
    assert result is None

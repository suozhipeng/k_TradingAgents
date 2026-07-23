"""Dedicated tests for field-level lineage recording and querying."""

import duckdb
from tradingagents.astock.store.provider_lineage import record_field_lineage


def test_lineage_records_minimal_fields():
    conn = duckdb.connect(":memory:")
    lid = record_field_lineage(
        conn, provider="tushare", provider_api="daily_basic",
        upstream_source="tushare", source_symbol="600519.SH",
        source_field="pe_ttm", normalized_field="pe_ttm",
        as_of="2026-07-22",
    )
    assert lid.startswith("l_")
    assert conn.execute("SELECT normalized_field FROM provider_field_lineage").fetchone()[0] == "pe_ttm"


def test_lineage_records_quality_tag():
    conn = duckdb.connect(":memory:")
    record_field_lineage(
        conn, provider="akshare", provider_api="stock_zh_a_hist",
        upstream_source="eastmoney", source_symbol="600519",
        source_field="close", normalized_field="close",
        as_of="2026-07-22", quality_tag="fallback",
    )
    assert conn.execute("SELECT quality_tag FROM provider_field_lineage").fetchone()[0] == "fallback"


def test_lineage_idempotent_same_input():
    conn = duckdb.connect(":memory:")
    lid1 = record_field_lineage(
        conn, provider="tushare", provider_api="daily_basic",
        upstream_source="tushare", source_symbol="000001.SZ",
        source_field="pb", normalized_field="pb",
        as_of="2026-07-22",
    )
    lid2 = record_field_lineage(
        conn, provider="tushare", provider_api="daily_basic",
        upstream_source="tushare", source_symbol="000001.SZ",
        source_field="pb", normalized_field="pb",
        as_of="2026-07-22",
    )
    assert lid1 == lid2
    assert conn.execute("SELECT COUNT(*) FROM provider_field_lineage").fetchone()[0] == 1


def test_lineage_distinct_fields():
    conn = duckdb.connect(":memory:")
    record_field_lineage(
        conn, provider="tushare", provider_api="daily_basic",
        upstream_source="tushare", source_symbol="600519.SH",
        source_field="pe_ttm", normalized_field="pe_ttm",
        as_of="2026-07-22",
    )
    record_field_lineage(
        conn, provider="akshare", provider_api="stock_zh_a_hist",
        upstream_source="eastmoney", source_symbol="600519",
        source_field="close", normalized_field="close",
        as_of="2026-07-22",
    )
    assert conn.execute("SELECT COUNT(*) FROM provider_field_lineage").fetchone()[0] == 2

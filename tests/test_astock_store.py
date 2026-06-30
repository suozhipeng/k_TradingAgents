"""Tests for the AStock DuckDB local database storage layer (Phase 12).

Run::
    cd /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents
    python3 -m pytest tests/test_astock_store.py -v
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tempfile
from datetime import date
from pathlib import Path

# Add repo root so we can import directly (avoid full __init__ chain)
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import duckdb
import pandas as pd
import pytest

# Check if parquet support is available (pyarrow or fastparquet)
try:
    import pyarrow  # noqa: F401
    _HAS_PARQUET = True
except ImportError:
    try:
        import fastparquet  # noqa: F401
        _HAS_PARQUET = True
    except ImportError:
        _HAS_PARQUET = False

from tradingagents.astock.store.schema import AStockStore, init_astock_db
from tradingagents.astock.store.loader import KlineLoader, ValuationLoader, BatchLoader
from tradingagents.astock.store import schema_defs
from tradingagents.astock.store.pg_store import ALL_MODEL_CLASSES


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def store() -> AStockStore:
    """Return an in-memory AStockStore with schema initialised."""
    s = AStockStore(":memory:")
    s.connect()
    s.init_schema()
    yield s
    s.close()


@pytest.fixture
def sample_kline_df() -> pd.DataFrame:
    """Sample K-line data for testing."""
    return pd.DataFrame(
        {
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
            "open": [10.0, 10.5, 10.3],
            "high": [11.0, 11.2, 10.8],
            "low": [9.8, 10.1, 10.0],
            "close": [10.5, 10.3, 10.7],
            "volume": [100000.0, 120000.0, 95000.0],
            "amount": [1050000.0, 1250000.0, 1020000.0],
            "turnover_rate": [0.01, 0.012, 0.009],
        }
    )


@pytest.fixture
def sample_valuation_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": [date(2024, 1, 2), date(2024, 1, 3)],
            "pe": [15.0, 14.5],
            "pb": [1.8, 1.7],
            "market_cap": [1e10, 9.8e9],
        }
    )


@pytest.fixture
def sample_order_book_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-02 09:30:00", "2024-01-02 09:30:05"]
            ),
            "bid_price": [10.0, 10.05],
            "bid_volume": [1000.0, 1500.0],
            "ask_price": [10.1, 10.15],
            "ask_volume": [800.0, 1200.0],
        }
    )


@pytest.fixture
def sample_trade_tape_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-02 09:30:01", "2024-01-02 09:30:02"]
            ),
            "price": [10.05, 10.07],
            "volume": [100.0, 200.0],
            "direction": ["buy", "sell"],
        }
    )


# ===================================================================
# 1. Schema initialisation
# ===================================================================


def test_init_schema(store: AStockStore) -> None:
    """Verify all managed tables exist after init_schema (currently 31 tables)."""
    tables = store.list_tables()
    expected = [
        "database_storage_profiles",
        "security_master",
        "trading_calendar",
        "security_status_history",
        "industry_classification_history",
        "suspension_events",
        "price_limit_rules",
        "kline_bars",
        "valuations",
        "corporate_actions",
        "adjust_factors",
        "order_book_snapshots",
        "trade_tape",
        "research_reports",
        "news_items",
        "announcements",
        "backtest_results",
        "paper_trades",
        "market_indicators",
        "technical_indicators",
        "data_sources",
        "data_quality_checks",
        "data_snapshots",
        "data_partitions",
        "data_ingestion_jobs",
        "data_ingestion_job_events",
        "migration_versions",
        "audit_log",
        "api_keys",
        "data_quality_rules",
        "data_quarantine",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"
    assert len(tables) == len(expected)


def test_orm_column_order_matches_schema_defs() -> None:
    """PostgreSQL ORM declarations preserve the schema_defs SSOT order."""
    models = {cls.__tablename__: cls for cls in ALL_MODEL_CLASSES}
    assert set(models) == set(schema_defs.TABLE_DEFS)

    for table_name, table_def in schema_defs.TABLE_DEFS.items():
        model_columns = [column.name for column in models[table_name].__table__.columns]
        assert model_columns == table_def.column_names, table_name

        model_pk = [column.name for column in models[table_name].__table__.primary_key.columns]
        assert model_pk == table_def.primary_key, table_name


def test_drop_all_tables(store: AStockStore) -> None:
    """drop_all_tables removes all managed tables."""
    assert len(store.list_tables()) == 31
    store.drop_all_tables()
    assert store.list_tables() == []


def test_table_exists(store: AStockStore) -> None:
    assert store.table_exists("kline_bars")
    assert not store.table_exists("nonexistent_table")


# ===================================================================
# 2. K-line insert and query
# ===================================================================


def test_insert_and_query_kline(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    count = store.insert_kline("000001.SZ", sample_kline_df)
    assert count == 3

    df = store.query_kline("000001.SZ")
    assert len(df) == 3
    assert list(df["close"]) == [10.5, 10.3, 10.7]


def test_insert_kline_empty(store: AStockStore) -> None:
    count = store.insert_kline("000001.SZ", pd.DataFrame())
    assert count == 0


def test_insert_kline_with_date_filter(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    df = store.query_kline("000001.SZ", start="2024-01-03", end="2024-01-04")
    assert len(df) == 2
    # DuckDB DATE columns are returned as Timestamp by fetchdf()
    assert str(df.iloc[0]["trade_date"]).startswith("2024-01-03")


def test_insert_kline_different_intervals(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    """K-line for different intervals should not overlap."""
    store.insert_kline("000001.SZ", sample_kline_df, interval="1d")
    store.insert_kline("000001.SZ", sample_kline_df, interval="1w")
    df_1d = store.query_kline("000001.SZ", interval="1d")
    df_1w = store.query_kline("000001.SZ", interval="1w")
    assert len(df_1d) == 3
    assert len(df_1w) == 3


# ===================================================================
# 3. INSERT OR REPLACE dedup
# ===================================================================


def test_insert_or_replace_dedup(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    """Inserting the same primary key twice should upsert, not duplicate."""
    store.insert_kline("000001.SZ", sample_kline_df)
    count1 = len(store.query_kline("000001.SZ"))

    # Insert again with updated close
    df2 = sample_kline_df.copy()
    df2["close"] = [99.0, 99.5, 99.9]
    store.insert_kline("000001.SZ", df2)
    count2 = len(store.query_kline("000001.SZ"))

    # Should still be 3 rows
    assert count1 == 3
    assert count2 == 3

    # Check that close was updated
    df_check = store.query_kline("000001.SZ")
    assert list(df_check["close"]) == [99.0, 99.5, 99.9]


def test_valuations_dedup(store: AStockStore, sample_valuation_df: pd.DataFrame) -> None:
    store.insert_valuations("000001.SZ", sample_valuation_df)
    assert len(store.query_valuations("000001.SZ")) == 2

    df2 = sample_valuation_df.copy()
    df2["pe"] = [99.0, 88.0]
    store.insert_valuations("000001.SZ", df2)
    df_check = store.query_valuations("000001.SZ")
    assert len(df_check) == 2
    assert list(df_check["pe"]) == [99.0, 88.0]


# ===================================================================
# 4. Valuations
# ===================================================================


def test_insert_and_query_valuations(store: AStockStore, sample_valuation_df: pd.DataFrame) -> None:
    count = store.insert_valuations("000001.SZ", sample_valuation_df)
    assert count == 2

    df = store.query_valuations("000001.SZ")
    assert len(df) == 2

    # Date filter
    df2 = store.query_valuations("000001.SZ", start="2024-01-03")
    assert len(df2) == 1
    assert df2.iloc[0]["pe"] == 14.5


# ===================================================================
# 5. Order book & trade tape
# ===================================================================


def test_insert_order_book(store: AStockStore, sample_order_book_df: pd.DataFrame) -> None:
    count = store.insert_order_book_snapshot("000001.SZ", sample_order_book_df)
    assert count == 2

    df = store.query_order_book("000001.SZ")
    assert len(df) == 2
    assert list(df["bid_price"]) == [10.0, 10.05]


def test_insert_trade_tape(store: AStockStore, sample_trade_tape_df: pd.DataFrame) -> None:
    count = store.insert_trade_tape("000001.SZ", sample_trade_tape_df)
    assert count == 2

    df = store.query_trade_tape("000001.SZ")
    assert len(df) == 2
    assert list(df["direction"]) == ["buy", "sell"]


# ===================================================================
# 6. Research reports, news, announcements
# ===================================================================


def test_insert_research_reports(store: AStockStore) -> None:
    df = pd.DataFrame(
        [
            {
                "report_date": date(2024, 1, 5),
                "title": "Buy Rating on 000001",
                "institution": "CICC",
                "analyst": "Zhang",
                "rating": "buy",
                "pdf_url": "http://example.com/r1.pdf",
            }
        ]
    )
    count = store.insert_research_reports("000001.SZ", df, source="test")
    assert count == 1

    result = store.query_research_reports("000001.SZ")
    assert len(result) == 1
    assert result.iloc[0]["rating"] == "buy"


def test_insert_news_items(store: AStockStore) -> None:
    df = pd.DataFrame(
        [
            {
                "publish_date": date(2024, 1, 5),
                "title": "Market Update",
                "summary": "Market summary text",
                "url": "http://example.com/news1",
            }
        ]
    )
    count = store.insert_news_items("000001.SZ", df, source="test")
    assert count == 1

    result = store.query_news_items("000001.SZ")
    assert len(result) == 1
    assert result.iloc[0]["title"] == "Market Update"


def test_insert_announcements(store: AStockStore) -> None:
    df = pd.DataFrame(
        [
            {
                "publish_date": date(2024, 1, 5),
                "title": "Board Meeting Notice",
                "summary": "Summary of board decision",
                "url": "http://example.com/ann1",
            }
        ]
    )
    count = store.insert_announcements("000001.SZ", df)
    assert count == 1

    result = store.query_announcements("000001.SZ")
    assert len(result) == 1
    assert "Board" in result.iloc[0]["title"]


# ===================================================================
# 7. Market indicators
# ===================================================================


def test_insert_market_indicators(store: AStockStore) -> None:
    df = pd.DataFrame(
        [
            {
                "trade_date": date(2024, 1, 2),
                "ma_5": 10.2,
                "ma_20": 9.8,
                "ma_60": 9.5,
                "rsi_14": 55.0,
                "atr_14": 0.5,
                "volume_ma_5": 100000.0,
            }
        ]
    )
    count = store.insert_market_indicators("000001.SZ", df)
    assert count == 1

    result = store.query_market_indicators("000001.SZ")
    assert len(result) == 1
    assert result.iloc[0]["rsi_14"] == 55.0


# ===================================================================
# 8. Backtest results
# ===================================================================


def test_store_and_get_backtest_results(store: AStockStore) -> None:
    result = {
        "run_id": "bt-001",
        "symbol": "000001.SZ",
        "strategy_name": "ma_trend",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "total_return": 0.15,
        "annualized_return": 0.12,
        "sharpe_ratio": 1.5,
        "max_drawdown": -0.1,
        "win_rate": 0.6,
        "total_trades": 20,
    }
    count = store.store_backtest_result(result)
    assert count == 1

    df = store.get_backtest_results()
    assert len(df) == 1
    assert df.iloc[0]["run_id"] == "bt-001"

    # Filter by strategy
    df2 = store.get_backtest_results(strategy_name="ma_trend")
    assert len(df2) == 1

    df3 = store.get_backtest_results(strategy_name="nonexistent")
    assert len(df3) == 0


# ===================================================================
# 9. Paper trades
# ===================================================================


def test_store_and_get_paper_trades(store: AStockStore) -> None:
    trade = {
        "trade_id": "pt-001",
        "symbol": "000001.SZ",
        "direction": "buy",
        "price": 10.5,
        "volume": 1000.0,
        "fees": 5.0,
        "trade_date": "2024-01-02",
        "strategy_name": "test_strat",
        "actionable": False,
        "decision_scope": "paper_trading_only",
    }
    count = store.store_paper_trade(trade)
    assert count == 1

    df = store.get_paper_trades()
    assert len(df) == 1
    assert df.iloc[0]["trade_id"] == "pt-001"

    # Filter by symbol
    df2 = store.get_paper_trades(symbol="000001.SZ")
    assert len(df2) == 1

    df3 = store.get_paper_trades(symbol="600000.SH")
    assert len(df3) == 0


# ===================================================================
# 10. Export / Import
# ===================================================================


def test_export_csv(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        tmp_path = f.name

    try:
        result = store.export_table("kline_bars", fmt="csv", output_path=tmp_path)
        assert os.path.exists(result)
        with open(result, "r") as fh:
            lines = fh.readlines()
        # header + 3 data rows
        assert len(lines) >= 4
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_export_json(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    try:
        result = store.export_table("kline_bars", fmt="json", output_path=tmp_path)
        assert os.path.exists(result)
        # DuckDB JSON export is NDJSON (one JSON object per line)
        with open(result, "r") as fh:
            lines = fh.readlines()
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line.strip())
            assert obj["symbol"] == "000001.SZ"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@pytest.mark.skipif(
    not _HAS_PARQUET,
    reason="Requires pyarrow or fastparquet for parquet support",
)
def test_export_parquet(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        tmp_path = f.name

    try:
        result = store.export_table("kline_bars", fmt="parquet", output_path=tmp_path)
        assert os.path.exists(result)
        # Verify we can read it back
        df_read = pd.read_parquet(result)
        assert len(df_read) == 3
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_import_csv(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    # Export to CSV first, then import into a fresh store
    store.insert_kline("000001.SZ", sample_kline_df)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        tmp_path = f.name

    try:
        store.export_table("kline_bars", fmt="csv", output_path=tmp_path)

        # Create a new store and import
        store2 = AStockStore(":memory:")
        store2.connect()
        store2.init_schema()

        count = store2.import_table("kline_bars", fmt="csv", file_path=tmp_path)
        assert count == 3

        df = store2.query_kline("000001.SZ")
        assert len(df) == 3
        assert list(df["close"]) == [10.5, 10.3, 10.7]

        store2.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@pytest.mark.skipif(
    not _HAS_PARQUET,
    reason="Requires pyarrow or fastparquet for parquet support",
)
def test_import_parquet(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        tmp_path = f.name

    try:
        store.export_table("kline_bars", fmt="parquet", output_path=tmp_path)

        store2 = AStockStore(":memory:")
        store2.connect()
        store2.init_schema()

        count = store2.import_table("kline_bars", fmt="parquet", file_path=tmp_path)
        assert count == 3

        store2.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_export_unknown_table(store: AStockStore) -> None:
    with pytest.raises(ValueError, match="Unknown table"):
        store.export_table("nonexistent", fmt="csv")


def test_export_unknown_format(store: AStockStore) -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        store.export_table("kline_bars", fmt="xlsx")


# ===================================================================
# 11. Table stats
# ===================================================================


def test_get_table_stats(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    stats = store.get_table_stats()
    assert stats["kline_bars"]["rows"] == 0

    store.insert_kline("000001.SZ", sample_kline_df)
    stats = store.get_table_stats()
    assert stats["kline_bars"]["rows"] == 3
    assert stats["kline_bars"]["latest_date"] is not None


# ===================================================================
# 12. Vacuum
# ===================================================================


def test_vacuum(store: AStockStore) -> None:
    # Vacuum should not raise
    store.vacuum()


# ===================================================================
# 13. Raw SQL query
# ===================================================================


def test_query_sql(store: AStockStore, sample_kline_df: pd.DataFrame) -> None:
    store.insert_kline("000001.SZ", sample_kline_df)
    store.insert_kline("600000.SH", sample_kline_df)

    df = store.query_sql(
        "SELECT symbol, count(*) as cnt FROM kline_bars GROUP BY symbol ORDER BY symbol"
    )
    assert len(df) == 2
    assert list(df["cnt"]) == [3, 3]


# ===================================================================
# 14. Thread-safety (concurrent writes)
# ===================================================================


def test_concurrent_writes(store: AStockStore) -> None:
    """Multiple threads writing to the same table should not corrupt data."""
    n_threads = 5
    rows_per_thread = 20
    results: list[int] = [0] * n_threads

    def _write(thread_id: int) -> None:
        symbol = f"CONCUR.{thread_id:04d}"
        for i in range(rows_per_thread):
            df = pd.DataFrame(
                [
                    {
                        "trade_date": date(2024, 1, 2 + i),
                        "open": 10.0 + i,
                        "high": 11.0 + i,
                        "low": 9.0 + i,
                        "close": 10.5 + i,
                        "volume": 100000.0,
                        "amount": 1050000.0,
                        "turnover_rate": 0.01,
                    }
                ]
            )
            store.insert_kline(symbol, df)

    threads = [
        threading.Thread(target=_write, args=(tid,)) for tid in range(n_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Each thread wrote rows_per_thread unique rows (different symbols → unique PK)
    total = store.query_sql("SELECT count(*) as cnt FROM kline_bars")
    assert total.iloc[0]["cnt"] == n_threads * rows_per_thread


# ===================================================================
# 15. init_astock_db factory
# ===================================================================


def test_init_astock_db_factory() -> None:
    store = init_astock_db(":memory:")
    assert store.db_path == ":memory:"
    assert len(store.list_tables()) == 31
    store.close()


# ===================================================================
# 16. BacktestResult Pydantic model storage
# ===================================================================


@pytest.mark.skipif(
    not os.environ.get("TEST_PYDANTIC_BT"),
    reason="Only run when TEST_PYDANTIC_BT=1 (requires BacktestResult import)",
)
def test_store_backtest_result_model() -> None:
    """Store a BacktestResult Pydantic model instance."""
    from tradingagents.astock.execution import BacktestResult

    store = AStockStore(":memory:")
    store.connect()
    store.init_schema()

    bt = BacktestResult(
        symbol="000001.SZ",
        start_date="2024-01-01",
        end_date="2024-12-31",
        total_return=0.1,
        annualized_return=0.08,
        sharpe_ratio=1.2,
        max_drawdown=-0.05,
        win_rate=0.55,
        total_trades=15,
    )
    bt.run_id = "bt-model-001"  # type: ignore[attr-defined]
    count = store.store_backtest_result(bt)
    assert count == 1

    df = store.get_backtest_results()
    assert len(df) == 1
    assert df.iloc[0]["run_id"] == "bt-model-001"

    store.close()


# ===================================================================
# Phase 13: Commercial-grade additions (new tables)
# ===================================================================


def test_new_tables_exist(store: AStockStore) -> None:
    """Verify Phase 13 tables are created by init_schema."""
    tables = store.list_tables()
    for t in ("migration_versions", "audit_log", "api_keys", "data_quality_rules", "data_quarantine"):
        assert t in tables, f"Missing Phase 13 table: {t}"


def test_migration_engine(store: AStockStore) -> None:
    """Apply a trivial migration and verify it's tracked."""
    store._MIGRATIONS = []
    store._MIGRATIONS.append(
        ("test_v1", "Test: create temp table", "CREATE TABLE IF NOT EXISTS _mig_test (x INTEGER)", "DROP TABLE IF EXISTS _mig_test")
    )

    results = store.migrate()
    assert len(results) == 1
    assert results[0]["version_id"] == "test_v1"
    assert results[0]["status"] == "applied"

    results2 = store.migrate()
    assert len(results2) == 0

    df = store.list_migrations()
    assert len(df) == 1
    assert df.iloc[0]["version_id"] == "test_v1"

    store.conn.execute("DROP TABLE IF EXISTS _mig_test")
    store._MIGRATIONS = []


def test_migration_rollback(store: AStockStore) -> None:
    """Roll back a migration that has rollback_sql."""
    store._MIGRATIONS = []
    store._MIGRATIONS.append(
        ("test_rollback_v1", "Rollback test", "CREATE TABLE IF NOT EXISTS _mig_rb (y VARCHAR)", "DROP TABLE IF EXISTS _mig_rb")
    )
    store.migrate()
    store.rollback_migration("test_rollback_v1")
    assert not store.table_exists("_mig_rb")
    store._MIGRATIONS = []


def test_audit_log(store: AStockStore) -> None:
    """Write and query audit log entries."""
    eid = store.store_audit_log(
        event_type="data_import",
        action="import_kline",
        actor="system",
        resource_type="kline_bars",
        resource_id="000001.SZ",
        detail={"rows": 250},
        outcome="success",
    )
    assert eid

    df = store.query_audit_log(actor="system")
    assert len(df) == 1
    assert df.iloc[0]["event_type"] == "data_import"

    df2 = store.query_audit_log(resource_type="kline_bars")
    assert len(df2) == 1


def test_api_keys(store: AStockStore) -> None:
    """CRUD for API keys."""
    import hashlib
    key = "sk-test-secret-123"
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    kid = store.add_api_key(
        key_hash=key_hash,
        key_prefix="sk-test",
        label="Test Key",
        role="readonly",
        owner="tester",
        allowed_capabilities="kline,valuation",
        rate_limit=50,
    )
    assert kid

    record = store.validate_api_key(key_hash)
    assert record is not None
    assert record["role"] == "readonly"
    assert record["rate_limit"] == 50

    bad = store.validate_api_key("nonexistent")
    assert bad is None

    store.revoke_api_key(kid)
    revoked = store.validate_api_key(key_hash)
    assert revoked is None


def test_quality_rules(store: AStockStore) -> None:
    """Register and run a quality rule."""
    df = pd.DataFrame({
        "trade_date": [date(2024, 1, 2)],
        "open": [10.0], "high": [11.0], "low": [9.0], "close": [10.5],
        "volume": [100000.0],
    })
    store.insert_kline("000001.SZ", df)

    rid = store.store_quality_rule(
        rule_name="check:negative_close",
        description="Flag negative close prices",
        scope_dataset="kline_bars",
        check_sql="SELECT '000001.SZ' as symbol, '1d' as interval, 0 as violations WHERE 1=0",
        severity="warn",
    )
    assert rid

    result = store.run_quality_rule(rid)
    assert result["status"] in ("pass", "warn")

    all_results = store.run_all_quality_rules()
    assert len(all_results) >= 1


def test_quarantine(store: AStockStore) -> None:
    """Store and resolve quarantined records."""
    qid = store.store_quarantine(
        source_dataset="kline_bars",
        symbol="000001.SZ",
        interval="1d",
        reason="Negative price detected",
        original_values={"close": -1.0, "volume": 1000},
        severity="error",
    )
    assert qid

    df = store.query_quarantine(severity="error")
    assert len(df) == 1
    assert df.iloc[0]["resolution"] == "unresolved"

    store.resolve_quarantine(qid, resolved_by="admin")
    df2 = store.query_quarantine(severity="error", resolution="resolved")
    assert len(df2) == 1

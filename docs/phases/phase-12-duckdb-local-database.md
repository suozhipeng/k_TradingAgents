# Phase 12：DuckDB 本地数据库 — 结构化存储层

## 元数据

- Status: `complete`
- Started: `2026-06-14`
- Completed: `2026-06-15`
- Owner: `Hermes (DeepSeek)`
- Git branch: `xg_dev`
- Commit SHA: `94d9fbe`

## 产品目标

Add a DuckDB-backed local database (`AStockStore`) as the canonical local storage layer for all A-share data. Previously, all data lived transiently in in-memory caches or was discarded after each run. This phase introduces persistent, queryable storage with a dedicated CLI tool for import/export, inspection, and maintenance — enabling data retention across runs for backtest reuse, analyst inspection, and offline analysis.

## 范围

### 包含

1. **DuckDB storage schema** (`tradingagents/astock/store/schema.py`, 902 lines):
   - `AStockStore` class wrapping a DuckDB connection with thread-safe access
   - 10 tables created via `IF NOT EXISTS` with `INSERT OR REPLACE` semantics:
     - `kline_bars` — K-line OHLCV data (daily + intraday intervals)
     - `valuations` — PE, PB, market cap snapshots per date
     - `order_book_snapshots` — bid/ask quotes at timestamps
     - `trade_tape` — individual trade records
     - `research_reports` — analyst/researcher output storage
     - `news_items` — news articles with source metadata
     - `announcements` — regulatory announcements
     - `backtest_results` — strategy backtest run outputs
     - `paper_trades` — paper trading order ledger
     - `market_indicators` — composite market metrics
   - Per-table `insert_*` / `query_*` methods with type-safe signatures
   - `export_table()` / `import_table()` supporting CSV, JSON, Parquet formats
   - `get_table_stats()` — row count, date range, schema per table
   - `vacuum()` — DuckDB VACUUM for storage compaction
   - `query_sql()` — arbitrary SQL passthrough
   - `list_tables()` — table enumeration
   - `init_schema()` / `drop_all_tables()` for test lifecycle
   - Default DB path: `~/.tradingagents/astock/astock.duckdb`
   - Lifetime management via `__enter__` / `__exit__` context manager

2. **Data loaders** (`tradingagents/astock/store/loader.py`, 241 lines):
   - `BatchLoader` — batch-fetch multiple symbols/sections from providers
   - `KlineLoader` — provider → DuckDB kline pipeline
   - `ValuationLoader` — provider → DuckDB valuation pipeline
   - All loaders use `AStockDataFacade` as the provider router

3. **CLI tool** (`scripts/astock_db_tool.py`, 167 lines):
   - `list-tables` — list all tables
   - `stats` — per-table row counts and date ranges
   - `export` — export table to file (csv/json/parquet)
   - `import` — import file into table
   - `query` — run arbitrary SQL
   - `vacuum` — storage compaction

4. **Package integration**:
   - `tradingagents/astock/store/` subpackage with re-exports
   - `tradingagents/astock/__init__.py` exports `AStockStore`, `init_astock_db`, `KlineLoader`, `ValuationLoader`, `BatchLoader`
   - `pyproject.toml` adds `duckdb>=1.2.0` dependency

5. **Sample report payload** (`webui/public/sample.json`, 120 lines):
   - Live research sample: `600519.SH` (贵州茅台) with full advisory chain

### 排除

- No changes to existing `AStockDataRouter`, `AStockInterface`, or provider adapter code
- No provider-to-DuckDB auto-wiring (loaders exist but are opt-in)
- No storage-level caching integration (in-memory cache remains primary)
- No schema migration system (schema is `CREATE IF NOT EXISTS`)
- No index optimization beyond primary keys

## 架构映射

| ARCHITECTURE.md section | Module | Expected change |
|---|---|---|
| Data layer | `tradingagents/astock/store/schema.py` | New — DuckDB schema + AStockStore |
| Data layer | `tradingagents/astock/store/loader.py` | New — provider → DuckDB loaders |
| CLI | `scripts/astock_db_tool.py` | New — DB management CLI |
| Package init | `tradingagents/astock/__init__.py` | Re-export store types |
| Config | `pyproject.toml` | Add duckdb dependency |

## 产品决策

- **DuckDB over SQLite**: DuckDB provides native Parquet support, vectorized execution, and better analytical query performance for time-series market data.
- **`INSERT OR REPLACE` semantics**: All tables use upsert semantics keyed on `(symbol, trade_date, ...)` for idempotent re-insertion — no unique constraint violations on replay.
- **Thread-safe connection**: Global lock via `threading.Lock` around DuckDB operations to support concurrent writer attempts (used by backtest/paper-trade paths).
- **Default path in home directory**: `~/.tradingagents/astock/astock.duckdb` — survives repository deletion, follows XDG-adjacent convention.

## 实现记录

### 修改文件

| File | Lines | Purpose |
|---|---|---|
| `tradingagents/astock/store/schema.py` | +902 | DuckDB DDL, AStockStore class, init_astock_db factory |
| `tradingagents/astock/store/loader.py` | +241 | Data loaders (BatchLoader, KlineLoader, ValuationLoader) |
| `tradingagents/astock/store/__init__.py` | +28 | Subpackage exports |
| `tradingagents/astock/__init__.py` | +7 | Re-export store types |
| `scripts/astock_db_tool.py` | +167 | DB management CLI |
| `tests/test_astock_store.py` | +681 | 31 tests covering all tables + import/export + concurrency |
| `pyproject.toml` | +1 | Add duckdb>=1.2.0 dependency |
| `webui/public/sample.json` | +120 | Live research sample payload |

### 行为契约

- **Input**: DuckDB database path (default `~/.tradingagents/astock/astock.duckdb`) or factory function `init_astock_db(path)`
- **Output**: Query results as `pandas.DataFrame`; insert returns row count; export writes file; import reads file
- **Degradation**: Missing DuckDB package raises `ImportError` at class instantiation (not module import time)
- **Safety boundary**: Default path is user-writeable home dir; `drop_all_tables()` is explicit (no auto-drop); `vacuum()` is explicit (no auto-vacuum)

## ECC 验收

### 命令

```bash
cd /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents
python3 -m pytest tests/test_astock_store.py -v --tb=short 2>&1
```

### 结果

- Pass: `31`
- Fail: `0`
- Skip: `0`
- Environment gaps: None

Codex verdict: `accept`

## 风险与缺口

1. **Threading model**: Global lock simplifies correctness but serializes concurrent insert paths. Acceptable for batch-oriented research use; revisit if high-frequency writes are needed.
2. **No auto-migration**: Schema is `CREATE IF NOT EXISTS`. Table changes (new columns, constraints) require explicit migration or `drop_all_tables()` for dev environments.
3. **Loader integration opt-in**: `KlineLoader`/`ValuationLoader` exist but are not wired into `AStockInterface` or the research pipeline — they must be called explicitly. Future phases may add auto-wiring.

## 下一 phase 进入条件

Phase 12 is a standalone infrastructure layer. No dependencies on subsequent phases. The backlog / maintenance work that follows is documented in `docs/ASTOCK_CURRENT_STATUS.md` under P0/P1/P2, with the highest-priority uncommitted item being the WebUI i18n + A-stock report viewer alignment (P1 backlog).

## 修正记录

_No corrections at time of writing._

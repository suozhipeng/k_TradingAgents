# AStock Pro 数据库模块开发白皮书

> 版本以 [../CHANGELOG.md](../CHANGELOG.md) 最新条目为准。
> **项目**: TradingAgents / AStock Pro
> **模块路径**: `tradingagents/astock/store/`

---

## 目录

1. [概述](#1-概述)
2. [架构设计](#2-架构设计)
3. [存储后端](#3-存储后端)
4. [数据模型](#4-数据模型)
5. [迁移系统](#5-迁移系统)
6. [数据同步](#6-数据同步)
7. [作业管理](#7-作业管理)
8. [数据质量](#8-数据质量)
9. [部署指南](#9-部署指南)
10. [API 参考](#10-api-参考)
11. [v2.0 变更日志](#11-v20-变更日志)

---

## 1. 概述

AStock Pro 数据库模块为 A 股量化交易数据管理平台提供商业级数据存储层。支持三种存储后端：

- **DuckDB** — 本地 OLAP 分析缓存，适用于单机开发、WebUI、回测快照
- **PostgreSQL** — 生产级主存储（OLTP），支持多用户并发写入和事务
- **ClickHouse** — 生产级 OLAP 分析副本，适用于海量历史行情扫描

所有后端共享同一套表结构和数据模型，通过运行时后端切换机制无缝衔接。

---

## 2. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask API Layer                          │
│              tradingagents/astock/api/                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
               ┌───────────▼───────────┐
               │   BackendManager      │  ← 运行时后端切换
               │   backend_mgr         │
               └───────────┬───────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
  ┌─────▼─────┐    ┌──────▼──────┐   ┌───────▼───────┐
  │  DuckDB   │    │ PostgreSQL  │   │  ClickHouse   │
  │  (Local)  │    │ (Primary)   │   │  (OLAP)       │
  └───────────┘    └─────────────┘   └───────────────┘
```

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| AStockStore | `schema.py` | DuckDB 本地存储层 |
| PGStore | `pg_store.py` | PostgreSQL 生产存储层 |
| BackendManager | `backend.py` | 运行时后端切换 |
| MigrationRunner | `migrations/runner.py` | 版本化迁移引擎 |
| DataJobManager | `jobs.py` | 异步作业管理 |
| CH Schema | `clickhouse_schema.py` | ClickHouse DDL 定义 |
| Loaders | `loader.py` | 数据加载器 |
| **SchemaDefs** | **`schema_defs.py`** | **SSOT: 统一表定义/列映射/索引定义** |
| **ORM Models** | **`models/`** | **32 个 ORM 模型（分模块组织）** |

---

## 3. 存储后端

### 3.1 DuckDB（本地 OLAP）

**文件**: `tradingagents/astock/store/schema.py`

DuckDB 作为本地分析缓存，使用 `INSERT OR REPLACE` 语义实现幂等写入。

```python
from tradingagents.astock.store import AStockStore, init_astock_db

store = init_astock_db("~/.tradingagents/astock/astock.duckdb")
store.init_schema()  # 创建所有表和索引
store.insert_kline("000001.SZ", dataframe)
df = store.query_kline("000001.SZ", start="2024-01-01")
```

**特性**:
- 线程安全写入（内部 `threading.Lock`）
- 上下文管理器支持（`with` 语句）
- 内置迁移引擎（`store.migrate()`）
- 审计日志、API 密钥管理、数据质量规则

### 3.2 PostgreSQL（生产主存储）

**入口文件**: `tradingagents/astock/store/pg_store.py`

基于 SQLAlchemy 2.0 + asyncpg 的异步优先设计，通过 `models/` 子目录使用 32 个 ORM 模型类。`pg_store.py` 是 public compatibility entrypoint，具体职责已拆到 `pg_*` mixin：

| 文件 | 职责 |
|------|------|
| `pg_common.py` | `PGConfig`、共享 SQLAlchemy 导入、ORM 模型集合 |
| `pg_connection.py` | 同步/异步连接、schema 初始化、迁移 |
| `pg_io.py` | DataFrame upsert/query 通用 I/O |
| `pg_market_data.py` | K 线、估值、盘口等市场数据写读 |
| `pg_governance.py` | 数据质量、审计、API key、通知等治理表操作 |
| `pg_admin.py` | 备份、恢复、统计、清理等管理能力 |
| `pg_store.py` | 组合 mixin，导出 `PGStore` / `init_pg_store` |

```python
from tradingagents.astock.store import PGConfig, PGStore

config = PGConfig(host="postgres", port=5432, database="astock",
                  user="astock", password="astock_prod_2026")
store = PGStore(config)
await store.connect()
await store.init_schema()
```

**连接池配置**:
- 默认池大小: 20
- 支持同步和异步双模式
- 自动 TimescaleDB hypertable 检测与创建

### 3.3 运行时后端切换

**文件**: `tradingagents/astock/store/backend.py`

```python
from tradingagents.astock.store import backend_mgr

# 查询当前状态
print(backend_mgr.status())
# {'backend': 'duckdb', 'duckdb_connected': True, ...}

# 切换到 PostgreSQL
result = backend_mgr.switch_to("postgresql")
# {'backend': 'postgresql', 'connected': True, 'message': '...'}

# 获取当前活跃 store
store = backend_mgr.get_store()
```

**配置持久化**: `~/.tradingagents/backend.json`

**优先级**:
1. 环境变量（最高）— `ASTOCK_DB_BACKEND`, `PG_HOST`, `PG_PORT`, `PG_DB` 等
2. 持久化配置文件
3. 默认值

### 3.4 存储拓扑声明

三端均注册在 `database_storage_profiles` 表中：

| profile_name | role | engine |
|-------------|------|--------|
| duckdb_local_olap | local_cache_olap | duckdb |
| postgresql_production_oltp | production_primary | postgresql |
| clickhouse_production_olap | production_analytics | clickhouse |

---

## 4. 数据模型

### 4.1 表总览

共 **32 张表**，分为六大类别：

#### 市场数据核心（6 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `kline_bars` | (symbol, bar_time, interval, adjust) | K 线数据 |
| `valuations` | (symbol, trade_date) | 估值数据（PE/PB/市值） |
| `order_book_snapshots` | (symbol, timestamp) | 盘口快照 |
| `trade_tape` | (symbol, timestamp) | 逐笔成交 |
| `market_indicators` | (symbol, trade_date) | 市场指标（MA/RSI/ATR） |
| `technical_indicators` | (symbol, bar_time, ...) | 技术指标（JSON 泛型存储） |

#### 证券基础信息（5 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `security_master` | symbol | 证券主档 |
| `trading_calendar` | (exchange, trade_date) | 交易日历 |
| `security_status_history` | (symbol, effective_date) | 证券状态历史 |
| `industry_classification_history` | (symbol, effective_date, ...) | 行业分类历史 |
| `suspension_events` | (symbol, start_date) | 停牌事件 |

#### 公司行为与定价（3 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `corporate_actions` | action_id | 公司行为（分红/送股/拆股） |
| `adjust_factors` | (symbol, trade_date, adjust) | 复权因子 |
| `price_limit_rules` | rule_id | 涨跌停价格规则 |

#### 研究数据（3 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `research_reports` | (symbol, report_date, title) | 研报 |
| `news_items` | (symbol, publish_date, url) | 新闻 |
| `announcements` | (symbol, publish_date, url) | 公告 |

#### 交易与回测（3 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `backtest_results` | run_id | 回测结果 |
| `paper_trades` | trade_id | 模拟交易 |
| `data_sources` | source_id | 数据源注册 |

#### 运维管理（12 张）

| 表名 | 主键 | 说明 |
|------|------|------|
| `database_storage_profiles` | profile_name | 存储拓扑声明 |
| `migration_versions` | version_id | 迁移版本追踪 |
| `data_quality_checks` | check_id | 数据质量检查记录 |
| `data_quality_rules` | rule_id | 数据质量规则 |
| `data_snapshots` | snapshot_id | 数据快照 |
| `data_partitions` | partition_id | 数据分区 |
| `data_ingestion_jobs` | job_id | 数据摄入作业 |
| `data_ingestion_job_events` | event_id | 作业事件日志 |
| `audit_log` | event_id | 审计日志 |
| `api_keys` | key_id | API 密钥管理 |
| `data_quarantine` | quarantine_id | 数据隔离区 |
| `notification_channels` | name | 通知渠道配置（webhook/dingtalk/email/work_weixin） |

### 4.2 索引策略

每张表都定义了针对性的查询路径索引，例如：

```sql
CREATE INDEX idx_kline_symbol_interval_time ON kline_bars(symbol, interval, bar_time);
CREATE INDEX idx_audit_event_time ON audit_log(event_time);
```

共 **27 个索引**，覆盖所有高频查询路径。

### 4.3 数据类型规范

| 数据类型 | DuckDB | PostgreSQL | ClickHouse |
|---------|--------|------------|------------|
| 字符串 | VARCHAR | TEXT | String |
| 整数 | INTEGER | INTEGER | Int32 |
| 长整 | BIGINT | BIGINT | Int64 |
| 浮点 | DOUBLE | DOUBLE PRECISION | Float64 |
| 日期 | DATE | DATE | Date |
| 时间 | TIMESTAMP | TIMESTAMP | DateTime |
| 布尔 | BOOLEAN | BOOLEAN | UInt8 |
| 可空 | 原生支持 | Nullable | Nullable(T) |

### 4.4 K 线数据约束

```
- interval ∈ ('1m', '5m', '15m', '30m', '60m', '1d', '1w', '1mo', '1y')
- adjust ∈ ('none', 'qfq', 'hfq')
- quality ∈ ('normal', 'abnormal', 'missing')
- open/high/low/close ≥ 0
- high ≥ low
- volume ≥ 0, amount ≥ 0
```

### 4.5 列名映射

不同数据源返回的列名可能不一致，系统通过 `COLUMN_MAP` 进行标准化：

```python
KLINE_COLUMN_MAP = {
    "date": "bar_time", "datetime": "bar_time", "time": "bar_time",
    "turnover": "turnover_rate", "pe_ttm": "pe",
    ...
}
```

---

## 5. 迁移系统

### 5.1 内联迁移（DuckDB）

`AStockStore` 内置轻量迁移引擎：

```python
# 定义迁移
AStockStore._MIGRATIONS = [
    ("V001", "Add new column",
     "ALTER TABLE kline_bars ADD COLUMN quality VARCHAR DEFAULT 'normal'",
     "ALTER TABLE kline_bars DROP COLUMN quality"),
]

# 应用
store.migrate()           # 应用所有未执行的迁移
store.migrate("V001")     # 应用指定迁移
store.rollback_migration("V001")  # 回退迁移
store.list_migrations()   # 查看迁移状态
```

### 5.2 独立迁移引擎（PostgreSQL）

`MigrationRunner` 支持目录发现、依赖检查、事务保障：

```python
from tradingagents.astock.store.migrations import MigrationRunner

runner = MigrationRunner(async_engine)
await runner.discover()       # 发现 V{YYYYMMDD}_{NNN}__*.py 文件
await runner.upgrade()        # 执行所有待迁移
await runner.downgrade("V20260628_001")  # 回退到指定版本
await runner.status()         # 查看迁移状态（返回 DataFrame）

# 创建新迁移文件
path = await runner.create("add_new_table")
```

**迁移文件命名约定**: `V{YYYYMMDD}_{NNN}__{name}.py`

```python
# V20260628_001__initial_schema.py
version_id = "V20260628_001"
description = "Initial schema"
dependencies = []

async def upgrade(engine):
    await engine.execute(text("CREATE TABLE ..."))

async def downgrade(engine):
    await engine.execute(text("DROP TABLE ..."))
```

### 5.3 迁移追踪

迁移状态持久化在 `migration_versions` 表：

| 字段 | 说明 |
|------|------|
| version_id | 版本号 |
| checksum | 文件 SHA-256 校验 |
| status | applied / failed / reverted |
| duration_ms | 执行耗时 |
| rollback_sql | 回滚 SQL |

---

## 6. 数据同步

### 6.1 ClickHouse 同步

**文件**: `scripts/astock_sync_ch.py`

从 DuckDB 或 PostgreSQL 批量抽取数据到 ClickHouse OLAP 副本：

```bash
# 一次性同步所有表
python scripts/astock_sync_ch.py --source duckdb

# 增量同步（自指定日期起）
python scripts/astock_sync_ch.py --source postgresql --since 2024-01-01

# 连续监控模式
python scripts/astock_sync_ch.py --source duckdb --watch --interval 60
```

**环境变量配置**:
```bash
export CH_HOST=http://localhost:8123
export CH_USER=astock
export CH_PASSWORD=astock_ch_2026
export PG_HOST=postgres
export PG_PORT=5432
export DUCKDB_PATH=~/.tradingagents/astock/astock.duckdb
```

**同步流程**:
1. 通过 `TABLE_MAP` 确定源表和目标 CH 表的映射关系
2. 从源库读取数据（支持 `since` 日期过滤）
3. 清理 NaN/NaT/None 为 ClickHouse 兼容的 `\N`
4. 以 CSV 格式通过 HTTP 接口批量插入

### 6.2 ClickHouse 表结构

**文件**: `tradingagents/astock/store/clickhouse_schema.py`

12 张 OLAP 表，全部使用 `MergeTree()` 引擎（单节点部署）：

| CH 表 | 分区键 | 排序键 | TTL |
|-------|--------|--------|-----|
| kline_bars_ch | toYYYYMM(trade_date) | (symbol, interval, bar_time) | 5 年 |
| valuations_ch | toYYYYMM(trade_date) | (symbol, trade_date) | 5 年 |
| order_book_snapshots_ch | toYYYYMM(timestamp) | (symbol, timestamp) | 2 年 |
| trade_tape_ch | toYYYYMM(timestamp) | (symbol, timestamp) | 2 年 |
| market_indicators_ch | toYYYYMM(trade_date) | (symbol, trade_date) | 5 年 |
| technical_indicators_ch | toYYYYMM(trade_date) | (symbol, interval, indicator, bar_time) | 3 年 |
| adjust_factors_ch | toYYYYMM(trade_date) | (symbol, trade_date, adjust) | 10 年 |
| security_status_history_ch | toYYYYMM(effective_date) | (symbol, effective_date) | 10 年 |
| industry_classification_history_ch | toYYYYMM(effective_date) | (symbol, effective_date, classification, level) | 10 年 |
| suspension_events_ch | toYYYYMM(start_date) | (symbol, start_date) | 10 年 |
| corporate_actions_ch | toYYYYMM(action_date) | (action_id,) | 10 年 |
| data_quality_checks_ch | toYYYYMM(ingestion_time) | (dataset, check_id, ingestion_time) | 3 年 |

**DDL 导出**:
```python
from tradingagents.astock.store.clickhouse_schema import export_ch_sql

# 导出到文件
export_ch_sql("deploy/ch_init/01_create_tables.sql")

# 获取 DDL 字符串
ddl = export_ch_sql()
```

---

## 7. 作业管理

### 7.1 DataJobManager

**文件**: `tradingagents/astock/store/jobs.py`

线程安全的异步作业管理器，支持优先级调度和重试：

```python
from tradingagents.astock.store.jobs import DataJobManager

manager = DataJobManager(max_workers=4, store=pg_store)

# 提交作业
job = manager.submit(
    kind="kline_import",
    fn=worker_function,
    total=1000,
    priority=10,
    max_retries=3,
)

# 查询进度
print(job.progress)  # 0.0 ~ 1.0
print(job.to_dict())

# 列出作业
jobs = manager.list(status="running", limit=20)

# 取消作业
manager.cancel(job.job_id)
```

**作业状态机**:
```
queued → running → succeeded
                → failed (可重试)
                → cancelled
```

**重试策略**: 指数退避延迟 `[5s, 15s, 30s, 60s, 120s]`

---

## 8. 数据质量

### 8.1 质量规则

```python
# 注册规则
rule_id = store.store_quality_rule(
    rule_name="kline:no_negative_prices",
    check_sql="SELECT COUNT(*) AS violations FROM kline_bars WHERE open < 0 OR close < 0",
    severity="critical",
)

# 执行规则
result = store.run_quality_rule(rule_id)
# {'rule_id': ..., 'status': 'critical', 'matched': 150, 'failed': 150, 'quarantined': 150}

# 批量执行所有规则
results = store.run_all_quality_rules()
```

### 8.2 数据隔离区

违规数据自动移入隔离区：

```python
# 手动隔离
qid = store.store_quarantine(
    source_dataset="kline_bars",
    symbol="000001.SZ",
    reason="Price anomaly detected",
    original_values={"open": -1.0, "close": 10.5},
)

# 审查后解除隔离
store.resolve_quarantine(qid, resolved_by="analyst_01")

# 查询未解决隔离记录
df = store.query_quarantine(severity="critical")
```

### 8.3 质量检查记录

每次规则执行都会写入 `data_quality_checks` 表：

| 字段 | 说明 |
|------|------|
| check_id | 检查唯一标识 |
| dataset | 目标数据集 |
| status | pass / warn / critical / error |
| missing_count | 缺失行数 |
| invalid_count | 无效行数 |
| duplicate_count | 重复行数 |

---

## 9. 部署指南

### 9.1 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.12+ |
| PostgreSQL | 16+ |
| ClickHouse | 24.12+ |
| Docker Compose | v2 |

### 9.2 Docker Compose 一键部署

```yaml
# docker-compose.yml
services:
  app:         # Flask API (gunicorn, port 5001)
  postgres:   # PostgreSQL 16 (port 5433)
  clickhouse: # ClickHouse 24.12 (ports 8123/9000)
  pgadmin:    # PGAdmin 管理界面 (port 5050, profile: admin)
```

**启动**:
```bash
docker compose up -d
```

**健康检查**:
- PostgreSQL: `pg_isready -U astock -d astock`
- ClickHouse: `clickhouse-client --query "SELECT 1"`
- Flask API: `curl -f http://localhost:5860/api/v1/health`

### 9.3 目录结构

```
deploy/
  pg_init/01_extensions.sql    # PG 初始化（扩展、schema、权限）
  ch_init/01_create_tables.sql # CH 初始化（12 张 MergeTree 表）

tradingagents/astock/
  store/
    __init__.py                # 模块导出
    schema.py                  # DuckDB 存储层（DDL 从 schema_defs 派生）
    schema_defs.py             # **[v2.0] 统一表定义 (SSOT)**
    pg_store.py                # PostgreSQL public entrypoint（组合 pg_* mixin）
    pg_common.py               # PGConfig + ORM 模型集合
    pg_connection.py           # 连接、schema 初始化、迁移
    pg_io.py                   # DataFrame upsert/query 通用 I/O
    pg_market_data.py          # 市场数据写读
    pg_governance.py           # 治理表操作
    pg_admin.py                # 管理/备份/统计能力
    backend.py                 # 运行时后端切换
    clickhouse_schema.py       # ClickHouse DDL + 导出工具
    migrations/
      runner.py                # 迁移引擎
      V20260628_001__.py       # 迁移文件
    models/                    # **[v2.0] ORM 模型分模块**
      __init__.py              # 聚合导出 + ALL_MODEL_CLASSES
      base.py                  # DeclarativeBase
      reference.py             # SecurityMaster, TradingCalendar 等
      market_data.py           # KlineBar, Valuation, TechnicalIndicator 等
      events.py                # CorporateAction, BacktestResult 等
      governance.py            # DataSource, AuditLog, ApiKey, NotificationChannel 等
    jobs.py                    # 作业管理器
    loader.py                  # 数据加载器
  api/
    __init__.py                # Flask 应用工厂
    routes_data.py             # 数据 API
    routes_admin.py            # 管理 API
    auth.py                    # 认证中间件
    audit.py                   # 审计日志
```

### 9.4 生产配置

**PostgreSQL 性能调优** (`docker-compose.yml`):
```yaml
command: >
  postgres
  -c max_connections=200
  -c effective_cache_size=4GB
  -c work_mem=64MB
  -c maintenance_work_mem=256MB
```

**ClickHouse 资源限制**:
```yaml
ulimits:
  nofile:
    soft: 262144
    hard: 262144
```

---

## 10. API 参考

### 10.1 核心类

#### AStockStore (DuckDB)

```python
# 初始化
store = init_astock_db(db_path)
store.init_schema()

# K 线操作
store.insert_kline(symbol, df, interval="1d", source="tushare")
df = store.query_kline(symbol, start="2024-01-01", end="2024-12-31")

# 估值操作
store.insert_valuations(symbol, df, source="eastmoney")
df = store.query_valuations(symbol, start="2024-01-01")

# 通用 CRUD
store.insert_table_rows(table_name, rows)
store.query_table(table_name, where="", limit=100)
store.drop_all_tables()

# 迁移
store.migrate()
store.rollback_migration("V001")

# 审计
store.store_audit_log(event_type="data_ingestion", action="complete")

# 质量
store.store_quality_rule(rule_name="...", check_sql="...")
store.run_quality_rule(rule_id)
store.query_quarantine(severity="critical")
```

#### PGStore (PostgreSQL)

```python
# 初始化
store = PGStore(config, sync=False)
await store.connect()
await store.init_schema()

# K 线操作 (async)
rows = await store.insert_kline("000001.SZ", df)
df = await store.query_kline("000001.SZ", start="2024-01-01")

# 关闭
await store.close()
```

#### BackendManager

```python
# 查询状态
status = backend_mgr.status()

# 切换后端
result = backend_mgr.switch_to("postgresql")

# 获取活跃 store
store = backend_mgr.get_store()
```

### 10.2 REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/kline?symbol=...` | 查询 K 线 |
| GET | `/api/v1/valuation?symbol=...` | 查询估值 |
| POST | `/api/v1/data/manual/<table_name>` | 手动写入受管表 |
| GET/POST | `/api/v1/admin/backend` | 查看/切换后端 |
| GET | `/api/v1/admin/backend/config` | 查看后端配置 |
| POST | `/api/v1/admin/health/sync-ch` | 触发 ClickHouse 同步健康检查 |
| GET | `/api/v1/ops/audit` | 查询审计日志 |
| GET | `/api/v1/ops/tasks` | 查询运维任务列表 |
| GET | `/api/v1/ops/scheduler/status` | 查询调度器状态 |

---

## 附录 A: 环境变量清单

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ASTOCK_DB_BACKEND` | `duckdb` | 当前后端 (`duckdb` / `postgresql`) |
| `ASTOCK_DB_PATH` | `~/.tradingagents/astock/astock.duckdb` | DuckDB 文件路径 |
| `PG_HOST` | `localhost` | PostgreSQL 主机 |
| `PG_PORT` | `5432` | PostgreSQL 端口 |
| `PG_DB` | `astock` | PostgreSQL 数据库名 |
| `PG_USER` | `astock` | PostgreSQL 用户名 |
| `PG_PASSWORD` | `astock_prod_2026` | PostgreSQL 密码 |
| `PG_POOL_SIZE` | `20` | PG 连接池大小 |
| `CH_HOST` | `http://localhost:8123` | ClickHouse HTTP 地址 |
| `CH_USER` | `astock` | ClickHouse 用户名 |
| `CH_PASSWORD` | `astock_ch_2026` | ClickHouse 密码 |
| `FLASK_ENV` | `production` | Flask 运行环境 |

## 附录 B: 表间关系图

```
security_master (1) ──── (N) kline_bars
                       (1) ──── (N) valuations
                       (1) ──── (N) order_book_snapshots
                       (1) ──── (N) trade_tape
                       (1) ──── (N) corporate_actions
                       (1) ──── (N) adjust_factors
                       (1) ──── (N) suspension_events
                       (1) ──── (N) security_status_history
                       (1) ──── (N) industry_classification_history

trading_calendar ──── 验证 kline_bars.bar_time 有效性

data_quality_checks ──── 审计所有写入操作
audit_log ──── 全局审计追踪
api_keys ──── 控制 API 访问权限
```

## 附录 C: 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-28 | 初始版本，三后端架构 + 迁移系统 + 质量门禁 |
| v2.0 | 2026-06-29 | 10项重大改进（详见下方变更日志） |
| v2.2 | 2026-06-30 | ORM 列顺序对齐 schema_defs SSOT，新增 `test_orm_column_order_matches_schema_defs` 回归测试 |
| v2.3 | 2026-07-05 | 新增 `notification_channels` 表（通知渠道配置），ORM 模型数 31→32 |

---

## 11. v2.0 变更日志

### 11.1 关键 Bug 修复

| # | 修复项 | 影响 | 文件 |
|---|--------|------|------|
| 1 | `PGConfig.pool_size` 参数传递错误 | 同步引擎创建失败 | `pg_store.py` |
| 2 | `asyncio.run()` 嵌套调用风险 | 运行时崩溃 | `backend.py` |
| 3 | `_MIGRATIONS` 空列表 | 迁移引擎无实际迁移 | `schema.py`, `pg_store.py` |

### 11.2 架构优化

| # | 优化项 | 说明 | 新增/修改文件 |
|---|--------|------|--------------|
| 4 | ORM 模型拆分 | ORM 模型从 `pg_store.py` 拆至 `models/` 子包；当前为 32 个模型 | `models/base.py`, `reference.py`, `market_data.py`, `events.py`, `governance.py` |
| 5 | 统一 Schema 定义 (SSOT) | 新建 `schema_defs.py` 作为 DDL/ORM/Index 唯一数据源 | `schema_defs.py` |
| 6 | 迁移自动发现 | `discover_migrations()` 自动扫描 `migrations/` 目录 | `schema.py`, `pg_store.py` |

### 11.3 数据导入/导出/备份增强

| # | 功能 | 说明 | 文件 |
|---|------|------|------|
| 7 | 全库备份/恢复 | `backup()`, `restore()`, `backup_to_parquet()`, `restore_from_parquet()` | `schema.py` |
| 8 | 增量导出 | `export_incremental()` 基于 `updated_at` 过滤 | `schema.py`, `astock_db_tool.py` |
| 9 | 导出压缩 | `export_table(compression="gzip")` 支持 gzip/bz2/xz | `schema.py`, `astock_db_tool.py` |
| 10 | 导入验证 | `_validate_import()` 自动校验行数一致性 | `schema.py`, `astock_db_tool.py` |

### 11.4 性能优化

| # | 优化项 | 说明 | 文件 |
|---|--------|------|------|
| 11 | Bulk Upsert | `executemany` + 分块提交替代逐条插入 | `pg_store.py` |

### 11.5 测试验证

- 当前回归基线：`tests/test_astock_store.py` 收集 39 项，36 passed / 3 skipped。
- 跳过项需要 pyarrow/fastparquet 或 `TEST_PYDANTIC_BT=1`。

### 11.6 v2.1 代码清理

| # | 清理项 | 说明 | 影响 |
|---|--------|------|------|
| 1 | 移除死代码 | 删除 `schema.py` 中 44 个 `CREATE_XYZ` 常量 | schema.py 从 2513 行减至 1985 行（-528 行） |
| 2 | 统一 SSOT | `SUPPORTED_KLINE_INTERVALS` 从 schema.py + pg_store.py 两处重复定义，统一到 `schema_defs.py` | 单一事实来源 |
| 3 | 迁移引用修复 | `CREATE_MIGRATION_VERSIONS` 改为从 `schema_defs.TABLE_DEFS` 动态生成 | 消除硬编码 DDL |
| 4 | 索引定义统一 | `INDEX_DEFS` 从 schema.py 复制定义改为 `from .schema_defs import DEFAULT_INDEX_DEFS` | PG 和 DuckDB 共享同一索引定义 |

### 11.7 v2.2 ORM 列顺序对齐

| # | 变更项 | 说明 | 影响文件 |
|---|--------|------|----------|
| 1 | ORM 列顺序对齐 schema_defs | 将 `KlineBar`, `TechnicalIndicator`, `NewsItem`, `Announcement`, `IndustryClassificationHistory` 的列声明顺序重排，使其与 `schema_defs.TABLE_DEFS` 的 SSOT 顺序完全一致 | `models/market_data.py`, `models/events.py`, `models/reference.py` |
| 2 | 新增回归测试 | `test_orm_column_order_matches_schema_defs` 断言 ORM 模型的列顺序和主键顺序与 `schema_defs` 严格匹配，防止未来再次脱节 | `tests/test_astock_store.py` |
| 3 | `interval`/`adjust` 默认值 | `KlineBar.interval` 添加 `default="1d"`，`KlineBar.adjust` 添加 `default="none"` | `models/market_data.py` |

**迁移注意事项**:
- 空库不受影响（`init_schema` 直接按新顺序建表）
- 已有数据库需创建新的迁移文件执行 `ALTER TABLE` 重排序列
- 主键列顺序变更不影响 `ON CONFLICT` 语义，但需确认上游查询无硬编码假设
- 经调研确认：所有下游消费者（`pg_store.py` 的 `_get_pk_columns` fallback、`insert_kline` 硬编码、查询过滤）均与 `schema_defs` 一致，无需额外修改

### 11.8 v2.3 PGStore 职责拆分

| # | 变更项 | 说明 | 影响文件 |
|---|--------|------|----------|
| 1 | `PGStore` public entrypoint 收敛 | `pg_store.py` 保持 `PGStore` / `init_pg_store` 导出，避免破坏既有导入路径 | `pg_store.py` |
| 2 | 连接与 I/O 拆分 | 连接、schema 初始化、迁移拆入 `pg_connection.py`，DataFrame 通用写读拆入 `pg_io.py` | `pg_connection.py`, `pg_io.py` |
| 3 | 领域能力拆分 | 市场数据写读、治理表操作、管理能力分别拆入独立 mixin | `pg_market_data.py`, `pg_governance.py`, `pg_admin.py` |
| 4 | 回归基线 | 全量测试通过：`1070 passed, 15 skipped, 9 warnings, 120 subtests passed` | `tests/` |

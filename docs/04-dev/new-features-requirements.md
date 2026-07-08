# 新增功能需求文档

> 整理自 `xg_dev` 分支近期工作（2026-06-27 ~ 2026-06-30）

---

## 目录

1. [K 线数据 CLI + 双后端引擎](#1-k-线数据-cli--双后端引擎)
2. [数据库模块 v1.0 重构](#2-数据库模块-v10-重构)
3. [API 层修复](#3-api-层修复)
4. [Web 前端修复](#4-web-前端修复)
5. [Backlog 关联](#5-backlog-关联)

---

## 1. K 线数据 CLI + 双后端引擎

### 1.1 概述

基于 **baostock**（免费 / 无限流 / 无反爬）构建全市场 A 股 K 线数据拉取工具链，
采用 **DuckDB + SQLite 双后端** 写入策略，参考 [Sequoia-X](https://github.com/sngyai/Sequoia-X) 设计。

**文件清单：**
| 文件 | 职责 |
|------|------|
| `scripts/kline_engine.py` | 核心引擎：数据拉取、多进程并行、双后端写入 |
| `scripts/kline_cli.py` | CLI 界面：拉取/查询/统计子命令 |
| `scripts/fetch_kline.py` | 旧版单用途拉取（AkshareAdapter，逐步废弃） |
| `kline/kline.duckdb` | DuckDB 数据文件（4.7 MB） |
| `kline/kline.sqlite` | SQLite 便携备份（844 KB） |

### 1.2 需求详情

#### FR-01 双后端写入

- **目标**：写入 DuckDB（项目集成，对接 AStockStore 标准 schema）和 SQLite（便携备份，干净 schema + UNIQUE 约束）
- **行为**：
  - 默认两个后端同时写入
  - `--duckdb-only` 仅写 DuckDB
  - `--sqlite-only` 仅写 SQLite
- **SQLite schema**：表 `stock_daily`，列 `id/symbol/date/open/high/low/close/volume/turnover/freq`，UNIQUE(symbol, date, freq)
- **DuckDB schema**：对接 `tradingagents.astock.store.schema.AStockStore.insert_kline()`

#### FR-02 多频率支持

- **日线**：`1d` / `day` / `daily`，后复权
- **分钟线**：`5m` / `15m` / `30m` / `60m`，不复权
- 统一频率映射表 `FREQUENCY_MAP` → (baostock_freq, normalized_interval)

#### FR-03 多进程并行拉取

- 使用 `multiprocessing.Pool`，默认 8 进程
- 每个 worker 独立 login，过期自动 logout
- 支持 `KeyboardInterrupt` 优雅退出（已写入数据不丢失）
- 300s 超时保护

#### FR-04 增量同步

- 自动检查本地 `MAX(bar_time)` / `MAX(date)`，只拉取缺失数据
- `BaostockSync.sync_today()` 用于日频增量更新
- 全市场今日拉取为默认模式

#### FR-05 全历史回填

- `BaostockSync.backfill()` 带重试机制（默认 3 次，指数退避）
- 定期重连（默认每 200 只股票）防止 baostock 长连接超时
- 自动跳过已是最新的股票
- 进度日志（每 500 只）

#### FR-06 CLI 子命令

| 子命令 | 功能 | 关键参数 |
|--------|------|---------|
| `fetch` | 拉取（默认全市场今日日K） | `--all`, `--symbol`, `-f freq`, `--workers`, `--duckdb-only`, `--sqlite-only` |
| `query` | 查询 | `--symbol`, `--date/-d`, `--latest/-n`, `--start/--end`, `-f freq`, `--from-sqlite` |
| `stats` | 统计 | `-f freq`, `--from-sqlite` |

#### FR-07 股票代码转换

- 项目格式：`600519.SH`
- Baostock 格式：`sh.600519`
- 6xx/9xx → sh，其余 → sz

### 1.3 未完成 / 待后续

- [ ] 分钟数据拉取后的 SQLite 写入量较大，已加但未做批量 INSERT 优化
- [x] `fetch_kline.py`（旧版 akshare）已保留为后备数据源，文件头部加了 Legacy 标注
- [x] cronjob `kline-daily-fetch` (job_id: c6e0b345edb9) 已注册，交易日 16:00 HKT 自动拉取当日增量

---

## 2. 数据库模块 v1.0 重构

### 2.1 概述

从单一 `schema.py` 拆解为 **SchemaDefs SSOT + ORM Models + 后端适配器** 三层架构，
实现 DuckDB / PostgreSQL / ClickHouse 三后端共享同一套表定义。

**文件清单：**
| 文件 | 行数 | 职责 |
|------|------|------|
| `store/schema_defs.py` | 698 | **SSOT**：32 张表的 ColumnDef / TableDef / DDL 生成 |
| `store/schema.py` | 963 | DuckDB 后端（已重构为导入 schema_defs） |
| `store/pg_store.py` | 753 | PostgreSQL 后端（已重构为导入 schema_defs） |
| `store/models/` | 5 文件 | ORM 模型（按模块拆分） |
| `store/backend.py` | 22 | BackendManager 运行时后端切换 |
| `docs/database_module_whitepaper.md` | 784 | 数据库白皮书 |
| `tests/test_astock_store.py` | +15 | 回归测试（列顺序对齐） |

### 2.2 需求详情

#### FR-08 SchemaDefs SSOT（单一事实源）

- **目标**：所有表定义集中在 `schema_defs.py`，DuckDB / PostgreSQL 由 `generate_ddl(dialect)` 生成对应 DDL
- **数据类型**：
  - `ColumnDef`: name, type_duckdb, type_postgresql, nullable, default, check
  - `TableDef`: name, columns[], primary_key[], checks[], indexes[]
- 覆盖表：32 张，含行情、参考数据、事件、治理、迁移版本、审计日志、API 密钥、数据质量规则、隔离区

#### FR-09 ORM 模型拆分

| 模块 | 文件 | 模型数 |
|------|------|--------|
| `models/base.py` | Base + TimeStampedBase | 基类 |
| `models/market_data.py` | 行情模型 | ~8 |
| `models/reference.py` | 参考数据模型 | ~6 |
| `models/events.py` | 事件模型 | ~5 |
| `models/governance.py` | 治理模型（含 API 密钥、数据质量、隔离区、审计） | ~12 |

#### FR-10 后端适配

- **DuckDB**（`schema.py`）：锁保护线程安全，INSERT OR REPLACE 幂等，context manager
- **PostgreSQL**（`pg_store.py`）：生产级 OLTP，完整事务，主键 / 索引 / 迁移
- **ClickHouse**（`ch_schema.py`，已有占位）：OLAP 分析副本
- `BackendManager`（`backend.py`）：运行时后端切换

#### FR-11 迁移引擎

- `MIGRATIONS` 列表 + 运行时自动迁移
- 迁移版本表自行管理（在 schema_defs 中定义）

#### FR-12 治理层

- 审计日志表
- API 密钥管理表
- 数据质量规则表
- 隔离区（quarantine）表

### 2.3 已验证 / 已修复

- commit `be3d01d`: ORM 列顺序与 schema_defs 对齐 + `test_astock_store` 回归测试
- commit `f102346`: 清理死代码（去除硬编码 DDL），拆分 ORM 模型

---

## 3. API 层修复

#### FR-13 K 线 limit pushdown

- **目标**：DuckDB 查询 K 线时 LIMIT 下推到 SQL 层，避免全表扫描后截断
- **文件**：`routes_data.py`

#### FR-14 公告查询 DESC 排序

- **目标**：公告列表默认按时间降序
- **文件**：`routes_data.py`

#### FR-15 NaN 辅助函数

- **目标**：JSON 序列化前处理 NaN/Inf，避免 Flask 报错
- **影响范围**：多个 route 文件

#### FR-16 API 错误信封统一

- **目标**：所有 API 错误返回统一 `{"error": ..., "code": ...}` 信封
- **影响范围**：多个 route 文件

#### FR-17 Paper Trader 分页

- **目标**：Paper 交易记录支持分页查询
- **文件**：`routes_paper.py`

---

## 4. Web 前端修复

#### FR-18 kc_data_loader.js 去重

- **目标**：ECharts K 线页面移除重复的 script 加载
- **文件**：`kc_chart.html`（commit `bc16bf8`）

#### FR-19 head_extra block 位置修正

- **目标**：`base.html` 中将 `{% block head_extra %}` 移出 `<style>` 标签作用域，避免样式覆盖
- **文件**：`base.html`（commit `9491128`）

---

## 5. Backlog 关联

以下 P0 项与本批新增功能有直接关联：

| Backlog Item | 关联说明 |
|-------------|---------|
| BL-000 实盘准入清单 | 数据库治理层（审计、API 密钥、数据质量规则）为实盘准入提供基础设施 |
| BL-003 trade/quote | K 线 CLI 提供独立数据源验证能力，可与 trade/quote 对照 |

---

*本文档由 Hermes Agent 于 2026-07-01 自动整理，截至 commit `be3d01d`。*

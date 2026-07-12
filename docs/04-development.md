# 开发文档

> PRD、新功能需求、测试计划和需求追踪矩阵的整合文档。

## 目录

- [1. 产品需求文档 (PRD)](#1-产品需求文档-prd)
- [2. 新功能需求](#2-新功能需求)
- [3. 测试计划](#3-测试计划)
- [4. 需求追踪矩阵](#4-需求追踪矩阵)

---

## PRD

# Product Requirements Document

> 本文档定义产品定位、目标用户、核心场景、能力需求和安全约束。详细需求分解和任务队列见 [`BACKLOG.md`](BACKLOG.md)，模块技术细节见 [`full_function_documentation.md`](full_function_documentation.md)。
>
> 合并自 ASTOCK_PRD.md + ASTOCK_REQUIREMENTS.md + ASTOCK_TECH_REQUIREMENTS.md

---

### 产品概述

#### 产品名称

`TradingAgents-Astock`

#### 产品定义

一个面向 A 股场景的多 Agent 投研与受控交易系统，覆盖研究、报告、回测、模拟盘、QMT managed mock/read-only 边界和产品化 WebUI。

#### 产品目标

- 为 A 股研究与策略验证提供统一工作台
- 用多 Agent 研究链替代单一结论式分析
- 在研究、回测、模拟盘、受控执行边界之间建立连续闭环
- 保持安全边界，避免默认自动实盘

### 目标用户

- 个人投资研究者
- 量化/策略验证用户
- 需要多 Agent 辅助研究的交易团队
- 需要受控执行而非默认自动交易的使用者

### 用户核心场景

#### ### 场景 A：研究驱动

用户输入股票代码、日期、运行模式后，系统生成 A 股研究报告，包括五层数据摘要、多空辩论结论和 advisory 决策结果。

#### ### 场景 B：策略验证

用户选择策略、区间和参数，在 WebUI 或 API 中运行回测、对比收益/回撤/Sharpe，并查看绩效图表。

#### ### 场景 C：模拟盘试跑

用户在不触发真实交易的情况下运行 PaperTrader，验证信号、仓位、交易记录和风控逻辑。

#### ### 场景 D：受控执行

用户在当前阶段只能查看 QMT managed mock/read-only 状态；真实 QMT 下单、委托查询和券商回报对账属于 P3 准入后事项。

### 产品范围

#### 包含范围

- 五层数据能力
- 多 Agent 研究链
- advisory 决策链
- 报告展示
- 回测
- 模拟盘
- QMT managed mock/read-only 边界
- 数据存储与缓存
- Flask WebUI
- Streamlit 只读 viewer
- CLI

#### 不包含范围

- 默认自动实盘
- 无风控、无确认的下单放开
- 多券商统一抽象
- 把所有前端入口合并成一套运行时 UI
- 安全与隐私专项、SLA 与故障分级、用户角色/RBAC 当前只登记，不进入核心功能需求

### 产品能力需求

#### ### PRD-01 数据能力

系统应覆盖：

- 行情层
- 研报层
- 新闻层
- 基础数据层
- 公告层

#### ### PRD-02 研究能力

系统应支持：

- AStockAnalyst
- Bull Researcher
- Bear Researcher
- Research Manager

并形成统一研究输出。

#### ### PRD-03 决策表达

系统应输出结构化 advisory 结果：

- ResearchConclusion
- TraderProposal
- RiskDecision
- PortfolioDecision

#### ### PRD-04 展示能力

系统应支持：

- CLI 报告
- Streamlit 只读 viewer
- WebUI 报告与产品页面

#### ### PRD-05 回测与策略能力

系统应支持：

- 多策略回测
- 批量回测
- 策略优化
- 策略对比
- 绩效分析

#### ### PRD-06 交易模拟与受控执行

系统应支持：

- 模拟盘
- QMT mock/read-only 状态展示
- 安全模式
- 人工确认
- 风控门

### 安全与约束

#### 默认安全边界

研究输出默认必须满足：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

#### 执行约束

- `safety mode` 默认开启
- 当前不开放 auto mode
- QMT API/UI 固定 mock/read-only，不探测真实券商连接
- 风控门先于执行生效

### 当前产品状态

当前仓库已正式归档到 `Phase 29`，大部分产品能力已落地，包括：

- 研究链
- advisory 链
- 回测与模拟盘
- QMT managed mock/read-only 边界
- 数据库与缓存
- WebUI
- 策略优化与绩效分析
- 全仓回归稳定化
- KLineChart、筛选器、板块/资金页面、动量轮动、AI Agent、专业交易页

### 当前产品缺口

- QMT 在 provider 口径上的能力定义仍不完全收口
- trade state 属于 Paper Trading 路径，不代表真实账户状态
- 实盘账户、订单、成交、撤单、拒单、部分成交和券商回报 reconciliation 尚未闭环
- 策略、回测、优化、绩效、策略对比、动量轮动需要收敛为统一 Strategy Lab
- AI Agent、研究报告、新闻/公告/研报解读需要收敛为统一 AI Research Center
- 龙头相关入口需要收敛为一个顶层入口，内部用顶部 tab 切换动量、轮动、板块、资金线索和候选池
- 数据质量、回测反偏差、组合级风控和审计链路仍需加强
- 部分“模块已存在”和“产品能力完整”之间仍有差距

### 1 实盘分析判断

当前新功能可以支撑实盘前研究、盘中辅助观察、策略验证和受控执行试运行，但不应定义为完整实盘生产交易系统。

可用于实盘辅助分析的能力：

- 实时/准实时行情与 K 线展示
- 新闻、公告、研报、F10、估值等多源数据辅助
- AI research/advisory chain
- 策略回测、优化、绩效和模拟盘验证
- QMT managed mode / safety mode 的受控执行雏形

进入完整实盘生产前仍需补齐：

- 实盘账户、订单、成交和券商回报闭环
- kill switch、硬风控、权限、审计和异常恢复
- 数据质量分级、数据快照和可追溯 provenance
- 回测反偏差、out-of-sample、walk-forward 和过拟合检测
- 组合级风险、容量、流动性和绩效归因

### 成功标准

- 用户可以完成从研究到回测、模拟盘、受控执行的连续流程
- 默认路径不触发自动实盘
- WebUI/CLI/viewer 角色清晰
- 回归稳定，产品迭代后可复验
- 所有页面明确标注 research / paper / managed / live-ready 能力边界
- 关键产品指标可被追踪，包括研究报告生成成功率、回测完成率、provider 可用率、任务失败率和审计事件覆盖率
- 后续 Phase 30-39 的每项需求都能在需求追踪矩阵中定位到模块、页面/API、测试和 phase 证据
- API、数据、运行、测试和风险披露均有独立文档约束，不依赖口头约定
- 每个 live-ready 声明都能追溯到准入清单、运行手册、测试验收和风险披露
- 商用交付前必须能回答“当前能力等级、数据来源、测试证据、失败处理、合规边界”五个问题

### 1 后续产品路线

后续路线以 `BACKLOG.md` 为准：

1. Phase 30：Live Trading Readiness
2. Phase 31：Data Quality & Bias Control
3. Phase 32：Strategy Lab
4. Phase 33：AI Research Center
5. Phase 34：Market Leaders
6. Phase 35：Trading & Execution
7. Phase 36：Portfolio Risk & Attribution
8. Phase 37：Ops & Audit
9. Phase 38：Product Navigation Cleanup
10. Phase 39：End-to-End UAT

### 2 商用生产级文档要求

后续开发必须按以下文档闭环执行：

- API 变更先更新 `01-architecture.md`，再进入代码实现。
- 数据字段、provider、质量标签、血缘和快照变更先更新 `03-operations.md`。
- DuckDB、cache、schema、报告归档和回测结果结构变更先更新 `04-development.md`。
- 受控执行、QMT、订单、风控、故障处理和回滚流程先更新 `03-operations.md`。
- 每个 phase 必须按 `04-development.md` 留存测试命令、结果和阻断项。
- 页面、报告、AI 输出、回测结果和交易入口必须遵守 `03-operations.md`。
- 核心功能启动、依赖和健康检查必须遵守 `03-operations.md`。
- AI provider、prompt、模型输出和降级必须遵守 `03-operations.md`。
- WebUI 页面状态、能力标签和顶层导航必须遵守 `02-user-guide.md`。
- WebUI 页面输入、输出、状态、错误态和截图证据必须遵守 `README.md`。
- API/data/AI/trading/UI 兼容性变化必须遵守 `03-operations.md`。
- 当前暂不纳入范围必须以 `README.md` 为准，不得隐式扩展。

### 关联文档

- `BACKLOG.md` — 待开发 backlog 和 Phase 30-39 路线图
- `04-development.md` — 需求、模块、API/页面、测试、phase 追踪矩阵
- `03-operations.md` — 部署、环境、产品指标与监控
- `01-architecture.md` — API 端点参考、错误码、能力等级
- `03-operations.md` — 数据源授权、字典和血缘
- `03-operations.md` — 风险披露、合规边界与隐私声明
- `03-operations.md` — 实盘运行手册
- `03-operations.md` — 项目风险登记
- `04-development.md` — 测试验收计划
- `02-user-guide.md` — WebUI 产品规范
- `02-user-guide.md` — 策略开发规范
- `README.md` — 文档体系索引
- `docs/phase-archive.md` — 阶段索引
- `full_function_documentation.md` — 全功能文档
- `database_module_whitepaper.md` — 数据库模块白皮书


### 维护要求

- 新功能必须明确落在哪一层
- 不允许 UI 直接绕过 API/接口层读底层实现细节
- 不允许以 mock 能力冒充 real capability 写入状态文档
- phase 文档必须补 commit SHA 和测试证据

---

> 本文档合并自 ASTOCK_PRD.md + ASTOCK_REQUIREMENTS.md + ASTOCK_TECH_REQUIREMENTS.md

---

## 新功能需求

# 新增功能需求文档

> 整理自 `xg_dev` 分支近期工作（2026-06-27 ~ 2026-06-30）

---

### ## 目录

1. [K 线数据 CLI + 双后端引擎](#1-k-线数据-cli--双后端引擎)
2. [数据库模块 v1.0 重构](#2-数据库模块-v10-重构)
3. [API 层修复](#3-api-层修复)
4. [Web 前端修复](#4-web-前端修复)
5. [Backlog 关联](#5-backlog-关联)

---

### K 线数据 CLI + 双后端引擎

#### 概述

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

#### 需求详情

##### #### FR-01 双后端写入

- **目标**：写入 DuckDB（项目集成，对接 AStockStore 标准 schema）和 SQLite（便携备份，干净 schema + UNIQUE 约束）
- **行为**：
  - 默认两个后端同时写入
  - `--duckdb-only` 仅写 DuckDB
  - `--sqlite-only` 仅写 SQLite
- **SQLite schema**：表 `stock_daily`，列 `id/symbol/date/open/high/low/close/volume/turnover/freq`，UNIQUE(symbol, date, freq)
- **DuckDB schema**：对接 `tradingagents.astock.store.schema.AStockStore.insert_kline()`

##### #### FR-02 多频率支持

- **日线**：`1d` / `day` / `daily`，后复权
- **分钟线**：`5m` / `15m` / `30m` / `60m`，不复权
- 统一频率映射表 `FREQUENCY_MAP` → (baostock_freq, normalized_interval)

##### #### FR-03 多进程并行拉取

- 使用 `multiprocessing.Pool`，默认 8 进程
- 每个 worker 独立 login，过期自动 logout
- 支持 `KeyboardInterrupt` 优雅退出（已写入数据不丢失）
- 300s 超时保护

##### #### FR-04 增量同步

- 自动检查本地 `MAX(bar_time)` / `MAX(date)`，只拉取缺失数据
- `BaostockSync.sync_today()` 用于日频增量更新
- 全市场今日拉取为默认模式

##### #### FR-05 全历史回填

- `BaostockSync.backfill()` 带重试机制（默认 3 次，指数退避）
- 定期重连（默认每 200 只股票）防止 baostock 长连接超时
- 自动跳过已是最新的股票
- 进度日志（每 500 只）

##### #### FR-06 CLI 子命令

| 子命令 | 功能 | 关键参数 |
|--------|------|---------|
| `fetch` | 拉取（默认全市场今日日K） | `--all`, `--symbol`, `-f freq`, `--workers`, `--duckdb-only`, `--sqlite-only` |
| `query` | 查询 | `--symbol`, `--date/-d`, `--latest/-n`, `--start/--end`, `-f freq`, `--from-sqlite` |
| `stats` | 统计 | `-f freq`, `--from-sqlite` |

##### #### FR-07 股票代码转换

- 项目格式：`600519.SH`
- Baostock 格式：`sh.600519`
- 6xx/9xx → sh，其余 → sz

#### 未完成 / 待后续

- [ ] 分钟数据拉取后的 SQLite 写入量较大，已加但未做批量 INSERT 优化
- [x] `fetch_kline.py`（旧版 akshare）已保留为后备数据源，文件头部加了 Legacy 标注
- [x] cronjob `kline-daily-fetch` (job_id: c6e0b345edb9) 已注册，交易日 16:00 HKT 自动拉取当日增量

---

### 数据库模块 v1.0 重构

#### 概述

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

#### 需求详情

##### #### FR-08 SchemaDefs SSOT（单一事实源）

- **目标**：所有表定义集中在 `schema_defs.py`，DuckDB / PostgreSQL 由 `generate_ddl(dialect)` 生成对应 DDL
- **数据类型**：
  - `ColumnDef`: name, type_duckdb, type_postgresql, nullable, default, check
  - `TableDef`: name, columns[], primary_key[], checks[], indexes[]
- 覆盖表：32 张，含行情、参考数据、事件、治理、迁移版本、审计日志、API 密钥、数据质量规则、隔离区

##### #### FR-09 ORM 模型拆分

| 模块 | 文件 | 模型数 |
|------|------|--------|
| `models/base.py` | Base + TimeStampedBase | 基类 |
| `models/market_data.py` | 行情模型 | ~8 |
| `models/reference.py` | 参考数据模型 | ~6 |
| `models/events.py` | 事件模型 | ~5 |
| `models/governance.py` | 治理模型（含 API 密钥、数据质量、隔离区、审计） | ~12 |

##### #### FR-10 后端适配

- **DuckDB**（`schema.py`）：锁保护线程安全，INSERT OR REPLACE 幂等，context manager
- **PostgreSQL**（`pg_store.py`）：生产级 OLTP，完整事务，主键 / 索引 / 迁移
- **ClickHouse**（`ch_schema.py`，已有占位）：OLAP 分析副本
- `BackendManager`（`backend.py`）：运行时后端切换

##### #### FR-11 迁移引擎

- `MIGRATIONS` 列表 + 运行时自动迁移
- 迁移版本表自行管理（在 schema_defs 中定义）

##### #### FR-12 治理层

- 审计日志表
- API 密钥管理表
- 数据质量规则表
- 隔离区（quarantine）表

#### 已验证 / 已修复

- commit `be3d01d`: ORM 列顺序与 schema_defs 对齐 + `test_astock_store` 回归测试
- commit `f102346`: 清理死代码（去除硬编码 DDL），拆分 ORM 模型

---

### API 层修复

##### #### FR-13 K 线 limit pushdown

- **目标**：DuckDB 查询 K 线时 LIMIT 下推到 SQL 层，避免全表扫描后截断
- **文件**：`routes_data.py`

##### #### FR-14 公告查询 DESC 排序

- **目标**：公告列表默认按时间降序
- **文件**：`routes_data.py`

##### #### FR-15 NaN 辅助函数

- **目标**：JSON 序列化前处理 NaN/Inf，避免 Flask 报错
- **影响范围**：多个 route 文件

##### #### FR-16 API 错误信封统一

- **目标**：所有 API 错误返回统一 `{"error": ..., "code": ...}` 信封
- **影响范围**：多个 route 文件

##### #### FR-17 Paper Trader 分页

- **目标**：Paper 交易记录支持分页查询
- **文件**：`routes_paper.py`

---

### Web 前端修复

##### #### FR-18 kc_data_loader.js 去重

- **目标**：ECharts K 线页面移除重复的 script 加载
- **文件**：`kc_chart.html`（commit `bc16bf8`）

##### #### FR-19 head_extra block 位置修正

- **目标**：`base.html` 中将 `{% block head_extra %}` 移出 `<style>` 标签作用域，避免样式覆盖
- **文件**：`base.html`（commit `9491128`）

---

### Backlog 关联

以下 P0 项与本批新增功能有直接关联：

| Backlog Item | 关联说明 |
|-------------|---------|
| BL-000 实盘准入清单 | 数据库治理层（审计、API 密钥、数据质量规则）为实盘准入提供基础设施 |
| BL-003 trade/quote | K 线 CLI 提供独立数据源验证能力，可与 trade/quote 对照 |

---

*本文档由 Hermes Agent 于 2026-07-01 自动整理，截至 commit `be3d01d`。*

---

## 测试计划

# A 股测试与验收计划

| 更新时间：2026-07-08（含验收证据表 ✅） |

本文定义 TradingAgents-Astock 的生产级测试、验收和发布门槛。它不替代 `tests/` 和 `docs/phase-archive.md`，而是规定后续 phase 如何证明“可以进入下一阶段”。

### 测试分层

| 层级 | 目标 | 示例 |
|---|---|---|
| Unit | 验证函数/类行为 | 策略信号、费用模型、数据清洗 |
| Contract | 验证 schema/API 契约 | advisory schemas、API envelope、错误码 |
| Integration | 验证模块接线 | data router -> interface -> runtime |
| UI/API Slice | 验证页面和 API 闭环 | Flask WebUI + routes |
| Regression | 验证历史能力不退化 | A 股主链切片、全仓 pytest |
| Live Guarded | 验证外部依赖 | live provider、QMT、LLM |
| UAT | 验证用户工作流 | 研究、回测、模拟盘、受控执行 |

### 标准验收门槛

每个 phase 必须提供：

- scope。
- 修改文件。
- API/UI/store schema 是否变化。
- 测试命令。
- 测试结果。
- 已知 skipped 原因。
- 风险和回滚。
- commit SHA。

### 模块验收要求

#### Data & Ops

- provider fallback 可测试。
- stale/partial/mock/fallback/invalid 标签可验证。
- 数据刷新失败有错误码。
- DuckDB/store 读写可验证。

#### AI Research Center

- live research 缺少真实 LLM 时 fail closed。
- deterministic verification 可离线运行。
- 每个 AI 输出保留模型、prompt、数据快照和引用来源。
- advisory 输出不触发真实交易。

#### Strategy Lab

- 策略信号无 NaN 泄漏。
- 回测禁止未来函数。
- 回测结果包含数据假设、成本模型、benchmark。
- 优化结果不能让无交易参数排前。
- 多策略对比排序稳定。

#### Market Leaders

- 候选池有来源和刷新时间。
- 入池/出池理由可解释。
- 板块、资金、龙虎榜、北向均标注数据来源。

#### Trading & Execution

- paper 与 managed 视觉和 API 均区分。
- Risk Gate 拦截有 reason code。
- kill switch 可阻断后续交易。
- managed order 必须有人工确认记录。
- live-ready 前 reconciliation 可检测。

#### Ops & Audit

- 长任务有 task lifecycle。
- 关键动作有 Audit Event。
- 错误进入错误中心。
- 告警级别和处理动作可追踪。

### UAT 场景

| 场景 | 步骤 | 通过标准 |
|---|---|---|
| 研究报告 | 输入 A 股 symbol -> 运行 AI Research -> 生成报告 | 报告含数据来源、模型、时间和 advisory 标记 |
| 策略回测 | 选择策略 -> 设置区间 -> 运行回测 | 输出指标、交易明细、数据假设和 benchmark |
| 策略优化 | 选择策略 -> grid search -> 查看 Top N | 无交易/数据不足参数不排前 |
| 龙头决策 | 打开 Market Leaders -> 查看候选池 -> 进入资金线索 | 候选股有入池理由和数据来源 |
| 模拟盘 | 发起 paper order -> 查看虚拟成交和持仓 | 明确显示 paper，不显示为真实账户 |
| 受控执行 | 发起 managed action -> 风控 -> 人工确认 | 无确认不得执行，拦截有 reason |
| Ops 审计 | 查看任务/错误/审计 | 能追踪关键动作和失败原因 |

### 发布门槛

| 发布类型 | 最低要求 |
|---|---|
| docs-only | `git diff --check -- docs` 通过，索引无断链 |
| API change | contract tests + API slice tests |
| WebUI change | WebUI/API slice tests + 关键页面手工验证 |
| Strategy change | strategy unit + backtest + optimizer tests |
| Data change | provider fixture + data quality tests |
| Trading change | risk gate + paper/managed tests + rollback plan |
| Live-ready claim | runbook checklist + reconciliation + audit evidence |

### 不允许验收的情况

- 只凭页面能打开就验收。
- 只凭 DeepSeek/Hermes 自述就验收。
- mock 数据被描述为 real。
- paper 状态被描述为真实账户。
- live provider 失败但没有 skip guard 或失败说明。
- 交易相关变更没有风控和回滚说明。

### 后续要求

- Phase 30 起，每个 phase 文档必须引用本测试计划。
- Phase 31 起，回测必须展示数据质量和反偏差状态。
- Phase 35 起，交易相关验收必须包含订单生命周期和 kill switch。
- Phase 37 起，所有长任务必须有 Task Run 证据。
- Phase 38 起，导航和入口必须遵守统一的模块 sidebar 规范。
- Phase 39 起，端到端用户工作流必须通过 UAT 验收。

#### ### 验收证据（2026-06-26）

| 验收项 | 状态 | 证据 |
|--------|------|------|
| 测试分层定义 | ✅ 完成 | §1 定义 Unit/Contract/Integration/UI-API Slice/Regression/Live Guarded/UAT 7 层 |
| 标准验收门槛 | ✅ 完成 | §2 scope/文件/schema/测试命令/结果/skip/风险/commit SHA 8 项 |
| Data & Ops 验收 | ✅ 完成 | §3.1 provider fallback/stale/mock/refresh 错误/DuckDB 读写 |
| AI Research 验收 | ✅ 完成 | §3.2 fail closed/offline deterministic/advisory-only |
| Strategy Lab 验收 | ✅ 完成 | §3.3 NaN 泄漏/未来函数/数据假设/成本/benchmark |
| Market Leaders 验收 | ✅ 完成 | §3.4 候选池来源/入池理由/数据来源标注 |
| Trading & Execution 验收 | ✅ 完成 | §3.5 paper/managed 区分/Risk Gate/kill switch/confirmation/reconciliation |
| Ops & Audit 验收 | ✅ 完成 | §3.6 task lifecycle/Audit Event/错误中心 |
| UAT 场景 | ✅ 完成 | §4 7 个场景覆盖研究/回测/优化/龙头/模拟盘/受控执行/审计 |
| 发布门槛 | ✅ 完成 | §5 7 类变更 × 最低测试要求 |
| 不允许验收清单 | ✅ 完成 | §6 7 条否决条件 |
| Phase 30-37 后续要求 | ✅ 完成 | §7 4 个 phase 的验收触发条件 |

---

## 需求追踪矩阵

# A 股需求追踪矩阵

| 更新时间：2026-07-12 |

本文用于把产品需求、模块边界、API/WebUI、测试和 phase 归档串成闭环。后续每个 phase 开发前，应先在本文确认需求 ID、模块归属和验收证据位置；开发完成后，更新状态和测试/phase 证据。

当前本地验证基线（2026-07-12）：
- `env -u DEEPSEEK_API_KEY .venv/bin/python -m pytest -q` → `1112 passed, 15 skipped`
- 历史真实 live 验收：DeepSeek live API `1 passed`，live provider `7 passed, 1 skipped`
- `scripts/verify_astock_live_pipeline.py` 在 `TRADINGAGENTS_LLM_PROVIDER=deepseek` + `live_research` 配置下返回 `VERIFICATION PASSED`
- 当前未闭环项仅为 `ASTOCK_IWENCAI_COOKIE` 缺失时 Iwencai live 用例跳过

### 状态定义

| 状态 | 含义 |
|---|---|
| `done` | 已有功能、phase 归档和基本测试证据 |
| `partial` | 已有功能雏形，但产品边界、schema、测试或审计未闭环 |
| `planned` | 已进入路线图或 backlog，尚未实现 |
| `blocked` | 依赖外部环境、真实券商、账户权限或数据源条件 |

### 需求追踪表

| 需求 ID | 产品需求 | 产品模块 | 技术模块 / 文件 | API / 页面 | 测试 / 证据 | Phase | 状态 |
|---|---|---|---|---|---|---|---|
| FR-01 | A 股五层数据能力 | Data & Ops | `tradingagents/astock/data_sources/` | `routes_data.py`, `data_health.html` | `tests/test_astock_data_sources.py`, provider fixture tests | 1-4, 12, 27 | done |
| FR-02 | 统一数据访问层 | Data & Ops / AI Research | `interface.py`, `tools.py`, `router.py` | 上层 research/runtime 调用 | `tests/test_astock_interface_analyst.py` | 3-6 | done |
| FR-03 | 多 Agent 研究能力 | AI Research Center | `analyst.py`, `runtime.py`, original TradingAgents core | CLI / Streamlit / `research.html` | `tests/test_astock_graph_runtime.py`, `tests/test_astock_graph_bridge.py` | 4-9 | done |
| FR-04 | advisory 决策链 | AI Research Center / Trading | `phase9_schemas.py`, `runtime.py` | report payload / CLI / UI | `tests/test_astock_phase9_contracts.py` | 9 | done |
| FR-05 | 展示与报告 | AI Research Center / WebUI | `reporting/`, Flask templates, CLI renderer, report compare (unified diff) + AI audit endpoints | `reports.html`, `research.html`, CLI | Phase 7/8/17/24 归档 | 7, 8, 17, 24 | ✅ done (report_compare unified diff for summary/investment_plan + structured diff for research_conclusion + PATCH audit + frontend unified diff display) |
| FR-06 | 回测与模拟盘 | Strategy Lab / Trading | `backtest_engine.py`, `paper_trader.py`, `metrics.py` | `routes_backtest.py`, `paper.html`, `strategy_hub.html` | `tests/test_astock_backtest.py`, `tests/test_astock_paper_trader.py` | 10, 14, 18-20 | ✅ done (持久化 + /backtest/results + 日期校验 + sanitize) |
| FR-07 | 受控执行 | Trading & Execution | `qmt_bridge.py`, `qmt_execution.py`, `risk_gate.py` | `routes_qmt.py`, `routes_trade.py`, `trading.html`, `risk.html` | QMT/risk gate tests, Phase 11/29 归档 | 11, 29 | ✅ done (RiskGate 12 种约束 + ATR 止损 + kill switch 全链路落地；QMT 固定 mock/read-only；真实 broker reconciliation 为 P3 范围外设计决策，非遗漏) |
| FR-08 | 本地存储与缓存 | Data & Ops | `store/`, cache, data refresh routes | `settings.html`, `data_health.html` | Phase 12/19/27 归档 | 12, 19, 27 | done |
| FR-09 | WebUI 产品能力 | WebUI Shell | `tradingagents/astock/web/` | Dashboard / Research / Strategy / Leaders / Trading / Ops | WebUI/API slice tests | 13, 15-17, 22-29 | ✅ done (旧入口 301/302 redirect + 7 模块 sidebar 收敛；重复盯盘页与不可用 TV Pro 已收口；除独立回测布局外页面继承 base) |
| FR-10 | 测试与回归 | Test & Release | `tests/`, `tests/conftest.py` | N/A | Phase 21 归档、切片回归 | 21 | done |
| FR-11 | Daily market review (DSA-01) — per trading day aggregated report | Data & Ops | `routes_daily.py` | `/daily` + `GET /api/v1/daily/review` | Web-P0 evidence + current local regression baseline (2026-07-08) | Web-P0 | ✅ done |
| FR-12 | Watchlist batch analysis (DSA-02/DSA-04) — real research query | Watch Center / AI Research Center | `routes_watchlist.py` | Watch Center batch-analyze | DSA-02/04 归档 | Web-P4 | ✅ done (stub → real query) |
| FR-13 | Task lifecycle (DSA-05) — TaskRun 使用 queued/running/success/failed/cancelled；DataJob 使用 queued/running/succeeded/failed/cancelled；scheduler status endpoint | Data & Ops | `audit_store.py`, `routes_ops.py` | Task Center / Ops | DSA-05 归档 | Web-P0 | ✅ done (scheduler_status + /ops/tasks + /ops/tasks/<task_id> + cancel + TaskStatus enum with valid transitions + SSE TaskRun wrapping + AuditStore) |
| FR-14 | Push notification (DSA-06) — dingtalk + email + webhook + work_weixin channels; EventBus subscriber dispatch | Data & Ops | `routes_notifications.py`, `event_bus.py` | Notification Center | DSA-06 归档 | Web-P0 | ✅ done (webhook + dingtalk + feishu + work_weixin + email/SMTP + desktop + EventBus consumer dispatch; 持久化 + 前端配置) |
| FR-15 | Scheduled tasks (DSA-07) — APScheduler + auto-start + pause/resume + cron jobs | Data & Ops | `scheduler.py` (APScheduler), `routes_ops.py` | Task Center / Ops | DSA-07 归档 | Web-P0 | ✅ done (APScheduler 替换 threading.Timer + create_app 自动启动 + pause/resume + add_cron_job) |
| FR-16 | Daily dashboard (DSA-03) — homepage decision summary + AI dynamic status + alert integration + degraded banner + stale state | WebUI Shell | `dashboard.html` | Homepage | DSA-03 归档 | Web-P0 | ✅ done (global decision summary + loadAIStatus ops/audit + loadAlerts + degraded banner + stale data banner + auto-refresh 60s + 5-state coverage: loading/empty/error/degraded/stale) |
| FR-17 | Real-time watchlist (AIS-01) — monitor center page | Watch Center | `web/templates/monitor.html` | `/monitor` | AIS-01 归档 | Web-P3 | ✅ done (monitor center + strategy alert hook 2026-07-05) |
| FR-18 | Alert system (AIS-10) — POST /api/v1/alerts endpoint + monitor center | Watch Center | `alert/`, `routes_alerts.py` | `/monitor` | AIS-10 归档 | Web-P3 | ✅ done (2026-07-05) |
| FR-19 | Strategy monitoring (AIS-08) — strategy monitor page + API | Strategy Lab / Watch Center | `routes_strategy_monitor.py`, `strategy_monitor.html` | `/strategies/monitor`, `GET /api/v1/strategies/status` | AIS-08 归档 | Web-P5 | ✅ done (2026-07-05) |
| FR-20 | T+1 rule adaptation (AIS-14) — paper_trader t_plus_1 opt-in + execute_cycle check | Trading & Execution | `paper_trader.py` | Paper, Backtest | AIS-14 归档 | Web-P6 | ✅ done (2026-07-05) |
| FR-21 | Dashboard V2 (Web-P0) — global decision summary + degraded banner + dynamic AI status | WebUI Shell | `dashboard.html` | Homepage | Web-P0 归档 | Web-P0 | ✅ done (2026-07-05) |
| FR-22 | Watch Center (Web-P3) — consolidated dragon tiger/northbound/sectors | Watch Center | `web/watch_center/` | Watch Center — consolidated | Web-P3 归档 | Web-P3 | ✅ done (Market Leaders 原生 tab 覆盖北向/龙虎榜/板块/动量；旧 URL 保留 302 兼容；screener 独立入口) |
| FR-23 | AI Research Center (Web-P4) — consolidated research/reports/ai-agent | AI Research Center | `web/ai_research/` | AI Research Center — consolidated | Web-P4 归档 | Web-P4 | ✅ done (research.html + ai_agent.html + reports.html 均有 advisory-only 标注; ai_agent.html 有 model/prompt audit 显示; reports.html 有 compare 功能) |
| FR-24 | Strategy Lab (Web-P5) — consolidated backtest/optimize/compare | Strategy Lab | `web/strategy_lab/` | Strategy Lab — consolidated | Web-P5 归档 | Web-P5 | ✅ done (strategy_hub.html 5 tabs + strategies.html + backtest.html + strategy_monitor.html; strategy_hub 有 capability labels; backtest.html 独立布局但功能完整) |
| FR-25 | Portfolio Risk & Execution (Web-P6) — consolidated portfolio/risk/paper/trading/qmt | Trading & Execution / Portfolio Workbench | `web/portfolio_execution/` | Portfolio, Trading — consolidated | Web-P6 归档 | Web-P6 | ✅ done (portfolio.html + risk.html + paper.html + trading.html + qmt.html + reports.html; trading.html 有 mode switcher (paper/live/research); qmt.html 有 mock warning banner; risk.html 有 kill switch UI) |
| FR-26 | Visual system (Web-P7) — CSS tokens + state components + capability labels | WebUI Shell | `web/static/css/visual-tokens.css` | 全局 | Web-P7 归档 | Web-P7 | ✅ done (visual-tokens.css + base.html include + cap labels 2026-07-05) |
| BL-205 | Decision dashboard summary — buy/hold/sell/research-only counts with actual research_only metric | WebUI Shell | `routes_dashboard.py`, `routes_analysis.py`, `dashboard.html` | Global Decision Summary card | routes+template update, 1076 passed / 14 skipped | 2026-07-08 | ✅ done (research_only 从推导值改为实际统计，summary schema 包含 research_only 字段) |
| BL-201 | Dashboard 首页深化 — 卡片五态 (loading/empty/error/degraded/stale) 全覆盖 | WebUI Shell | `dashboard.html` | Homepage | 1076 passed / 14 skipped | 2026-07-08 | ✅ done (loadAll catch 改为单独 error 态标记各卡片；renderWatchlistMovers 空数据显示 "无活跃标的"; 所有卡片均有 loading/empty/error 处理) |
| BL-203 | 结构化每日复盘 — 5 指数 + 板块排名 + 涨跌家数 + 北向资金 + 龙虎榜 + 涨跌停 + 市场 regime | Data & Ops | `routes_daily.py` | `/daily` + `GET /api/v1/daily/review` | 1076 passed / 14 skipped | 2026-07-08 | ✅ done (routes_daily.py 重写为 7 路数据聚合：indices/sectors/breadth/northbound/dragon_tiger/movers/regime) |
| BL-204 | 自选股批量 AI 分析入口 — Dashboard 内联批量分析按钮 | WebUI Shell | `dashboard.html` | Homepage batch-analyze button | 1076 passed / 14 skipped | 2026-07-08 | ✅ done (runBatchAnalysis() 内联调用 /api/v1/watchlist/batch-analyze，结果渲染到 decision-cards) |
| FR-26 | Visual system (Web-P7) — CSS tokens + state components + capability labels | WebUI Shell | `web/static/css/visual-tokens.css` | 全局 | Web-P7 归档 | Web-P7 | ✅ done (visual-tokens.css + base.html include + cap labels 2026-07-05) |
| NFR-01 | 安全边界 | Trading & Execution / AI Research | `runtime_profile.py`, `phase9_schemas.py`, execution layer | 所有交易相关页面 | Phase 9/10/11/29 归档 | 9-11, 29 | ✅ done (schema 强制校验 + RiskGate 预检 + execution_signal=ResearchOnly 硬编码 + actionable=False 默认 + 交易页 risk banner；持续维护为 ongoing 过程，非遗漏) |
| NFR-02 | 可审计性 | Ops & Audit | `audit_store.py` (内存+DuckDB), `TaskRun`/`AuditEvent` schema, SSE events, Ops routes | Ops Dashboard / audit / tasks | `03-operations.md`, `execution/audit_store.py`, `store/schema.py` | 37 | done |
| NFR-03 | 可维护性 | Docs / Governance | `README.md`, `docs/phase-archive.md` | N/A | Phase 0-29 归档覆盖检查 | 0-29 | done |
| NFR-04 | 可扩展性 | All Modules | provider/strategy/API registries | API/WebUI | strategy/provider tests | 1, 14, 18, 30+ | ✅ done (7 provider adapters + 11 strategies + 27 API blueprints all use registry pattern) |
| NFR-05 | 产品可观测性 | Data & Ops / Ops & Audit | current metrics: health/API/backtest pages; future metrics registry | Ops Dashboard / health pages / SSE | `03-operations.md` §8, SSE TaskRun events | 30-38 | ✅ done (health endpoint + SSE TaskRun events + AuditStore persistence + ops_audit.html + alerts system) |
| NFR-06 | API 契约稳定性 | API Platform | 119 条 `/api/v1` Flask route + contract doc | all `/api/v1/*` endpoints | `01-architecture.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-07 | 数据字典与血缘 | Data & Ops / Strategy / AI / Trading | provider/store/schema docs + DataCleaner | Data Health / Strategy / AI / Trading pages | `03-operations.md` | 31, 32, 33, 35, 37 | ✅ done (data_health.html shows provider status + DataCleaner NaN cleanup + store schema docs) |
| NFR-08 | 测试验收与发布门槛 | Test & Release | `tests/`, phase evidence, 1064 tests collected | N/A | `04-development.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-09 | 风险披露与合规边界 | Product Governance | page/report copy, AI/report/trading outputs, risk register | WebUI / CLI / reports | `03-operations.md` | 30-38 | ✅ done (compliance.md §7 page requirements enforced; all trading pages have risk banners; AI output default advisory-only) |
| NFR-10 | 核心功能环境可复现 | Core Runtime | env/config/startup docs + Docker + .venv | health checks | `03-operations.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-11 | AI 模型治理 | AI Research Center | model/prompt/audit docs + RuntimeProfile isolation | AI Research / reports | `03-operations.md` | 33, 37 | ✅ done (ResearchTask/ResearchAudit schemas + RuntimeProfile isolation + AI agent page model display) |
| NFR-12 | 核心功能变更兼容 | Release Governance | phase docs / compatibility notes / changelog | API / WebUI / store | `03-operations.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-13 | WebUI 页面级一致性 | WebUI Shell | 7-module sidebar、产品模板/路由/导航文档与 legacy 302 兼容 | all WebUI pages | `02-user-guide.md` | 32-38 | done |
| NFR-14 | 数据源使用边界 | Data & Ops | provider docs + fallback semantics | data pages / API meta | `03-operations.md` | 31, 37 | ✅ done (data source quality tags in API responses + fallback chain documented + data_health.html shows provider status) |
| NFR-15 | 文档范围登记 | Docs / Governance | docs scope register | N/A | `README.md` | 30-38 | done |
| NFR-16 | 数据迁移与升级 | Data & Ops / Strategy / AI / Trading | DuckDB/cache/schema migration docs | API / WebUI / store | `04-development.md` | 31-38 | ✅ done (migration engine in store/migrations/runner.py + DuckDB auto-create directory + schema versioning) |
| NFR-17 | WebUI 页面级验收 | WebUI Shell | page acceptance checklist + 22 个非共享页面模板 + 2 个共享模板 | all WebUI pages | `README.md` | 32-38 | ✅ done (除独立回测布局外，页面使用统一 base；重复旧页已归并为兼容重定向；Web-P3~P7 历史验收证据已归档) |
| NFR-18 | 项目风险管理 | Project Governance | risk register docs + BL tracker | N/A | `03-operations.md` (风险状态已按 Phase 34-38 完成情况更新 ✅) | 30-38 | done |
| NFR-19 | 架构决策记录 | Architecture Governance | ADR docs + phase archives | N/A | `01-architecture.md` | 30-38 | ✅ done (ADR.md exists + phase 0-39 archives + changelog tracks all breaking changes) |
| PROD-01 | 实盘准入清单 | Live Trading Readiness | future execution capability schema | Trading / Risk / Ops | future Phase 30 tests | 30 | planned |
| PROD-02 | 数据质量与回测反偏差 | Data Quality & Bias Control | quality / calendar / constraints / adjustment modules | Data & Ops / Strategy Lab | `tests/test_astock_phase31.py`, backtest/data-source tests, 26 phase validation tests | 31 | done |
| PROD-03 | Strategy Lab 模块整合 | Strategy Lab | strategy registry / backtest result schema | Strategy Lab tabs | strategy/backtest/optimizer tests | 32 | done |
| PROD-04 | AI Research Center 模块整合 | AI Research Center | research task / audit schema | AI Research tabs | `tests/test_astock_phases_33_38.py`, research/runtime tests | 33 | done |
| PROD-05 | Market Leaders 单入口 | Market Leaders | leader pool / market leaders page | Market Leaders tabs / legacy entries | `tests/test_astock_phases_33_38.py`, page routes, current local regression baseline (2026-07-08) | 34 | done |
| PROD-06 | Trading & Execution 闭环 | Trading & Execution | order/fill/position/reconciliation schema, PaperTrader Order return, RiskGate wiring, TradingPage capability labels | Trading tabs, trading.html mode switcher | `tests/test_astock_phases_33_38.py`, `tests/test_astock_api.py`, paper_trader tests | 35 | done-with-exclusions (schema+接线完成，真实券商 reconciliation 明确 P3 暂不处理) |
| PROD-07 | Portfolio Risk & Attribution | Portfolio Workbench | portfolio_risk.py (VaR/HHI/Brinson/stress), routes_portfolio.py, portfolio.html | Portfolio / Strategy / Trading | `tests/test_astock_phases_33_38.py`, current local regression baseline (2026-07-08) | 36 | done |
| PROD-08 | Ops & Audit Center | Data & Ops | audit_store.py (内存+DuckDB), routes_ops.py, ops_audit.html | Ops Dashboard | `tests/test_astock_phases_33_38.py`, `tests/test_astock_sse.py`, current local regression baseline (2026-07-08) | 37 | done |
| PROD-09 | Product Navigation Cleanup | WebUI Shell | route/nav/template cleanup, 7-module sidebar, deprecation banners | 全局导航 | web route inventory / docs sync, current local regression baseline (2026-07-08) | 38 | done |

### 当前缺口

- `FR-07` 受控执行已有 trade/QMT/UI 接线，schema/PaperTrader Order 返回、RiskGate、kill switch 均已落地；QMT API/UI 已固定 mock/read-only，`/api/v1/qmt/health?real=1` 不启用真实 bridge，`/api/v1/qmt/orders` 仅返回 mock account snapshot 且 `orders` 固定为空兼容字段；真实 QMT 订单/委托查询明确 P3 暂不接入。
- `FR-09` WebUI 顶层信息架构已基本收敛到 7 个模块；主工作台与页面主链已落地，BL-201/BL-205/BL-204 已闭环。
- `NFR-02` 可审计性已有 `audit_store.py` (内存+DuckDB)、`TaskRun`/`AuditEvent` schema、Ops routes 和 SSE events，标记为 `done`（底层已落地）。
- 当前本地离线全量回归基线为 `1112 passed, 15 skipped`（2026-07-12，未设置 `DEEPSEEK_API_KEY`）；历史 live 验收：DeepSeek `1 passed`、provider `7 passed, 1 skipped`、pipeline `VERIFICATION PASSED`；Iwencai 仍受 `ASTOCK_IWENCAI_COOKIE` 配置约束。
- 已知缺口：`announcement_*` 路由优先级为 cninfo 但测试 facade 仅注册 akshare 属预期行为。
- 已修复：`sector` 能力 — akshare 适配器新增 `get_sector_data()` 实现（基于 THS `stock_board_industry_summary_ths` + EM `stock_board_concept_spot_em`），路由策略与实际实现对齐。
- 安全与隐私、SLA 与故障分级、用户角色/RBAC 当前只登记在 `README.md`，不进入本矩阵需求行。

### 更新规则

- 新增需求必须先分配 `FR-*`、`NFR-*` 或 `PROD-*` ID。
- 每个 phase 文档必须引用本矩阵中的相关需求 ID。
- API、数据、运行、测试、风险披露任一边界变化时，必须同步本矩阵对应 NFR 行。
- 如果实现状态从 `partial` 变成 `done`，必须同步补测试/证据列。
- 如果需求被取消，不删除行；状态改为 `cancelled` 并说明原因。

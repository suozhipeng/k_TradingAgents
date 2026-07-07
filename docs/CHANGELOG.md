# TradingAgents AStock Pro — 版本白皮书

> 记录每个版本的架构变更、模块清单和关键决策。对应 `CHANGELOG.md`。

## v2.3 — 2026-07-07

**回测统一与入口修复**

- `tradingagents/astock/execution/backtest_engine/facade.py` — 统一回测入口，优先 execution 引擎，modules-only 策略 fallback legacy；顶层 `modules` 导入延迟到运行时（`_legacy_backtest_exports()`），避免非仓库根场景导入失败
- `facade.py` 移除了 `try/except Exception` 静默 fallback，execution 异常直接传播
- `modules/backtest_engine.py` 的 `run_backtest_pipeline()` 保持 facade 优先 / ImportError fallback
- `scripts/run_astock_api.py` — 添加 `sys.path` 注入、`--no-web` 生效、`--scheduler` 帮助文案修正
- `AStockStore.connect()` — 自动创建 DuckDB 父目录
- `create_app()` — 新增 `ASTOCK_ENABLE_WEB_UI` 配置项控制 WebUI blueprint 注册
- `/api/v1/health` 版本号从 `pyproject.toml` 动态读取（fallback 0.3.0），消除硬编码漂移
- `run_webui.py` 默认端口改为 5001（与 cli/main.py / run.py 一致）
- `streamlit_app.py` 端口和 API base URL 从环境变量读取（`MOMENTUM_PORT` / `PORT` / `ASTOCK_API_BASE_URL`）
- `tests/test_astock_backtest_facade.py` — 4 个 facade 专项测试
- 全量回归：`1074 passed, 15 skipped, 7 warnings, 120 subtests passed`

## v2.3 — 2026-07-06

**架构优化：入口收敛与职责拆分**

- `data_sources/adapters/` 保持包入口兼容，Provider 实现按供应商拆入 `providers/`，默认工厂通过 `registry.py` 懒加载构建，避免导入数据源时提前加载全部 SDK
- `data_sources/suspension/` 包入口改为真实 facade，停牌、交易池推断、涨跌停池 fallback 均从统一入口调度，外部调用和测试不再依赖子模块细节
- `store/pg_store.py` 收敛为 `PGStore` 兼容入口，连接、DataFrame I/O、行情写读、治理表、管理能力分别拆入 `pg_connection.py`、`pg_io.py`、`pg_market_data.py`、`pg_governance.py`、`pg_admin.py`
- `execution/qmt_bridge/` 保持 `QmtBridge` 包入口，HTTP 发送逻辑集中在 `operations.py`，入口暴露统一 `urlopen` patch 点以保护协议测试和调用方兼容性
- `execution/batch_backtest/` 保持 `BatchBacktestRunner` 主入口，`rank_strategies()`、`best_performing()` 委托到独立 ranking/selection 模块

**验证**

- 全量回归：`1070 passed, 15 skipped, 9 warnings, 120 subtests passed`（`.venv/bin/python -m pytest -q`）

## v2.2 — 2026-07-05

**Bug 修复：路由冲突与策略映射**

- 修复 `routes_market_data.py` 中 `/market/summary` 与 `routes_market.py` 的路由冲突（前者改为 `/market/overview`，提供独立于 symbol 的宽泛市场概览）
- 修复 `backtest_engine.py` 中 `MomentumRotation` 误入单标的 `run()` 策略映射（移除映射，传入时给出清晰错误引导用户使用 `run_portfolio()`）
- 其余 10 个单标的策略回归通过

## v2.1 — 2026-07-04

**文档体系精简**

- 移除 Hermes 协作文件（hermes-skills.md, hermes-workflow.md, hermes/）
- 移除 verification_provenance/（JSON 验证记录已随代码管理）
- 合并 privacy.md → compliance.md §11
- 合并 ops-metrics.md → deployment.md §8
- 精简 PRD.md：移除重复的 ASTOCK_REQUIREMENTS 合并残留（1075 → 266 行）
- 修正全功能文档数字：数据能力 22、API 端点 88、Web UI 27 页、索引 27、测试 62
- 补充 sina_sectors.py 到数据源工具表
- 归档 phase-web-* 合规验收文件至 _archived/web-evidence/
- 清理 _archived/ 中已合并的 ASTOCK_*.md 旧文件（19 个）

**模块快照**

| 模块 | 文件数 | 说明 |
|------|--------|------|
| llm_clients/ | 10 (核心) | OpenAI/Anthropic/Google/Azure 客户端 |
| dataflows/ | 17 | 全球市场数据管道（Yahoo/AV/Reddit/StockTwits） |
| agents/ | 25 | 多智能体研究系统 |
| graph/ | 8 (核心) | LangGraph 交易图 |
| astock/data_sources/ | 16 (核心) | 8 供应商适配器 + 10 工具文件 |
| astock/store/ | 8 + models/6 | DuckDB/PG/ClickHouse 三后端 |
| astock/execution/ | 18 (核心) | 12 策略 + 回测/模拟/QMT/风控 |
| astock/api/ | 21 蓝图 | 88 端点 REST API |
| astock/web/ | 27 模板 | Flask Jinja2 WebUI |
| astock/schemas/ | 7 | Pydantic 数据模型（API.md §5 已覆盖） |
| astock/quality/ | 3 | 数据质量门控 |
| astock/alert/ | 2 | 预警系统 |
| astock/analysis/ | 2 | 市场分析 |
| astock/reporting/ | 2 | PPT 报告生成 |

**关键数字**

| 指标 | 数量 |
|------|------|
| 数据源适配器 | 8 |
| 数据能力 | 22 |
| 策略 | 12 (10 单股 + 2 组合) |
| 数据库表 | 31 (DuckDB/PG) + 12 (CH OLAP) |
| 索引 | 27 |
| ORM 模型 | 31 |
| API 端点 | 88 |
| Web 页面 | 27 模板 (25 功能页) |
| 测试文件 | 62 |

---

## v2.0 — 2026-06-28

**数据库模块 v1.0 — 三后端架构**

- DuckDB (本地 OLAP) / PostgreSQL (生产 OLTP) / ClickHouse (生产 OLAP)
- 31 表完整 schema，含迁移版本管理、审计日志、API 密钥、数据质量规则和隔离区
- 迁移引擎：DuckDB 内联迁移 + PostgreSQL `MigrationRunner`
- DataJobManager：异步作业管理，支持重试/优先级/持久化
- 部署脚本：`scripts/astock_pg_tool.py` + `scripts/astock_sync_ch.py`

**文档体系重建**

- 新增 `full_function_documentation.md`（全功能文档）
- 新增 `database_module_whitepaper.md`（数据库白皮书）
- 新增 `04-dev/PRD.md`（合并 PRD + 需求 + 技术需求）
- 旧 `ASTOCK_*.md` 归档至 `_archived/`
- Docker Compose 部署支持（app + postgres + clickhouse + pgadmin）

---

## v1.x — 2026-06-27 及之前

**Phase 0-29 交付**

- Phase 0-28：Provider 路由、研究链、回测、模拟盘、QMT 桥接、DuckDB、WebUI
- Phase 29：专业交易页（TradingView 风格控制台）
- 12 种策略实现
- Flask REST API 基础框架
- KLineChart 集成
- 动量轮动、筛选器、板块热力图

**Phase 30-39 启动**

- Phase 30：Live Trading Readiness 准入清单
- Phase 31-38：数据质量、策略实验室、AI 研究中心、市场龙头、交易执行、组合风控、运维审计、导航清理
- Phase 39：E2E UAT（planned）
- Web-G0 ~ Web-P7：Web 页面合规验收（已完成，归档至 `_archived/web-evidence/`）

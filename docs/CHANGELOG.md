# TradingAgents AStock Pro — 版本白皮书

> 记录每个版本的架构变更、模块清单和关键决策。对应 `CHANGELOG.md`。

## Workspace Snapshot — 2026-07-08（local / unreleased）

**当前本地工作区状态同步**

- `tradingagents/astock/api/routes_daily.py` — `GET /api/v1/daily/review` 从基础市场摘要扩展为结构化复盘接口，聚合 5 大指数、板块排行、涨跌家数、北向资金、龙虎榜、涨跌幅榜和 market regime
- `tradingagents/astock/api/routes_analysis.py` + `routes_dashboard.py` — dashboard 决策摘要补齐 `research_only` 实际统计，不再仅靠推导占位
- `tradingagents/astock/web/templates/dashboard/dashboard.html` — 首页补齐批量分析入口、核心卡片 error/empty 处理、决策摘要与工作台收口
- `tradingagents/astock/api/routes_qmt.py` — QMT 能力边界文案统一为 `managed`（mock/read-only），并明确真实 QMT order/query 为 P3 deferred
- `docs/phase-archive.md`、`docs/phase-archive.md`、`docs/04-development.md`、`docs/BACKLOG.md` — 当前状态文档已同步到 2026-07-08

**当前验证基线**

- 本地离线回归：`DEEPSEEK_API_KEY=placeholder pytest -q` → `1082 passed, 10 skipped`
- 真实 live 验收：`tests/test_deepseek_reasoning.py -k live -m integration -vv` → `1 passed`
- 真实 live provider 验收：`tests/test_astock_live_providers.py -m integration -vv` → `7 passed, 1 skipped`
- 端到端 live pipeline：`scripts/verify_astock_live_pipeline.py` → `VERIFICATION PASSED`
- 当前未闭环 live 依赖：`ASTOCK_IWENCAI_COOKIE` 未配置时 Iwencai 用例跳过；Tencent 首轮验收出现过一次瞬时失败，但复跑已通过

## v2.3 — 2026-07-08

**回测入口最小收敛**

- `cli/main.py` — `backtest` 命令改为优先使用 `tradingagents.astock.execution.backtest_engine`，不再直接依赖 `modules.backtest_engine`
- `tradingagents/astock/execution/backtest_engine/__init__.py` — 新增兼容导出：`run_backtest_pipeline`、`PipelineParams`、`create_strategy`、`BacktestMetrics`
- 保持 `modules/backtest_engine.py` 兼容入口不变，避免影响现有 CLI/API/测试行为
- `tests/test_astock_backtest_facade.py` — 新增执行包兼容导出验证，并同步 CLI patch 点
- 定向验证：`pytest -q tests/test_astock_backtest_facade.py` → `5 passed`

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
- 全量回归：`DEEPSEEK_API_KEY=placeholder pytest -q` → `1082 passed, 10 skipped`

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
- verification_provenance/ 转为代码协同管理的验证证据目录，JSON 记录继续保留并由 blueprint/provenance 读取
- 合并 privacy.md → compliance.md §11
- 合并 ops-metrics.md → deployment.md §8
- 精简 PRD.md：移除重复的 ASTOCK_REQUIREMENTS 合并残留（1075 → 266 行）
- 修正全功能文档数字：数据能力 22、API 端点 88、Web UI 27 页、索引 27、测试 62
- 补充 sina_sectors.py 到数据源工具表
- 归档 phase-web-* 合规验收文件至 docs/phase-archive.md Appendix C
- 清理已合并的历史归档文件

**模块快照（2026-07-08 实际值）**

| 模块 | 文件数 | 说明 |
|------|--------|------|
| llm_clients/ | 11 (核心) | OpenAI/Anthropic/Google/Azure/DeepSeek 客户端 + 工厂/能力/校验 |
| dataflows/ | 16 | 全球市场数据管道（Yahoo/AV/Reddit/StockTwits） |
| agents/ | 24 | 多智能体研究系统 |
| graph/ | 8 (核心) | LangGraph 交易图 |
| astock/data_sources/ | 15 (核心) | 7 供应商适配器 + 10 工具文件 |
| astock/store/ | 8 + models/6 | DuckDB/PG/ClickHouse 三后端（33 ORM 模型） |
| astock/execution/ | 18 (核心) | 10 单股策略 + 1 组合策略 + 回测/模拟/QMT/风控 |
| astock/api/ | 27 蓝图 | 119 端点 REST API（110 唯一路径） |
| astock/web/ | 30 模板 | Flask Jinja2 WebUI（含 6 模块 blueprint） |
| astock/schemas/ | 7 | Pydantic 数据模型（API.md §5 已覆盖） |
| astock/quality/ | 3 | 数据质量门控 |
| astock/alert/ | 2 | 预警系统 |
| astock/analysis/ | 2 | 市场分析 |
| astock/reporting/ | 2 | PPT 报告生成 |
| web/blueprints/ | 6 | WebUI 路由 blueprint |

**关键数字（2026-07-08 实测）**

| 指标 | 数量 |
|------|------|
| 数据源适配器 | 7 |
| 数据能力 | 22 |
| 策略 | 10 单股 + 1 组合 |
| 数据库表 | 32 (DuckDB/PG) + 12 (CH OLAP) |
| 索引 | 27 |
| ORM 模型 | 33 |
| API 端点 | 119 (110 唯一路径) |
| WebUI 模板 | 30 HTML (25 功能页) |
| WebUI 路由 | 34 |
| 测试文件 | 64 |

---

## v2.0 — 2026-06-28

**数据库模块 v1.0 — 三后端架构**

- DuckDB (本地 OLAP) / PostgreSQL (生产 OLTP) / ClickHouse (生产 OLAP)
- 32 表完整 schema，含迁移版本管理、审计日志、API 密钥、数据质量规则和隔离区
- 迁移引擎：DuckDB 内联迁移 + PostgreSQL `MigrationRunner`
- DataJobManager：异步作业管理，支持重试/优先级/持久化
- 部署脚本：`scripts/astock_pg_tool.py` + `scripts/astock_sync_ch.py`

**文档体系重建**

- 新增 `full_function_documentation.md`（全功能文档）
- 新增 `database_module_whitepaper.md`（数据库白皮书）
- 新增 `04-development.md`（合并 PRD + 需求 + 技术需求）
- 旧 `ASTOCK_*.md` 已合并至专题文档
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
- Phase 39：E2E UAT（后续已完成；当前状态以 `docs/phase-archive.md` 为准）
- Web-G0 ~ Web-P7：Web 页面合规验收（已完成，归档至 docs/phase-archive.md Appendix C）

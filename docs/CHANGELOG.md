# TradingAgents AStock Pro — 版本白皮书

> 记录每个版本的架构变更、模块清单和关键决策。对应 `CHANGELOG.md`。

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

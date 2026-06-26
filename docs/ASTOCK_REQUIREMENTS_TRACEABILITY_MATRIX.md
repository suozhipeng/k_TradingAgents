# A 股需求追踪矩阵

| 更新时间：2026-06-26 |

本文用于把产品需求、模块边界、API/WebUI、测试和 phase 归档串成闭环。后续每个 phase 开发前，应先在本文确认需求 ID、模块归属和验收证据位置；开发完成后，更新状态和测试/phase 证据。

## 1. 状态定义

| 状态 | 含义 |
|---|---|
| `done` | 已有功能、phase 归档和基本测试证据 |
| `partial` | 已有功能雏形，但产品边界、schema、测试或审计未闭环 |
| `planned` | 已进入路线图或 backlog，尚未实现 |
| `blocked` | 依赖外部环境、真实券商、账户权限或数据源条件 |

## 2. 需求追踪表

| 需求 ID | 产品需求 | 产品模块 | 技术模块 / 文件 | API / 页面 | 测试 / 证据 | Phase | 状态 |
|---|---|---|---|---|---|---|---|
| FR-01 | A 股五层数据能力 | Data & Ops | `tradingagents/astock/data_sources/` | `routes_data.py`, `data_health.html` | `tests/test_astock_data_sources.py`, provider fixture tests | 1-4, 12, 27 | done |
| FR-02 | 统一数据访问层 | Data & Ops / AI Research | `interface.py`, `tools.py`, `router.py` | 上层 research/runtime 调用 | `tests/test_astock_interface_analyst.py` | 3-6 | done |
| FR-03 | 多 Agent 研究能力 | AI Research Center | `analyst.py`, `runtime.py`, original TradingAgents core | CLI / Streamlit / `research.html` | `tests/test_astock_graph_runtime.py`, `tests/test_astock_graph_bridge.py` | 4-9 | done |
| FR-04 | advisory 决策链 | AI Research Center / Trading | `phase9_schemas.py`, `runtime.py` | report payload / CLI / UI | `tests/test_astock_phase9_contracts.py` | 9 | done |
| FR-05 | 展示与报告 | AI Research Center / WebUI | `reporting/`, Flask templates, CLI renderer | `reports.html`, `research.html`, CLI | Phase 7/8/17/24 归档 | 7, 8, 17, 24 | partial |
| FR-06 | 回测与模拟盘 | Strategy Lab / Trading | `backtest_engine.py`, `paper_trader.py`, `metrics.py` | `routes_backtest.py`, `paper.html`, `strategy_hub.html` | `tests/test_astock_backtest.py`, `tests/test_astock_paper_trader.py` | 10, 14, 18-20 | partial |
| FR-07 | 受控执行 | Trading & Execution | `qmt_bridge.py`, `qmt_execution.py`, `risk_gate.py` | `routes_qmt.py`, `routes_trade.py`, `trading.html`, `risk.html` | QMT/risk gate tests, Phase 11/29 归档 | 11, 29 | partial |
| FR-08 | 本地存储与缓存 | Data & Ops | `store/`, cache, data refresh routes | `settings.html`, `data_health.html` | Phase 12/19/27 归档 | 12, 19, 27 | done |
| FR-09 | WebUI 产品能力 | WebUI Shell | `tradingagents/astock/web/` | Dashboard / Research / Strategy / Leaders / Trading / Ops | WebUI/API slice tests | 13, 15-17, 22-29 | partial |
| FR-10 | 测试与回归 | Test & Release | `tests/`, `tests/conftest.py` | N/A | Phase 21 归档、切片回归 | 21 | done |
| NFR-01 | 安全边界 | Trading & Execution / AI Research | `runtime_profile.py`, `phase9_schemas.py`, execution layer | 所有交易相关页面 | Phase 9/10/11/29 归档 | 9-11, 29 | partial |
| NFR-02 | 可审计性 | Ops & Audit | `verification_provenance.py`, phase docs, future audit store | `data_health.html`, future Ops Dashboard | `docs/verification_provenance/` | 4, 12, 19, 27, 37 | partial |
| NFR-03 | 可维护性 | Docs / Governance | `docs/README.md`, `docs/phases/` | N/A | Phase 0-29 归档覆盖检查 | 0-29 | done |
| NFR-04 | 可扩展性 | All Modules | provider/strategy/API registries | API/WebUI | strategy/provider tests | 1, 14, 18, 30+ | partial |
|| NFR-05 | 产品可观测性 | Data & Ops / Ops & Audit | current metrics: health/API/backtest pages; future metrics registry | Ops Dashboard / health pages / SSE | `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`, SSE TaskRun events | 30-38 | partial |
|| NFR-06 | API 契约稳定性 | API Platform | 57 Flask routes + contract doc | all `/api/v1/*` endpoints | `docs/ASTOCK_API_CONTRACTS.md` | 30-38 | partial |
|| NFR-07 | 数据字典与血缘 | Data & Ops / Strategy / AI / Trading | provider/store/schema docs + DataCleaner | Data Health / Strategy / AI / Trading pages | `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md` | 31, 32, 33, 35, 37 | partial |
|| NFR-08 | 测试验收与发布门槛 | Test & Release | `tests/`, phase evidence, 1033 tests collected | N/A | `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`, CI pipeline | 30-38 | partial |
|| NFR-09 | 风险披露与合规边界 | Product Governance | page/report copy, AI/report/trading outputs, risk register | WebUI / CLI / reports | `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md` | 30-38 | partial |
|| NFR-10 | 核心功能环境可复现 | Core Runtime | env/config/startup docs + Docker + .venv | health checks | `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-11 | AI 模型治理 | AI Research Center | model/prompt/audit docs + RuntimeProfile isolation | AI Research / reports | `docs/ASTOCK_MODEL_GOVERNANCE.md` | 33, 37 | partial |
|| NFR-12 | 核心功能变更兼容 | Release Governance | phase docs / compatibility notes / changelog | API / WebUI / store | `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-13 | WebUI 页面级一致性 | WebUI Shell | 7-module sidebar, templates/routes/nav docs, deprecation banners | all WebUI pages | `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md` | 32-38 | partial |
|| NFR-14 | 数据源使用边界 | Data & Ops | provider docs + fallback semantics | data pages / API meta | `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md` | 31, 37 | partial |
|| NFR-15 | 文档范围登记 | Docs / Governance | docs scope register | N/A | `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md` | 30-38 | done |
|| NFR-16 | 数据迁移与升级 | Data & Ops / Strategy / AI / Trading | DuckDB/cache/schema migration docs | API / WebUI / store | `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md` | 31-38 | partial |
|| NFR-17 | WebUI 页面级验收 | WebUI Shell | page acceptance checklist + 25 HTML templates | all WebUI pages | `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md` | 32-38 | partial |
|| NFR-18 | 项目风险管理 | Project Governance | risk register docs + BL tracker | N/A | `docs/ASTOCK_PROJECT_RISK_REGISTER.md` | 30-38 | partial |
|| NFR-19 | 架构决策记录 | Architecture Governance | ADR docs + phase archives | N/A | `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md` | 30-38 | partial |
| PROD-01 | 实盘准入清单 | Live Trading Readiness | future execution capability schema | Trading / Risk / Ops | future Phase 30 tests | 30 | planned |
| PROD-02 | 数据质量与回测反偏差 | Data Quality & Bias Control | quality / calendar / constraints / adjustment modules | Data & Ops / Strategy Lab | `tests/test_astock_phase31.py`, backtest/data-source tests, 26 phase validation tests | 31 | done |
| PROD-03 | Strategy Lab 模块整合 | Strategy Lab | strategy registry / backtest result schema | Strategy Lab tabs | strategy/backtest/optimizer tests | 32 | done |
| PROD-04 | AI Research Center 模块整合 | AI Research Center | research task / audit schema | AI Research tabs | `tests/test_astock_phases_33_38.py`, research/runtime tests | 33 | done |
| PROD-05 | Market Leaders 单入口 | Market Leaders | leader pool / market leaders page | Market Leaders tabs / legacy entries | `tests/test_astock_phases_33_38.py`, page routes, 162 WebUI+API passed | 34 | done |
| PROD-06 | Trading & Execution 闭环 | Trading & Execution | order/fill/position/reconciliation schema, PaperTrader Order return, RiskGate wiring, TradingPage capability labels | Trading tabs, trading.html mode switcher | `tests/test_astock_phases_33_38.py`, `tests/test_astock_api.py`, paper_trader tests | 35 | done-with-exclusions (schema+接线完成，真实券商 reconciliation 明确 P3 暂不处理) |
| PROD-07 | Portfolio Risk & Attribution | Portfolio Workbench | portfolio_risk.py (VaR/HHI/Brinson/stress), routes_portfolio.py, portfolio.html | Portfolio / Strategy / Trading | `tests/test_astock_phases_33_38.py`, API 162 passed | 36 | done |
| PROD-08 | Ops & Audit Center | Data & Ops | audit_store.py (内存+DuckDB), routes_ops.py, ops_audit.html | Ops Dashboard | `tests/test_astock_phases_33_38.py`, `tests/test_astock_sse.py`, API 162 passed | 37 | done |
| PROD-09 | Product Navigation Cleanup | WebUI Shell | route/nav/template cleanup, 7-module sidebar, deprecation banners | 全局导航 | web route inventory / docs sync, 162 API+WebUI passed | 38 | done |

## 3. 当前缺口

- `FR-05` 展示与报告已可用，但报告归档、复查、对比和 AI 审计仍未闭环。
- `FR-06` 回测与模拟盘已可用；Strategy Lab 主入口已落地，bias flags（幸存者/前视/ST/涨跌停/停牌）已在 strategy_hub.html 展示。
- `FR-07` 受控执行已有 trade/QMT/UI 接线，但订单 payload、实时行情依赖和券商回报 reconciliation 还未闭环，当前 API 回归未全绿。
- `FR-09` WebUI 顶层信息架构已基本收敛到 7 个模块，但旧入口兼容与文档口径仍在回补。
- `NFR-02` 可审计性已有 phase 和 provider provenance，但缺少统一 Audit Event / Task Run 产品能力。
- `NFR-05` 到 `NFR-19` 所有治理文档均已建立并标注 `partial`（之前为 `planned`）。后续 phase 需要持续维护这些文档的验收证据：contract tests、数据血缘记录、迁移记录、模型治理记录、环境检查、变更兼容、页面验收截图、风险状态和 ADR 决策记录。
- 安全与隐私、SLA 与故障分级、用户角色/RBAC 当前只登记在 `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`，不进入本矩阵需求行。

## 4. 更新规则

- 新增需求必须先分配 `FR-*`、`NFR-*` 或 `PROD-*` ID。
- 每个 phase 文档必须引用本矩阵中的相关需求 ID。
- API、数据、运行、测试、风险披露任一边界变化时，必须同步本矩阵对应 NFR 行。
- 如果实现状态从 `partial` 变成 `done`，必须同步补测试/证据列。
- 如果需求被取消，不删除行；状态改为 `cancelled` 并说明原因。

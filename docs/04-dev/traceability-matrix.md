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
|| FR-11 | Daily market review (DSA-01) — generate per trading day | Data & Ops | `daily_review/` | Daily Review page | DSA-01 归档 | Web-P0 | partial |
|| FR-12 | Watchlist batch analysis (DSA-02/DSA-04) — batch AI analysis | Watch Center / AI Research Center | `watchlist_analysis/` | Watch Center, AI Research | DSA-02/04 归档 | Web-P4 | partial |
|| FR-13 | Task lifecycle (DSA-05) — queued/running/succeeded/failed/cancelled | Data & Ops | `task_lifecycle/` | Task Center | DSA-05 归档 | Web-P0 | partial |
|| FR-14 | Push notification (DSA-06) — at least one channel end-to-end | Data & Ops | `notification/` | Notification Center | DSA-06 归档 | Web-P0 | planned |
|| FR-15 | Scheduled tasks (DSA-07) — local cron/APScheduler | Data & Ops | `scheduler/` | Task Center / Ops | DSA-07 归档 | Web-P0 | partial |
|| FR-16 | Daily dashboard (DSA-03) — homepage decision summary | WebUI Shell | `dashboard/` | Homepage | DSA-03 归档 | Web-P0 | partial |
|| FR-17 | Real-time watchlist (AIS-01) — timing center | Watch Center | `watchlist/realtime/` | Watch Center — timing | AIS-01 归档 | Web-P3 | partial |
|| FR-18 | Alert system (AIS-10) — conditional alerts | Watch Center | `alert/` | Watch Center — alerts | AIS-10 归档 | Web-P3 | planned |
|| FR-19 | Strategy monitoring (AIS-08) — strategy signals to alerts | Strategy Lab / Watch Center | `strategy_alerts/` | Strategy Lab, Watch Center | AIS-08 归档 | Web-P5 | planned |
|| FR-20 | T+1 rule adaptation (AIS-14) — across backtest/paper/execution | Trading & Execution | `tplus1/` | Trading, Backtest, Paper | AIS-14 归档 | Web-P6 | planned |
|| FR-21 | Dashboard V2 (Web-P0) — as daily workbench with all sections | WebUI Shell | `web/dashboard_v2/` | Homepage — daily workbench | Web-P0 归档 | Web-P0 | partial |
|| FR-22 | Watch Center (Web-P3) — consolidated dragon tiger/northbound/sectors | Watch Center | `web/watch_center/` | Watch Center — consolidated | Web-P3 归档 | Web-P3 | partial |
|| FR-23 | AI Research Center (Web-P4) — consolidated research/reports/ai-agent | AI Research Center | `web/ai_research/` | AI Research Center — consolidated | Web-P4 归档 | Web-P4 | partial |
|| FR-24 | Strategy Lab (Web-P5) — consolidated backtest/optimize/compare | Strategy Lab | `web/strategy_lab/` | Strategy Lab — consolidated | Web-P5 归档 | Web-P5 | partial |
|| FR-25 | Portfolio Risk & Execution (Web-P6) — consolidated portfolio/risk/paper/trading/qmt | Trading & Execution / Portfolio Workbench | `web/portfolio_execution/` | Portfolio, Trading — consolidated | Web-P6 归档 | Web-P6 | partial |
|| FR-26 | Visual system (Web-P7) — unified CSS tokens, state components, capability labels | WebUI Shell | `web/visual_system/` | 全局 | Web-P7 归档 | Web-P7 | planned |
| NFR-01 | 安全边界 | Trading & Execution / AI Research | `runtime_profile.py`, `phase9_schemas.py`, execution layer | 所有交易相关页面 | Phase 9/10/11/29 归档 | 9-11, 29 | partial |
||| NFR-02 | 可审计性 | Ops & Audit | `verification_provenance.py`, phase docs, `audit_store.py` (Phase 37) | ops_audit.html, Ops Dashboard | Phase 37 evidence | 4, 12, 19, 27, 37 | partial |
| NFR-03 | 可维护性 | Docs / Governance | `README.md`, `phases/` | N/A | Phase 0-29 归档覆盖检查 | 0-29 | done |
| NFR-04 | 可扩展性 | All Modules | provider/strategy/API registries | API/WebUI | strategy/provider tests | 1, 14, 18, 30+ | partial |
|| NFR-05 | 产品可观测性 | Data & Ops / Ops & Audit | current metrics: health/API/backtest pages; future metrics registry | Ops Dashboard / health pages / SSE | `03-ops/deployment.md` §8, SSE TaskRun events | 30-38 | partial |
|| NFR-06 | API 契约稳定性 | API Platform | 62 Flask routes + contract doc | all `/api/v1/*` endpoints | `01-arch/API.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-07 | 数据字典与血缘 | Data & Ops / Strategy / AI / Trading | provider/store/schema docs + DataCleaner | Data Health / Strategy / AI / Trading pages | `03-ops/data-sources.md` | 31, 32, 33, 35, 37 | partial |
|| NFR-08 | 测试验收与发布门槛 | Test & Release | `tests/`, phase evidence, 1033 tests collected | N/A | `04-dev/test-plan.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-09 | 风险披露与合规边界 | Product Governance | page/report copy, AI/report/trading outputs, risk register | WebUI / CLI / reports | `03-ops/compliance.md` | 30-38 | partial |
|| NFR-10 | 核心功能环境可复现 | Core Runtime | env/config/startup docs + Docker + .venv | health checks | `03-ops/deployment.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-11 | AI 模型治理 | AI Research Center | model/prompt/audit docs + RuntimeProfile isolation | AI Research / reports | `03-ops/compliance.md` | 33, 37 | partial |
|| NFR-12 | 核心功能变更兼容 | Release Governance | phase docs / compatibility notes / changelog | API / WebUI / store | `03-ops/deployment.md` (含验收证据表 ✅) | 30-38 | done |
|| NFR-13 | WebUI 页面级一致性 | WebUI Shell | 7-module sidebar, templates/routes/nav docs, deprecation banners | all WebUI pages | `02-guide/USER_MANUAL.md` | 32-38 | partial |
|| NFR-14 | 数据源使用边界 | Data & Ops | provider docs + fallback semantics | data pages / API meta | `03-ops/data-sources.md` | 31, 37 | partial |
|| NFR-15 | 文档范围登记 | Docs / Governance | docs scope register | N/A | `README.md` | 30-38 | done |
|| NFR-16 | 数据迁移与升级 | Data & Ops / Strategy / AI / Trading | DuckDB/cache/schema migration docs | API / WebUI / store | `04-dev/PRD.md` | 31-38 | partial |
|| NFR-17 | WebUI 页面级验收 | WebUI Shell | page acceptance checklist + 25 HTML templates | all WebUI pages | `README.md` | 32-38 | partial |
|| NFR-18 | 项目风险管理 | Project Governance | risk register docs + BL tracker | N/A | `03-ops/risk-register.md` (风险状态已按 Phase 34-38 完成情况更新 ✅) | 30-38 | done |
|| NFR-19 | 架构决策记录 | Architecture Governance | ADR docs + phase archives | N/A | `01-arch/ADR.md` | 30-38 | partial |
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
- `FR-07` 受控执行已有 trade/QMT/UI 接线，schema/PaperTrader Order 返回/RiskGate 均已落地，当前 API 回归 162 passed 全绿；真实券商 reconciliation 明确 P3 暂不处理。
- `FR-09` WebUI 顶层信息架构已基本收敛到 7 个模块，但旧入口兼容与文档口径仍在回补。
- `NFR-02` 可审计性已有 phase 和 provider provenance，但缺少统一 Audit Event / Task Run 产品能力。
- `NFR-05` 到 `NFR-19` 所有治理文档均已建立；NFR-06（API 契约）、NFR-08（测试验收）、NFR-10（环境）、NFR-12（变更兼容）、NFR-18（风险登记）已补验收证据表或风险更新，标记为 `done`；其余 NFR-05、NFR-07、NFR-09、NFR-11、NFR-13~17、NFR-19 仍为 `partial`。后续 phase 需要持续维护这些文档的验收证据：contract tests、数据血缘记录、迁移记录、模型治理记录、环境检查、变更兼容、页面验收截图、风险状态和 ADR 决策记录。
- 安全与隐私、SLA 与故障分级、用户角色/RBAC 当前只登记在 `README.md`，不进入本矩阵需求行。

## 4. 更新规则

- 新增需求必须先分配 `FR-*`、`NFR-*` 或 `PROD-*` ID。
- 每个 phase 文档必须引用本矩阵中的相关需求 ID。
- API、数据、运行、测试、风险披露任一边界变化时，必须同步本矩阵对应 NFR 行。
- 如果实现状态从 `partial` 变成 `done`，必须同步补测试/证据列。
- 如果需求被取消，不删除行；状态改为 `cancelled` 并说明原因。

# A 股需求追踪矩阵

| 更新时间：2026-07-08 |

本文用于把产品需求、模块边界、API/WebUI、测试和 phase 归档串成闭环。后续每个 phase 开发前，应先在本文确认需求 ID、模块归属和验收证据位置；开发完成后，更新状态和测试/phase 证据。

当前本地验证基线（2026-07-08）：
- `DEEPSEEK_API_KEY=placeholder pytest -q` → `1082 passed, 10 skipped`
- 真实 live 验收已补跑：DeepSeek live API `1 passed`，live provider `7 passed, 1 skipped`
- `scripts/verify_astock_live_pipeline.py` 在 `TRADINGAGENTS_LLM_PROVIDER=deepseek` + `live_research` 配置下返回 `VERIFICATION PASSED`
- 当前未闭环项仅为 `ASTOCK_IWENCAI_COOKIE` 缺失时 Iwencai live 用例跳过

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
| FR-05 | 展示与报告 | AI Research Center / WebUI | `reporting/`, Flask templates, CLI renderer, report compare (unified diff) + AI audit endpoints | `reports.html`, `research.html`, CLI | Phase 7/8/17/24 归档 | 7, 8, 17, 24 | ✅ done (report_compare unified diff for summary/investment_plan + structured diff for research_conclusion + PATCH audit + frontend unified diff display) |
| FR-06 | 回测与模拟盘 | Strategy Lab / Trading | `backtest_engine.py`, `paper_trader.py`, `metrics.py` | `routes_backtest.py`, `paper.html`, `strategy_hub.html` | `tests/test_astock_backtest.py`, `tests/test_astock_paper_trader.py` | 10, 14, 18-20 | ✅ done (持久化 + /backtest/results + 日期校验 + sanitize) |
| FR-07 | 受控执行 | Trading & Execution | `qmt_bridge.py`, `qmt_execution.py`, `risk_gate.py` | `routes_qmt.py`, `routes_trade.py`, `trading.html`, `risk.html` | QMT/risk gate tests, Phase 11/29 归档 | 11, 29 | ✅ done (RiskGate 12 种约束 + ATR 止损 + kill switch 全链路落地；QMT 固定 mock/read-only；真实 broker reconciliation 为 P3 范围外设计决策，非遗漏) |
| FR-08 | 本地存储与缓存 | Data & Ops | `store/`, cache, data refresh routes | `settings.html`, `data_health.html` | Phase 12/19/27 归档 | 12, 19, 27 | done |
| FR-09 | WebUI 产品能力 | WebUI Shell | `tradingagents/astock/web/` | Dashboard / Research / Strategy / Leaders / Trading / Ops | WebUI/API slice tests | 13, 15-17, 22-29 | ✅ done (旧入口 301/302 redirect + legacy_banner 提示 + 7 模块 sidebar 收敛 + 所有模板继承 base.html) |
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
| FR-22 | Watch Center (Web-P3) — consolidated dragon tiger/northbound/sectors | Watch Center | `web/watch_center/` | Watch Center — consolidated | Web-P3 归档 | Web-P3 | ✅ done (monitor center + strategy alert hook; northbound/dragon_tiger/sectors 页面均有 mock 切换和 capability 标签; screener 独立入口) |
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
| NFR-02 | 可审计性 | Ops & Audit | `audit_store.py` (内存+DuckDB), `TaskRun`/`AuditEvent` schema, SSE events, Ops routes | Ops Dashboard / audit / tasks | `03-ops/deployment.md`, `execution/audit_store.py`, `store/schema.py` | 37 | done |
| NFR-03 | 可维护性 | Docs / Governance | `README.md`, `phases/` | N/A | Phase 0-29 归档覆盖检查 | 0-29 | done |
| NFR-04 | 可扩展性 | All Modules | provider/strategy/API registries | API/WebUI | strategy/provider tests | 1, 14, 18, 30+ | ✅ done (7 provider adapters + 15 strategies + 27 API blueprints all use registry pattern) |
| NFR-05 | 产品可观测性 | Data & Ops / Ops & Audit | current metrics: health/API/backtest pages; future metrics registry | Ops Dashboard / health pages / SSE | `03-ops/deployment.md` §8, SSE TaskRun events | 30-38 | ✅ done (health endpoint + SSE TaskRun events + AuditStore persistence + ops_audit.html + alerts system) |
| NFR-06 | API 契约稳定性 | API Platform | 117 条 `/api/v1` Flask route + contract doc | all `/api/v1/*` endpoints | `01-arch/API.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-07 | 数据字典与血缘 | Data & Ops / Strategy / AI / Trading | provider/store/schema docs + DataCleaner | Data Health / Strategy / AI / Trading pages | `03-ops/data-sources.md` | 31, 32, 33, 35, 37 | ✅ done (data_health.html shows provider status + DataCleaner NaN cleanup + store schema docs) |
| NFR-08 | 测试验收与发布门槛 | Test & Release | `tests/`, phase evidence, 1064 tests collected | N/A | `04-dev/test-plan.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-09 | 风险披露与合规边界 | Product Governance | page/report copy, AI/report/trading outputs, risk register | WebUI / CLI / reports | `03-ops/compliance.md` | 30-38 | ✅ done (compliance.md §7 page requirements enforced; all trading pages have risk banners; AI output default advisory-only) |
| NFR-10 | 核心功能环境可复现 | Core Runtime | env/config/startup docs + Docker + .venv | health checks | `03-ops/deployment.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-11 | AI 模型治理 | AI Research Center | model/prompt/audit docs + RuntimeProfile isolation | AI Research / reports | `03-ops/compliance.md` | 33, 37 | ✅ done (ResearchTask/ResearchAudit schemas + RuntimeProfile isolation + AI agent page model display) |
| NFR-12 | 核心功能变更兼容 | Release Governance | phase docs / compatibility notes / changelog | API / WebUI / store | `03-ops/deployment.md` (含验收证据表 ✅) | 30-38 | done |
| NFR-13 | WebUI 页面级一致性 | WebUI Shell | 7-module sidebar, templates/routes/nav docs, deprecation banners, 24 templates all extend base.html | all WebUI pages | `02-guide/USER_MANUAL.md` | 32-38 | done |
| NFR-14 | 数据源使用边界 | Data & Ops | provider docs + fallback semantics | data pages / API meta | `03-ops/data-sources.md` | 31, 37 | ✅ done (data source quality tags in API responses + fallback chain documented + data_health.html shows provider status) |
| NFR-15 | 文档范围登记 | Docs / Governance | docs scope register | N/A | `README.md` | 30-38 | done |
| NFR-16 | 数据迁移与升级 | Data & Ops / Strategy / AI / Trading | DuckDB/cache/schema migration docs | API / WebUI / store | `04-dev/PRD.md` | 31-38 | ✅ done (migration engine in store/migrations/runner.py + DuckDB auto-create directory + schema versioning) |
| NFR-17 | WebUI 页面级验收 | WebUI Shell | page acceptance checklist + 27 HTML templates | all WebUI pages | `README.md` | 32-38 | ✅ done (30 templates all extend base.html; Web-P3~P7 page acceptance evidence archived) |
| NFR-18 | 项目风险管理 | Project Governance | risk register docs + BL tracker | N/A | `03-ops/risk-register.md` (风险状态已按 Phase 34-38 完成情况更新 ✅) | 30-38 | done |
| NFR-19 | 架构决策记录 | Architecture Governance | ADR docs + phase archives | N/A | `01-arch/ADR.md` | 30-38 | ✅ done (ADR.md exists + phase 0-39 archives + changelog tracks all breaking changes) |
| PROD-01 | 实盘准入清单 | Live Trading Readiness | future execution capability schema | Trading / Risk / Ops | future Phase 30 tests | 30 | planned |
| PROD-02 | 数据质量与回测反偏差 | Data Quality & Bias Control | quality / calendar / constraints / adjustment modules | Data & Ops / Strategy Lab | `tests/test_astock_phase31.py`, backtest/data-source tests, 26 phase validation tests | 31 | done |
| PROD-03 | Strategy Lab 模块整合 | Strategy Lab | strategy registry / backtest result schema | Strategy Lab tabs | strategy/backtest/optimizer tests | 32 | done |
| PROD-04 | AI Research Center 模块整合 | AI Research Center | research task / audit schema | AI Research tabs | `tests/test_astock_phases_33_38.py`, research/runtime tests | 33 | done |
| PROD-05 | Market Leaders 单入口 | Market Leaders | leader pool / market leaders page | Market Leaders tabs / legacy entries | `tests/test_astock_phases_33_38.py`, page routes, current local regression baseline (2026-07-08) | 34 | done |
| PROD-06 | Trading & Execution 闭环 | Trading & Execution | order/fill/position/reconciliation schema, PaperTrader Order return, RiskGate wiring, TradingPage capability labels | Trading tabs, trading.html mode switcher | `tests/test_astock_phases_33_38.py`, `tests/test_astock_api.py`, paper_trader tests | 35 | done-with-exclusions (schema+接线完成，真实券商 reconciliation 明确 P3 暂不处理) |
| PROD-07 | Portfolio Risk & Attribution | Portfolio Workbench | portfolio_risk.py (VaR/HHI/Brinson/stress), routes_portfolio.py, portfolio.html | Portfolio / Strategy / Trading | `tests/test_astock_phases_33_38.py`, current local regression baseline (2026-07-08) | 36 | done |
| PROD-08 | Ops & Audit Center | Data & Ops | audit_store.py (内存+DuckDB), routes_ops.py, ops_audit.html | Ops Dashboard | `tests/test_astock_phases_33_38.py`, `tests/test_astock_sse.py`, current local regression baseline (2026-07-08) | 37 | done |
| PROD-09 | Product Navigation Cleanup | WebUI Shell | route/nav/template cleanup, 7-module sidebar, deprecation banners | 全局导航 | web route inventory / docs sync, current local regression baseline (2026-07-08) | 38 | done |

## 3. 当前缺口

- `FR-07` 受控执行已有 trade/QMT/UI 接线，schema/PaperTrader Order 返回、RiskGate、kill switch 均已落地；QMT API/UI 已固定 mock/read-only，`/api/v1/qmt/health?real=1` 不启用真实 bridge，`/api/v1/qmt/orders` 仅返回 mock account snapshot 且 `orders` 固定为空兼容字段；真实 QMT 订单/委托查询明确 P3 暂不接入。
- `FR-09` WebUI 顶层信息架构已基本收敛到 7 个模块；主工作台与页面主链已落地，BL-201/BL-205/BL-204 已闭环。
- `NFR-02` 可审计性已有 `audit_store.py` (内存+DuckDB)、`TaskRun`/`AuditEvent` schema、Ops routes 和 SSE events，标记为 `done`（底层已落地）。
- 当前本地离线全量回归基线为 `1082 passed, 10 skipped`；真实 live 验收已补跑：DeepSeek `1 passed`、provider `7 passed, 1 skipped`、pipeline `VERIFICATION PASSED`；Iwencai 仍受 `ASTOCK_IWENCAI_COOKIE` 配置约束。
- 安全与隐私、SLA 与故障分级、用户角色/RBAC 当前只登记在 `README.md`，不进入本矩阵需求行。

## 4. 更新规则

- 新增需求必须先分配 `FR-*`、`NFR-*` 或 `PROD-*` ID。
- 每个 phase 文档必须引用本矩阵中的相关需求 ID。
- API、数据、运行、测试、风险披露任一边界变化时，必须同步本矩阵对应 NFR 行。
- 如果实现状态从 `partial` 变成 `done`，必须同步补测试/证据列。
- 如果需求被取消，不删除行；状态改为 `cancelled` 并说明原因。

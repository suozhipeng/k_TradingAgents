# A 股 Hermes 可执行任务包

| 更新时间：2026-06-24 |

本文把 `04-dev/hermes-tasks.md` 中的 5 分钟任务转换为 Hermes 可以直接分派给 DeepSeek 的执行任务包。本文只覆盖核心功能开发，不展开安全与隐私、SLA 与故障分级、用户角色/RBAC。

## 1. Hermes 执行总规则

每次执行一个任务时，Hermes 必须按以下顺序处理：

1. 加载 `tradingagents-core`。
2. 根据任务类型加载专项 skill：provider 任务用 `astock-provider-delivery`，研究链任务用 `astock-analyst-delivery`，phase 编排用 `astock-rollout-orchestrator`。
3. 生成 DeepSeek coding brief。
4. DeepSeek 执行 scoped work。
5. Codex 进行 review gate；如不可用，按 `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` 使用 Hermes fallback review。
6. 只有 review accept 后，才更新 phase 归档、追踪矩阵、风险登记和 ADR。

## 2. 通用任务 Brief 模板

```text
Hermes Task: <TASK_ID> <TASK_TITLE>

Load skills:
- tradingagents-core
- <optional skill>

Goal:
- <one-sentence goal>

Inputs:
- 04-dev/hermes-tasks.md
- 01-arch/API.md
- 04-dev/traceability-matrix.md
- 04-dev/test-plan.md
- <task-specific docs/files>

Allowed scope:
- <files/modules that may be changed>

Out of scope:
- Do not change original TradingAgents core unless explicitly listed.
- Do not add security/privacy, SLA/fault-level, or user role/RBAC work.
- Do not treat QMT as a real-data requirement unless the task explicitly says so.

Implementation steps:
1. <small executable step>
2. <small executable step>
3. <small executable step>

Tests:
- <pytest or docs check command>

Acceptance:
- <observable acceptance criteria>

Return to Hermes:
- Changed files
- Behavior summary
- Tests run and raw result
- Risks / assumptions
- Required doc updates
```

## 3. Phase 30 Live Trading Readiness

Common inputs:

- `03-ops/live-trading.md`
- `01-arch/API.md`
- `03-ops/compliance.md`
- `tradingagents/astock/api/routes_trade.py`
- `tradingagents/astock/api/routes_paper.py`
- `tradingagents/astock/api/routes_qmt.py`
- `tradingagents/astock/execution/risk_gate.py`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 30-01 | 搜索所有 `/trade`, `/paper`, `/qmt` API 返回字段，形成字段清单。 | docs only preferred; API files read-only unless fixing obvious label drift | `git diff --check -- docs` | 字段清单写入 phase 草稿或 runbook，不遗漏 trade/paper/qmt endpoints |
| 30-02 | 为每个交易 API 标注 capability：research/paper/managed/live-ready/mock。 | `01-arch/API.md`, phase doc; API meta only if explicitly approved | `tests/test_astock_api.py -q` if code changes | 所有交易 API 有 capability，不把 paper/mock 描述为 real |
| 30-03 | 梳理 `trade_state` 当前 paper 语义，更新文档和页面验收要求。 | `03-ops/live-trading.md`, `README.md` | docs check | trade_state 明确为 Paper Trading，不代表真实账户 |
| 30-04 | 定义 `TradingMode` enum 文档 schema。 | `01-arch/API.md`, `03-ops/live-trading.md` | docs check | enum 包含 research/paper/managed/live-ready |
| 30-05 | 定义 `ExecutionCapability` schema。 | API contracts, runbook | docs check | schema 可被交易 API 和页面复用 |
| 30-06 | 绘制订单生命周期 Mermaid 状态机。 | runbook, phase doc | docs check | 覆盖 created/submitted/confirmed/partial_filled/filled/cancelled/rejected/expired/error |
| 30-07 | 梳理风控 reason code。 | runbook, risk disclosure, future phase doc | `tests/test_astock_execution_risk_gate.py -q` if code changes | Risk Gate reason code 可用于 API 和页面 |
| 30-08 | 定义 kill switch 文档行为。 | runbook, risk disclosure | docs check | kill switch 激活后默认阻断后续执行 |
| 30-09 | 更新交易页页面验收清单。 | `README.md` | docs check | paper/managed/live-ready disabled 标签截图要求明确 |
| 30-10 | 运行 paper trader 验收并记录结果。 | phase doc only unless fixing tests | `tests/test_astock_paper_trader.py -q` | 测试结果写入 phase 证据；失败需记录原因 |

## 4. Phase 31 Data Quality & Bias Control

Common inputs:

- `03-ops/data-sources.md`
- `04-dev/PRD.md`
- `03-ops/data-sources.md`
- `tradingagents/astock/data_sources/router.py`
- `tradingagents/astock/data_sources/adapters.py`
- `tradingagents/astock/api/routes_data.py`
- `tradingagents/astock/api/routes_tv.py`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 31-01 | 列出 K 线 API 当前字段。 | docs first; `routes_data.py` only if adding meta fields is approved | `tests/test_astock_api.py -q` if code changes | 字段表包含 source/generated_at/freshness/quality 规划 |
| 31-02 | 定义 `DataQualityTag` schema。 | data dictionary, API contracts | docs check | normal/stale/partial/fallback/mock/degraded 定义清楚 |
| 31-03 | 定义 `BacktestDataAssumption` schema。 | data dictionary, Strategy Lab docs | docs check | 复权、成本、滑点、成交约束、样本外字段明确 |
| 31-04 | 梳理交易日历数据来源。 | data source usage doc | docs check | 标出 akshare/mootdx 可用性与 fallback |
| 31-05 | 梳理停复牌字段来源。 | data dictionary/source usage | docs check | 无稳定来源时标 planned，不伪造成 done |
| 31-06 | 梳理涨跌停成交约束。 | data dictionary/test plan | docs check | 回测不可成交条件明确 |
| 31-07 | 登记 survivorship bias 风险。 | risk register | docs check | 新增或更新相关 R-* 风险 |
| 31-08 | 为回测结果补 data_assumption 文档字段。 | data dictionary, API contracts | docs check | BacktestResult 可表达数据假设 |
| 31-09 | 更新 Data & Ops 页面验收点。 | WebUI checklist | docs check | data_health/settings 需要展示 freshness/quality/fallback |
| 31-10 | 运行数据源测试并记录。 | phase doc | `tests/test_astock_data_sources.py -q` | 结果写入 phase 证据；live skip guard 明确 |

## 5. Phase 32 Strategy Lab

Common inputs:

- `02-guide/strategy-dev.md`
- `01-arch/API.md`
- `tradingagents/astock/execution/`
- `tradingagents/astock/api/routes_backtest.py`
- `tradingagents/astock/api/routes_market.py`
- `tradingagents/astock/web/templates/strategy_hub.html`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 32-01 | 搜索所有策略注册点。 | docs; source read-only | docs check | `execution/__init__.py`, `_STRATEGY_REGISTRY`, `AVAILABLE_STRATEGIES` 均列出 |
| 32-02 | 定义 Strategy Registry schema。 | strategy guide, API contracts | docs check | name/category/params/search_space/suitability 完整 |
| 32-03 | 定义 Backtest Result schema。 | data dictionary, API contracts | docs check | metrics/equity/trades/assumption/benchmark 完整 |
| 32-04 | 定义 Optimize Result schema。 | API contracts, strategy guide | docs check | score/top_n/in_sample/out_sample/walk_forward 字段明确 |
| 32-05 | 梳理 Strategy Hub 当前 tab。 | WebUI checklist | docs check | 当前入口和目标入口不遗漏 |
| 32-06 | 标记旧策略入口迁移策略。 | WebUI product spec/checklist | docs check | 旧入口有 keep/redirect/deprecate 结论 |
| 32-07 | 更新 Strategy Lab 效果图。 | development progress doc or WebUI spec | docs check | tab 和核心区域清晰 |
| 32-08 | 如 registry 决策变化，更新 ADR。 | ADR | docs check | 新 ADR 或引用 ADR-004 |
| 32-09 | 运行策略测试。 | phase doc | `tests/test_astock_strategies.py -q` | passed 或失败原因明确 |
| 32-10 | 运行优化器测试。 | phase doc | `tests/test_astock_optimizer.py -q` | passed 或失败原因明确 |

## 6. Phase 33 AI Research Center

Common inputs:

- `03-ops/compliance.md`
- `03-ops/compliance.md`
- `tradingagents/astock/runtime.py`
- `tradingagents/astock/api/routes_ai_agent.py`
- `tradingagents/astock/api/routes_reports.py`
- `tradingagents/astock/web/templates/research.html`
- `tradingagents/astock/web/templates/ai_agent.html`
- `tradingagents/astock/web/templates/reports.html`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 33-01 | 搜索 AI/report/research 入口。 | docs; source read-only | docs check | research/ai_agent/reports/runtime 覆盖 |
| 33-02 | 定义 ResearchTask schema。 | model governance, API contracts | docs check | task_id/symbol/mode/status/snapshot 字段明确 |
| 33-03 | 定义 ResearchAudit schema。 | model governance, data dictionary | docs check | model/prompt/snapshot/citation/generated_at 完整 |
| 33-04 | 定义 advisory-only 输出要求。 | risk disclosure, model governance | docs check | AI 输出不得触发真实订单 |
| 33-05 | 梳理 LLM 不可用降级。 | model governance, test plan | docs check | fail closed/degraded 行为明确 |
| 33-06 | 梳理报告归档字段。 | data dictionary, release/change doc | docs check | markdown/json/ppt/web report 字段清晰 |
| 33-07 | 更新 AI Research 效果图。 | development progress doc / WebUI spec | docs check | 审计区和报告档案区明确 |
| 33-08 | 更新模型治理文档。 | model governance | docs check | prompt version 和 provider 记录明确 |
| 33-09 | 运行 research runtime 测试。 | phase doc | `tests/test_astock_graph_runtime.py -q` | passed 或失败原因明确 |
| 33-10 | 运行 PPT 测试。 | phase doc | `tests/test_astock_ppt.py -q` | passed 或失败原因明确 |

## 7. Phase 34 Market Leaders

Common inputs:

- `tradingagents/astock/api/routes_market_data.py`
- `tradingagents/astock/execution/momentum_rotation.py`
- `tradingagents/astock/web/templates/momentum_dashboard.html`
- `tradingagents/astock/web/templates/momentum_rotation.html`
- `tradingagents/astock/web/templates/dragon_tiger.html`
- `tradingagents/astock/web/templates/northbound.html`
- `tradingagents/astock/web/templates/sectors.html`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 34-01 | 列出现有龙头/板块/资金页面。 | docs; template read-only | docs check | momentum/rotation/dragon/northbound/sectors 覆盖 |
| 34-02 | 定义 Market Leaders 顶层入口。 | WebUI spec, ADR | docs check | 顶层最多一个入口 |
| 34-03 | 定义 LeaderPool schema。 | data dictionary, API contracts | docs check | source/reason/score/refreshed_at 完整 |
| 34-04 | 梳理 EastMoney/Sina/mock fallback。 | data source usage, risk register | docs check | mock 必须显著标注 |
| 34-05 | 定义候选池入池理由字段。 | data dictionary, WebUI checklist | docs check | 可解释、可追溯 |
| 34-06 | 定义候选池出池理由字段。 | data dictionary, WebUI checklist | docs check | 可解释、可追溯 |
| 34-07 | 更新 Market Leaders 效果图。 | development progress doc / WebUI spec | docs check | tab 和候选池区域清晰 |
| 34-08 | 更新页面级验收清单。 | WebUI checklist | docs check | success/empty/error/degraded 证据要求明确 |
| 34-09 | 运行 WebUI 测试。 | phase doc | `tests/test_astock_web.py -q` | passed 或失败原因明确 |
| 34-10 | 运行 API 测试。 | phase doc | `tests/test_astock_api.py -q` | passed 或失败原因明确 |

## 8. Phase 35 Trading & Execution

Common inputs:

- `03-ops/live-trading.md`
- `tradingagents/astock/api/routes_trade.py`
- `tradingagents/astock/api/routes_paper.py`
- `tradingagents/astock/execution/paper_trader.py`
- `tradingagents/astock/execution/risk_gate.py`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 35-01 | 定义 Order schema。 | API contracts, runbook | docs check | 状态完整，兼容 paper/managed |
| 35-02 | 定义 Fill schema。 | API contracts, runbook | docs check | 支持部分成交 |
| 35-03 | 定义 Position schema。 | API contracts, data dictionary | docs check | paper/managed 可共用 |
| 35-04 | 定义 Reconciliation schema。 | runbook, API contracts | docs check | 本地状态 vs 外部回报可表达 |
| 35-05 | 梳理 trade/order 当前行为。 | runbook, risk disclosure | docs check | 不误标 live-ready |
| 35-06 | 梳理 risk gate 前置条件。 | runbook, test plan | `tests/test_astock_execution_risk_gate.py -q` if changed | 下单前阻断条件明确 |
| 35-07 | 更新 Trading 效果图。 | development progress doc / WebUI spec | docs check | capability visible |
| 35-08 | 更新 runbook checklist。 | runbook | docs check | live-ready 前置条件完整 |
| 35-09 | 运行 paper/risk 测试。 | phase doc | `tests/test_astock_paper_trader.py -q`, `tests/test_astock_execution_risk_gate.py -q` | passed 或失败原因明确 |
| 35-10 | 记录 QMT 真实数据范围排除。 | document scope/register/runbook | docs check | QMT 不纳入真实数据源要求 |

## 9. Phase 36 Portfolio Risk & Attribution

Common inputs:

- `BACKLOG.md`
- `01-arch/API.md`
- `tradingagents/astock/execution/metrics.py`
- `tradingagents/astock/api/routes_dashboard.py`
- `tradingagents/astock/web/templates/dashboard.html`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 36-01 | 定义 Portfolio schema。 | API contracts, data dictionary | docs check | holdings/cash/nav 字段明确 |
| 36-02 | 定义 RiskExposure schema。 | API contracts, data dictionary | docs check | industry/concentration/beta/liquidity 字段明确 |
| 36-03 | 定义 Attribution schema。 | API contracts, data dictionary | docs check | benchmark/selection/timing/cost/slippage 明确 |
| 36-04 | 梳理回测结果复用字段。 | data dictionary | docs check | 可接 Strategy Lab |
| 36-05 | 梳理 paper 状态复用字段。 | data dictionary | docs check | 可接 Trading |
| 36-06 | 画 Portfolio Workbench 效果图。 | development progress doc / WebUI spec | docs check | 风险+归因页面结构明确 |
| 36-07 | 定义页面输入输出。 | WebUI checklist | docs check | 输入/输出明确 |
| 36-08 | 定义压力测试指标。 | metrics/Ops, API contracts | docs check | VaR/DD/stress 字段明确 |
| 36-09 | 补测试计划。 | test plan | docs check | 单元+API slice 覆盖面明确 |
| 36-10 | 更新追踪矩阵状态。 | traceability matrix | docs check | PROD-07 有证据路径 |

## 10. Phase 37 Ops & Audit

Common inputs:

- `03-ops/ops-metrics.md`
- `tradingagents/astock/api/routes_sse.py`
- `tradingagents/astock/execution/event_bus.py`
- `tradingagents/astock/api/routes_dashboard.py`
- `tradingagents/astock/api/routes_data_health.py`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 37-01 | 定义 TaskRun schema。 | API contracts, metrics/Ops | docs check | type/status/start/end/error 字段明确 |
| 37-02 | 定义 AuditEvent schema。 | API contracts, data dictionary | docs check | actor/input/output/snapshot/model/confirmation 明确 |
| 37-03 | 梳理 SSE event 当前字段。 | metrics/Ops, release/change | docs check | 可迁移到 TaskRun |
| 37-04 | 梳理 data refresh 任务。 | metrics/Ops | docs check | 可追踪 |
| 37-05 | 梳理 backtest 任务。 | metrics/Ops | docs check | 可追踪 |
| 37-06 | 梳理 AI research 任务。 | metrics/Ops, model governance | docs check | 可追踪 |
| 37-07 | 画 Ops Dashboard 效果图。 | development progress doc / WebUI spec | docs check | 任务/错误/健康三区明确 |
| 37-08 | 更新 metrics/Ops 文档。 | metrics/Ops | docs check | 指标可验收 |
| 37-09 | 运行 SSE 测试。 | phase doc | `tests/test_astock_sse.py -q` | passed 或失败原因明确 |
| 37-10 | 更新风险登记表。 | risk register | docs check | R-009/R-005 状态更新 |

## 11. Phase 38 Product Navigation Cleanup

Common inputs:

- `02-guide/USER_MANUAL.md`
- `README.md`
- `tradingagents/astock/web/templates/`
- `tradingagents/astock/web/__init__.py`

| Task ID | Hermes brief | Allowed scope | Tests | Acceptance |
|---|---|---|---|---|
| 38-01 | 列出所有 template 页面。 | docs; templates read-only unless implementation phase | docs check | 25 HTML 模板（23 页面模板 + 2 基础模板）覆盖 |
| 38-02 | 列出 sidebar/nav 入口。 | docs; base templates read-only unless approved | docs check | 无重复入口清单 |
| 38-03 | 定义目标顶层导航。 | WebUI spec, ADR | docs check | 7 个顶层模块 |
| 38-04 | 标记旧入口迁移策略。 | WebUI checklist, release/change | docs check | redirect/hidden/legacy 明确 |
| 38-05 | 更新 WebUI 产品规范。 | WebUI spec | docs check | 页面状态一致 |
| 38-06 | 更新页面级验收清单。 | WebUI checklist | docs check | 每页输入输出明确 |
| 38-07 | 画最终导航图。 | development progress doc / WebUI spec | docs check | Mermaid 可渲染 |
| 38-08 | 运行 WebUI/API slice。 | phase doc | `tests/test_astock_web.py -q`, `tests/test_astock_api.py -q` | passed 或失败原因明确 |
| 38-09 | 如导航决策变化，更新 ADR。 | ADR | docs check | accepted/superseded 状态正确 |
| 38-10 | 更新当前状态文档。 | current status, phase doc | docs check | Phase 38 证据闭合 |

## 12. Hermes 回填要求

每个 task 完成后，Hermes 必须回填：

- `docs/phases/phase-XX-*.md`：scope、修改文件、测试结果、风险、下一入口条件。
- `04-dev/traceability-matrix.md`：需求状态和证据列。
- `01-arch/API.md`：如新增、删除或调整 endpoint、数据源、能力等级或测试验收。
- `03-ops/risk-register.md`：相关风险状态。
- `01-arch/ADR.md`：如有重大决策变化。
- `phases/README.md`：只有 phase 完成且 review accept 后更新。

## 13. Hermes 禁止事项

- 不得在未 review accept 前标记 phase complete。
- 不得把 mock/fallback/cache 描述成真实实时数据。
- 不得把 paper/managed 描述成完整实盘。
- 不得绕过 `tradingagents-core` 修改策略、回测或原 TradingAgents core 边界。
- 不得隐式引入安全与隐私、SLA 与故障分级、用户角色/RBAC。

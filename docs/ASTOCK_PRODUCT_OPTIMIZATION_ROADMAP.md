# A 股专业金融产品优化路线图

| 更新时间：2026-06-23 |

本文从资深金融软件产品经理和金融从业人员视角，梳理 TradingAgents-Astock 当前仍需优化的模块，并给出可直接进入后续 phase 开发的任务边界。本文不替代 `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`，而是把其中的边界转换为产品化开发路线。

## 1. 产品定位判断

当前项目已经具备：

- A 股多源数据接入和 fallback。
- AI 研究链路和 advisory chain。
- 策略、回测、优化、绩效、对比和模拟盘能力。
- 龙头、板块、资金、筛选器和专业交易页雏形。
- QMT 受控执行和 paper trading 路径。

但从专业金融平台口径看，当前系统仍应定位为：

```text
投研分析 + 策略验证 + 模拟盘 + 受控执行试运行平台
```

不应定位为：

```text
完整自动实盘生产交易系统
```

主要原因是仍缺少账户/订单/成交 reconciliation、强风控、数据质量分级、回测反偏差、组合级风险和全链路审计。

## 2. 优先级总览

| 优先级 | 模块 | 产品目标 | 推荐 phase |
|---|---|---|---|
| P0 | Live Trading Readiness | 明确实盘准入，不把 paper/managed 误标成 live-ready | Phase 30 |
| P0 | Data Quality & Bias Control | 补齐交易日历、复权、停牌、涨跌停、ST/退市、反偏差 | Phase 31 |
| P1 | Strategy Lab | 把策略、回测、优化、绩效、对比、动量轮动收敛为统一工作台 | Phase 32 |
| P1 | AI Research Center | 把 AI Agent、研究页、报告中心、审计模型整合为一个 AI 投研模块 | Phase 33 |
| P1 | Market Leaders | 龙头、板块、资金、候选池、轮动回测最多保留一个顶层入口 | Phase 34 |
| P1 | Trading & Execution | 账户、订单、成交、撤单、拒单、部分成交、风控确认闭环 | Phase 35 |
| P2 | Portfolio Risk & Attribution | 从单股/单策略升级为组合级风险和绩效归因 | Phase 36 |
| P2 | Ops & Audit | 任务、错误、provider、模型、数据快照、人工确认统一审计 | Phase 37 |
| P2 | Product Navigation Cleanup | 清理重复入口、统一模式标签、沉淀专业金融终端体验 | Phase 38 |

建议先做 P0。否则后续继续堆页面和策略，会扩大“看起来像实盘、实际不是实盘”的产品风险。

## 3. P0-1 Live Trading Readiness

### 当前问题

- `trading.html` 已具备专业交易页观感，但账户、委托、成交和券商回报仍未形成生产级闭环。
- QMT bridge、paper trader、trade API 的能力边界容易被用户误解。
- 风控更多是模块能力，尚未形成实盘准入 checklist。

### 必须优化

- 建立统一交易模式：`research`、`paper`、`managed`、`live-ready`。
- 建立账户状态模型：资金、可用资金、冻结资金、持仓、市值、盈亏、风险暴露。
- 建立订单生命周期：创建、提交、确认、部分成交、全部成交、撤单、拒单、过期、异常。
- 建立硬风控：kill switch、最大单笔金额、最大持仓、最大日亏损、交易时段、手工确认。
- 建立 reconciliation：本地订单状态与券商回报差异检测。
- 建立审计：下单前数据快照、AI 建议、人工确认、订单回报、风控结果。

### 开发产物

- `docs/phases/phase-30-live-trading-readiness.md`
- `TradingMode` / `ExecutionCapability` 文档 schema
- 订单生命周期 Mermaid 状态机
- API 能力矩阵：research / paper / managed / live-ready
- WebUI 模式标签规范

### 验收标准

- 用户不会把 paper trading 误认为真实实盘。
- 每个交易相关 API 都能标注能力等级。
- 任何 live-ready 声明都有 checklist 证据。
- kill switch 和人工确认在文档层成为强制门槛。

## 4. P0-2 Data Quality & Bias Control

### 当前问题

- 数据源丰富，但数据质量、时效、缺失、fallback、复权、停牌和涨跌停约束尚未成为统一产品能力。
- 回测可运行，但专业投资视角下仍需显式防 survivorship bias、look-ahead bias 和未来函数。
- live provider provenance 已存在，但还未升级成可视化数据质量系统。

### 必须优化

- 交易日历：交易日、节假日、半日市、非交易时段。
- 证券状态：停复牌、ST、退市、上市日期、新股、涨跌停。
- 价格口径：前复权、后复权、不复权、除权除息。
- 数据质量：空值率、延迟、来源、fallback 轨迹、最后更新时间。
- 回测约束：涨跌停不可成交、停牌不可成交、T+1、成交量容量、滑点。
- 反偏差：样本外、walk-forward、survivorship bias、look-ahead bias、未来函数检查。

### 开发产物

- `docs/phases/phase-31-data-quality-bias-control.md`
- `DataQualityTag` 文档 schema
- `BacktestDataAssumption` 文档 schema
- provider health / provenance / freshness UI 设计
- 回测结果必须显示数据假设和反偏差状态

### 验收标准

- 每个回测结果显示数据区间、复权方式、成本模型、成交约束和是否样本外。
- 每个行情/财务/公告/新闻/研报数据块显示来源、更新时间和质量等级。
- 回测文档明确禁止未来函数和 look-ahead bias。

## 5. P1-1 Strategy Lab

### 当前问题

- 策略、回测、优化、绩效、对比、动量轮动已经存在，但产品心智和工程入口仍分散。
- 策略注册点分散，容易新增策略后漏掉 API 或 WebUI 展示。
- 动量轮动既像策略，又像龙头决策产品，需要明确归属或双入口策略。

### 必须优化

- 建立统一 Strategy Registry：名称、分类、参数 schema、搜索空间、适用市场、适用行情。
- 建立统一 Backtest Result：指标、净值曲线、交易明细、数据假设、benchmark、成本模型。
- 建立统一优化器结果：参数、score、样本内/样本外、walk-forward。
- 将 Backtest / Optimize / Compare / Performance / Momentum Rotation 收敛到 Strategy Lab。
- 保持动量轮动 Standalone 组合策略模式，不强行改成单标的 `StrategyBase`。

### 开发产物

- `docs/phases/phase-32-strategy-lab-consolidation.md`
- Strategy Registry schema
- Backtest Result schema
- Strategy Lab 页面 tab 设计
- 旧入口迁移表

### 验收标准

- 新增策略只需注册一次即可被 API、WebUI、优化器识别。
- 回测结果可被策略对比、绩效归因、AI Research 复用。
- 所有策略开发遵守 `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`。

## 6. P1-2 AI Research Center

### 当前问题

- AI Agent 页面、research 页面、reports 页面和 AStock runtime 均存在，但不是一个完整 AI 投研中心。
- AI 输出缺少统一 prompt、模型、数据快照、引用来源和人工确认审计。
- AI 结论和策略结果、持仓风险之间尚未形成可追溯联动。

### 必须优化

- 统一 AI Research Task：单股、多股、主题、行业、持仓组合。
- 统一上下文包：行情、财务、公告、新闻、研报、龙虎榜、北向、板块、策略结果、持仓风险。
- 统一 AI audit：模型、prompt、输入数据版本、引用来源、生成时间、人工确认状态。
- 统一报告归档：Markdown、JSON、PPT、Web report。
- 保留原 TradingAgents 底层 AI agent 能力，不重写 core。

### 开发产物

- `docs/phases/phase-33-ai-research-center.md`
- `ResearchTask` 文档 schema
- `ResearchAudit` 文档 schema
- AI Research Center WebUI 设计
- 报告归档与复查流程

### 验收标准

- 每个 AI 结论都能追溯输入数据、模型和 prompt。
- AI 结论默认 advisory，不直接触发真实订单。
- 报告中心不只是下载页，而是可检索、可复查、可对比的投研档案。

## 7. P1-3 Market Leaders

### 当前问题

- 龙头动量、动量轮动、龙虎榜、北向资金、板块页面分散。
- 用户会把龙头、资金、板块、轮动策略理解成多个产品线。
- 候选池的来源、入池/出池理由和刷新机制还需要更专业化。

### 必须优化

- 顶层最多保留一个 `Market Leaders` / `龙头决策` 入口。
- 内部使用顶部 tab：动量总览、候选池、板块强弱、资金线索、轮动回测。
- 候选池必须显示来源、更新时间、入池理由、出池理由、评分变化。
- 龙虎榜、北向、板块不再作为平级主产品入口，而是资金线索/板块强弱子功能。

### 开发产物

- `docs/phases/phase-34-market-leaders-entry.md`
- Market Leaders tab 设计
- Leader Pool schema
- 旧入口兼容跳转表

### 验收标准

- 顶层导航只有一个龙头相关入口。
- 用户可以从候选池一路进入评分、资金线索、轮动回测。
- 每个候选股有可解释的入池/出池理由。

## 8. P1-4 Trading & Execution

### 当前问题

- 专业交易页已经具备界面，但订单和账户仍需生产级状态模型。
- 风控页面与交易页需要从“展示型风控”升级为“执行前置门”。
- QMT、paper、research 三类路径需要统一模式和视觉区分。

### 必须优化

- Trading 首页显示当前模式、账户状态、风控状态、kill switch、最近订单。
- Paper、Managed QMT、Live-ready 分 tab，但共享订单状态 schema。
- Risk Gate 作为执行前置门，不只是 dashboard。
- 所有下单动作必须有人工确认、风控解释和审计记录。

### 开发产物

- `docs/phases/phase-35-trading-execution-control.md`
- Order / Fill / Position 文档 schema
- Trading WebUI 信息架构
- QMT 能力边界修正文档

### 验收标准

- paper、managed、live-ready 视觉和文案完全区分。
- API 不再出现 mock 订单被误认为真实订单的情况。
- 风控拦截有清晰 reason code。

## 9. P2-1 Portfolio Risk & Attribution

### 当前问题

- 当前能力更偏单股、单策略、单页面分析。
- 专业投资场景需要组合级风险、暴露、容量和归因。

### 必须优化

- 行业暴露、个股集中度、相关性、Beta、流动性、容量。
- VaR、压力测试、最大回撤分解、换手、交易成本贡献。
- benchmark、超额收益、选股贡献、择时贡献。
- 与 Strategy Lab 和 Trading 共享组合状态。

### 开发产物

- `docs/phases/phase-36-portfolio-risk-attribution.md`
- Portfolio Risk schema
- Attribution Report schema
- Portfolio Workbench 页面设计

### 验收标准

- 回测和模拟盘都能看到组合级风险。
- 策略收益能拆分为 benchmark、选股、择时、成本、滑点贡献。

## 10. P2-2 Ops & Audit

### 当前问题

- 已有 data health、provider provenance、SSE 和缓存能力，但还不是统一运维审计中心。
- 任务失败、数据刷新、AI 生成、回测、下单确认还缺统一审计线索。

### 必须优化

- 统一任务中心：数据刷新、回测、AI 分析、报告生成、交易动作。
- 统一审计日志：用户、时间、输入、输出、模型、数据、人工确认。
- 统一错误中心：provider 错误、API 错误、任务失败、风控拒绝。
- 统一健康页：provider、DuckDB、缓存、LLM、QMT、WebUI。

### 开发产物

- `docs/phases/phase-37-ops-audit-center.md`
- Audit Event schema
- Task Run schema
- Ops Dashboard 设计

### 验收标准

- 每个关键动作可追溯。
- 每个失败有错误类型、影响范围和建议处理动作。
- 运维页面能回答“现在系统能不能安全用于研究/模拟/受控执行”。

## 11. 推荐开发顺序

建议按以下顺序推进：

1. `Phase 30`：Live Trading Readiness。先定安全和能力口径。
2. `Phase 31`：Data Quality & Bias Control。再定数据可信和回测可信。
3. `Phase 32`：Strategy Lab。收敛策略与回测产品线。
4. `Phase 33`：AI Research Center。收敛 AI 投研与报告审计。
5. `Phase 34`：Market Leaders。收敛龙头和资金线索入口。
6. `Phase 35`：Trading & Execution。补订单、成交、风控执行闭环。
7. `Phase 36`：Portfolio Risk & Attribution。升级到组合级专业能力。
8. `Phase 37`：Ops & Audit。统一运行、错误、审计和健康状态。
9. `Phase 38`：Product Navigation Cleanup。最后清 UI 入口和体验一致性。

## 11.1 Phase 依赖关系

每个 Phase 执行前必须确认前置依赖已完成：

| Phase | 依赖前置 Phase | 依赖内容 |
|---|---|---|
| 31 | 30 | TradingMode enum、capability 标注规范 |
| 32 | 31 | BacktestDataAssumption schema、DataQualityTag |
| 33 | 31 | data_assumption 字段、DataQualityTag |
| 33 | 32 | BacktestResult schema（AI 可复用回测结果） |
| 34 | 31 | DataQualityTag（候选池数据来源标注） |
| 35 | 30 | TradingMode enum、capability 标注、kill switch 定义 |
| 35 | 34 | LeaderPool schema（龙头交易上下文） |
| 36 | 32 | BacktestResult schema、Strategy Registry |
| 36 | 35 | Order/Position/Fill schema、reconciliation |
| 37 | 30-36 | 所有前述 Phase 的 schema 和 API（TaskRun/AuditEvent 覆盖全部模块） |
| 38 | 32-37 | 所有模块页面收敛、导航整合、旧入口迁移 |

下一 phase 开始前必须在上一个 phase 的 phase 文档中标记依赖满足。

## 12. Phase 39 端到端 UAT

Phase 30-38 每个 phase 的任务均为模块级文档/schema/测试任务，缺少跨模块的端到端用户工作流验收。Phase 38 完成后必须执行以下 UAT 场景：

| UAT 场景 | 步骤 | 通过标准 | 涉及 Phase |
|---|---|---|---|
| 完整研究链路 | 输入 symbol → AI Research → 生成报告 → 报告含数据来源/模型/时间/advisory 标记 | 报告可追溯，advisory-only 标记存在 | 30, 33, 37 |
| 研究→回测→模拟盘 | 研究报告 → 选择策略 → 回测 → 模拟盘试跑 | 回测含数据假设，模拟盘明确 paper 标签 | 30, 31, 32, 35 |
| 策略→交易 | 策略回测 → 优化 → 模拟盘下单 → 风控门 → 人工确认 | 风控拦截有 reason code，人工确认记录存在 | 30, 32, 35 |
| 龙头→候选池→交易 | Market Leaders 候选池 → 查看入池理由 → 进入交易页 | 候选股有可解释理由，交易页显示 capability 标签 | 30, 34, 35 |
| 数据→AI→报告归档 | 数据刷新 → AI Research → 报告归档 → 报告复查 | 数据 freshness/quality 可查，报告可检索复查 | 31, 33, 37 |
| Ops 审计追溯 | 任意操作 → Ops Dashboard 查询 TaskRun/AuditEvent | 每个关键动作有 audit 引用，失败有错误原因 | 37 |

Phase 39 UAT 任务：

| ID | 任务 | 产物 | 验收 |
|---|---|---|---|
| 39-01 | 编写端到端 UAT 场景表 | UAT 场景表 | 覆盖上述 6 个场景 |
| 39-02 | 为每个场景编写执行步骤 | 步骤清单 | 每步可复现 |
| 39-03 | 执行 UAT 场景 1-3 | 执行结果 | 通过/失败记录 |
| 39-04 | 执行 UAT 场景 4-6 | 执行结果 | 通过/失败记录 |
| 39-05 | 更新当前状态文档 | ASTOCK_CURRENT_STATUS.md | 记录 UAT 结果 |

测试命令：
```bash
# 结合各 phase 的测试命令 + 手工端到端验证
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q
pytest tests/test_astock_graph_runtime.py -q
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_paper_trader.py -q
```

完成标准：
- 所有 6 个 UAT 场景至少执行一次并记录结果
- 失败场景必须有 root cause 分析和修复计划
- UAT 结果写入 ASTOCK_CURRENT_STATUS.md

## 13. 直接开发前检查清单

每个新 phase 开始前必须先回答：

- 本 phase 是 `research`、`paper`、`managed` 还是 `live-ready`？
- 是否触及原 TradingAgents core？如果触及，是否只是兼容性修复？
- 是否新增或修改 API schema？
- 是否新增或修改 store schema？
- 是否影响 DuckDB、cache、schema、报告归档或回测结果结构？
- 是否新增或修改数据源、AI provider、prompt 或模型输出 schema？
- 是否影响 WebUI 顶层导航？
- 是否有旧入口迁移策略？
- 是否需要数据快照、模型审计或订单审计？
- 是否影响核心功能启动、依赖、健康检查或 degraded 状态？
- 是否有明确测试命令？
- 是否有回滚方案？
- 是否新增或改变项目级风险状态？
- 是否涉及需要 ADR 记录的架构或产品边界决策？
- 是否触及当前暂不纳入范围：安全与隐私、SLA 与故障分级、用户角色/RBAC？

如果以上问题没有答案，不应开始代码开发。

## 13.1 生产级文档门槛

后续 Phase 30-38 不只交付功能，还必须同步生产级文档：

- API 变化：更新 `docs/ASTOCK_API_CONTRACTS.md`，包括 capability、envelope、错误码和 schema。
- 数据变化：更新 `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`，包括字段、来源、质量、快照和 fallback。
- 数据迁移变化：更新 `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`，包括 DuckDB/cache/schema 迁移、校验和回滚。
- 数据源变化：更新 `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`，包括来源、用途和使用边界。
- AI 变化：更新 `docs/ASTOCK_MODEL_GOVERNANCE.md`，包括 provider、prompt、模型输出和降级。
- 实盘/受控执行变化：更新 `docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`，包括开盘前检查、盘中处理、故障降级和回滚。
- 核心功能运行变化：更新 `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`，包括依赖、启动和健康检查。
- 测试变化：更新 `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`，包括测试命令、验收门槛和发布阻断项。
- 变更兼容变化：更新 `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`，包括需求 ID、schema、测试和回滚。
- 风险披露变化：更新 `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`，确保 AI、回测、模拟盘和交易入口不产生实盘误导。
- WebUI 变化：更新 `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`，包括页面状态、能力标签和旧入口迁移。
- WebUI 页面验收：更新 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`，包括输入、输出、状态、错误态和截图证据。
- 项目风险变化：更新 `docs/ASTOCK_PROJECT_RISK_REGISTER.md`，包括影响、概率、缓解措施和状态。
- 架构决策变化：更新 `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`，包括背景、决策、影响和关联文档。
- 暂不纳入模块变化：先更新 `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`，未明确重新纳入前不得进入核心功能开发。

## 14. 关联文档

- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
- `docs/ASTOCK_PROJECT_RISK_REGISTER.md`
- `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`
- `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`
- `docs/ASTOCK_API_CONTRACTS.md`
- `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`
- `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`
- `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`
- `docs/ASTOCK_MODEL_GOVERNANCE.md`
- `docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`
- `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`
- `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`
- `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`
- `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`
- `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`
- `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`
- `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

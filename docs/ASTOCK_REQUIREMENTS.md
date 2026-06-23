# TradingAgents-Astock 需求文档

## 1. 文档定位

本文档整理当前仓库的 A 股二次开发需求，统一以下三类信息：

- 产品目标与范围
- 功能/模块需求
- 当前实现边界与未闭环项

使用规则：

- 需求目标以本文档和 `planning/codebase/ASTOCK_RESOURCE_PLAN.md` 为准
- 当前实现事实以 `docs/ASTOCK_CURRENT_STATUS.md` 为准
- 每个阶段的实现证据以 `docs/phases/` 为准

配套拆分文档：

- `docs/ASTOCK_PRD.md`：产品需求 PRD
- `docs/ASTOCK_TECH_REQUIREMENTS.md`：技术需求与模块拆解
- `docs/ASTOCK_BACKLOG.md`：待开发 backlog
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`：专业金融缺口、文档/代码/WebUI 边界与设计图
- `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`：Phase 30-38 产品优化路线图
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`：需求、模块、API/页面、测试、phase 追踪矩阵
- `docs/ASTOCK_PROJECT_RISK_REGISTER.md`：项目级技术、数据、交易、AI、UI、迁移风险台账
- `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`：架构和产品边界关键决策记录
- `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`：产品指标、运行指标、告警和 Ops 需求
- `docs/ASTOCK_API_CONTRACTS.md`：API envelope、错误码、能力等级和 schema 稳定性
- `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`：核心实体、数据质量、provider 血缘和快照要求
- `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`：DuckDB、cache、schema 变化后的迁移策略
- `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`：核心数据源用途、来源标注和使用边界
- `docs/ASTOCK_MODEL_GOVERNANCE.md`：AI provider、prompt、模型输出和降级治理
- `docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`：实盘/受控执行运行流程、故障处理和回滚
- `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`：核心功能环境、依赖、启动和健康检查
- `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`：测试分层、验收门槛和发布阻断条件
- `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`：核心功能变更、兼容和回滚要求
- `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`：风险披露、合规边界和禁止声明
- `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`：WebUI 信息架构、页面状态、能力标签和页面验收
- `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`：WebUI 页面输入、输出、状态、错误态和截图验收清单
- `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`：当前纳入范围和暂不纳入范围登记

## 2. 项目目标

基于原始 `TradingAgents` 多 Agent 金融研究框架，构建一个面向 A 股的投研与受控交易系统。

一句话定义：

`TradingAgents-Astock = A 股投研分析 + 多 Agent 研究辩论 + advisory 决策链 + 回测/模拟盘/受控执行 + WebUI/CLI 展示`

## 3. 产品边界

### 3.1 范围内

- A 股五层数据能力
- 多 Agent 研究链路
- advisory 决策链
- 回测
- 模拟盘
- QMT 受控执行
- DuckDB 本地存储
- Flask WebUI
- Streamlit 只读运行时 viewer
- CLI 交互入口
- 策略优化、绩效分析、策略对比

### 3.2 范围外

- 默认自动实盘
- 无人工确认的真实交易放开
- 脱离安全边界的 `actionable=true` 默认输出
- 多券商统一实盘适配
- 把 Streamlit 和 Flask WebUI 强行合并成一个前端体系
- 安全与隐私专项文档、SLA 与故障分级、用户角色/RBAC 当前只登记，不展开为需求模块

## 4. 目标用户

- A 股研究/策略验证用户
- 需要多 Agent 辅助分析的个人或团队
- 需要先回测、再模拟、最后受控执行的交易流程使用者

## 5. 核心业务流程

### 5.1 研究链

```text
AStockDataRouter
  -> AStockInterface
  -> AStockAnalyst
  -> Bull Researcher
  -> Bear Researcher
  -> Research Manager
  -> AStockGraphReport
```

### 5.2 advisory 链

```text
ResearchConclusion
  -> TraderProposal
  -> RiskDecision
  -> PortfolioDecision
```

### 5.3 执行链

```text
BacktestEngine
  -> PaperTrader
  -> QmtExecution (managed mode / safety mode default)
```

## 6. 功能需求

### FR-01 A 股五层数据能力

系统必须提供五层数据能力：

- 行情层
- 研报层
- 新闻层
- 基础数据层
- 公告层

五层能力应通过统一接口暴露，不允许上层 Agent 直接耦合具体 provider。

### FR-02 统一数据访问层

系统必须提供统一的 `AStockInterface` / provider router，负责：

- symbol 标准化
- 主源/备源路由
- fallback
- 错误语义统一
- 分桶缓存

### FR-03 多 Agent 研究能力

系统必须支持以下研究角色：

- AStockAnalyst
- Bull Researcher
- Bear Researcher
- Research Manager

输出必须能够汇总为统一 `AStockGraphReport`。

### FR-04 advisory 决策链

系统必须支持以下结构化合约：

- `ResearchConclusion`
- `TraderProposal`
- `RiskDecision`
- `PortfolioDecision`

这些合约用于研究后的结构化决策表达，但默认不直接触发自动实盘。

### FR-05 展示与报告

系统必须支持：

- CLI Markdown/JSON 报告
- Streamlit 只读 viewer
- Flask WebUI 报告与页面体系

展示层必须兼容 A 股报告与 legacy payload。

### FR-06 回测与模拟盘

系统必须支持：

- 回测引擎
- 模拟盘引擎
- 多策略运行
- 指标统计
- 批量回测
- 策略比较

### FR-07 受控执行

系统必须支持 QMT 桥接与受控执行，但执行层必须满足：

- `safety mode` 默认开启
- 人工确认可阻断执行
- QMT 不可用时降级到模拟盘
- 风控门在执行前生效

### FR-08 本地存储与缓存

系统必须支持本地持久化，包括：

- DuckDB 本地数据库
- 数据导入/导出
- 数据刷新
- 缓存状态查看
- 缓存清理

### FR-09 WebUI 产品能力

系统必须支持 WebUI 产品端入口，覆盖：

- Dashboard
- 研究结果查看
- 回测与策略优化
- 绩效分析
- 数据刷新/缓存管理
- 策略对比
- QMT 状态查看

### FR-10 测试与回归

系统必须具备可重复回归能力：

- 全仓 pytest 可运行
- A 股主链切片可独立运行
- 外部依赖测试有清晰 skip guard
- 不依赖临时导入污染或手工环境修补

## 7. 非功能需求

### NFR-01 安全边界

A 股研究与执行链必须遵守：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

直到用户在安全模式下显式放行。

### NFR-02 可审计性

每个 Delivery Phase 必须归档到 `docs/phases/`，包含：

- scope
- implementation evidence
- tests
- risks
- next entry criteria
- commit SHA

### NFR-03 可维护性

需求、状态、phase 归档必须分层维护：

- 需求文档不直接充当状态文档
- 状态文档不替代 phase 证据
- phase 文档不替代总需求

### NFR-04 可扩展性

数据源、策略、执行模式、报告页面应可扩展，不应与单一 provider 强绑定。

### NFR-05 产品可观测性

系统必须逐步形成可观测产品指标：

- 研究报告生成成功率
- 回测完成率
- provider 可用率和数据新鲜度
- 任务失败率和 API 错误率
- 风控拦截率、人工确认率和订单异常率
- 审计事件覆盖率

指标定义和 Ops 要求以 `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md` 为准。

### NFR-06 API 契约稳定性

所有新增或变更 API 必须满足：

- 标注 `research`、`paper`、`managed`、`live-ready` 能力等级
- 使用稳定 response envelope 或在 phase 中说明兼容例外
- 统一错误码、错误分类、retryable 语义和 request id
- mock/paper/managed/live-ready 不得混用或误导
- 交易相关 API 必须返回风控、确认和审计引用

API 口径以 `docs/ASTOCK_API_CONTRACTS.md` 为准。

### NFR-07 数据字典与血缘

所有数据、回测、研究和交易输出必须逐步具备：

- 核心实体字段定义
- provider/source/fallback 轨迹
- freshness、quality、snapshot 标记
- 复权、交易日历、停牌、涨跌停、ST/退市等数据假设
- 可被 AI Research、Strategy Lab、Trading、Ops 复用的数据快照 ID

数据口径以 `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md` 为准。

### NFR-08 测试验收与发布门槛

每个后续 phase 必须提供可复验的测试证据：

- unit / contract / integration / UI/API slice / regression 分层测试
- live provider、LLM、QMT 等外部依赖必须有 skip guard 或受控验证说明
- API/schema/store/UI 变化必须有对应验收项
- 失败、跳过、风险、回滚和 commit SHA 必须进入 phase 归档

测试与验收口径以 `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md` 为准。

### NFR-09 风险披露与合规边界

系统必须在产品、页面、报告和文档中保持以下边界：

- AI 输出不是投资建议，不承诺收益
- 回测和模拟盘不代表未来实盘表现
- 数据源延迟、缺失、fallback 和质量风险必须显式披露
- 未完成 live-ready checklist 前，不得声称完整自动实盘生产能力
- 真实交易前必须保留人工确认、风控拦截和审计证据

风险与合规口径以 `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md` 为准。

### NFR-10 核心功能环境可复现

研究、回测、模拟盘、受控执行和 WebUI 等核心功能必须具备可复现环境说明：

- 环境类型
- 依赖清单
- 启动顺序
- provider / DuckDB / LLM / QMT 健康检查
- degraded 状态说明

环境口径以 `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md` 为准。

### NFR-11 AI 模型治理

AI Research 和 advisory 输出必须具备：

- model provider 和 model name
- prompt version
- input snapshot ids
- advisory-only 标记
- LLM 不可用时的 fail closed 或 degraded 行为

模型治理口径以 `docs/ASTOCK_MODEL_GOVERNANCE.md` 为准。

### NFR-12 核心功能变更兼容

后续 phase 的 API、data、AI、strategy、trading、UI 变更必须记录：

- 需求 ID
- 影响模块
- schema 变化
- 测试命令
- 回滚路径
- 是否影响原 TradingAgents core

变更口径以 `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md` 为准。

### NFR-13 WebUI 页面级一致性

WebUI 核心页面必须统一：

- 顶层信息架构
- loading / empty / degraded / error / stale 页面状态
- research / paper / managed / live-ready / mock 能力标签
- 旧入口迁移策略

WebUI 口径以 `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md` 为准。

### NFR-16 数据迁移与升级

DuckDB、cache、schema、报告归档和回测结果结构变化必须具备：

- 迁移前后 schema 摘要
- 迁移命令或脚本
- cache 清理/重建策略
- API/WebUI 回归验证
- 回滚或不可回滚说明

迁移口径以 `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md` 为准。

### NFR-17 WebUI 页面级验收

每个 WebUI 页面开发或重构必须记录：

- 页面入口、URL/route 和能力等级
- 输入、输出、API 依赖和数据来源
- loading、empty、success、stale、degraded、error 状态
- 错误码、用户提示和重试动作
- success、empty、error/degraded 截图或替代证据

页面验收口径以 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md` 为准。

## 8. 当前实现对照

截至当前仓库状态：

- 正式归档已执行到 `Phase 29`
- `Phase 0-29` 已在 `docs/ASTOCK_CURRENT_STATUS.md` 与 `docs/phases/README.md` 中标记完成
- 当前专业评审口径以 `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` 为准：已完成能力不等同于完整实盘生产能力

当前已大面积落地的需求：

- 五层数据路由
- A 股研究链
- advisory 决策链
- 回测与模拟盘
- QMT 受控执行
- DuckDB
- Flask WebUI
- Streamlit viewer
- 策略优化与绩效分析
- 策略对比
- 回归稳定化
- KLineChart、AI Agent、筛选器、板块/资金页面、动量轮动、专业交易页

## 9. 当前未完全闭环项

以下模块在仓库中已出现，但仍不应视为“完全实现”：

- QMT 作为五层 provider 的完整能力口径仍未完全收口
- QMT fundamentals 仍是占位/不提供
- `/api/v1/qmt/orders` 仍是 mock/read-only 响应
- `/api/v1/trade/state` 属于 Paper Trading 路径，不代表真实账户状态
- 实盘级账户、订单、成交、撤单、拒单、部分成交和券商回报 reconciliation 尚未闭环
- 策略、回测、优化、绩效、动量轮动需要收敛到统一 Strategy Lab
- AI Agent、研究报告、新闻/公告/研报解读需要收敛到统一 AI Research Center
- 龙头相关页面需要收敛为最多一个顶层入口，并在入口内部通过顶部 tab 切换

## 10. 后续需求入口

后续需求主线以 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` 为准。当前建议顺序为：

1. Phase 30：Live Trading Readiness，先定实盘准入和能力口径。
2. Phase 31：Data Quality & Bias Control，补数据可信和回测可信。
3. Phase 32：Strategy Lab，收敛策略与回测产品线。
4. Phase 33：AI Research Center，收敛 AI 投研与报告审计。
5. Phase 34：Market Leaders，收敛龙头和资金线索入口。
6. Phase 35：Trading & Execution，补订单、成交、风控执行闭环。
7. Phase 36：Portfolio Risk & Attribution，升级到组合级专业能力。
8. Phase 37：Ops & Audit，统一运行、错误、审计和健康状态。
9. Phase 38：Product Navigation Cleanup，清理 UI 入口和体验一致性。

所有后续 phase 必须在 `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md` 中有需求 ID 映射。

## 11. 关联文档

- `planning/codebase/ASTOCK_RESOURCE_PLAN.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
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
- `docs/phases/README.md`
- `docs/phases/phase-00-boundary-blueprint.md`
- `docs/phases/phase-09-trader-risk-portfolio.md`
- `docs/phases/phase-10-backtest-paper-trading.md`
- `docs/phases/phase-11-qmt-controlled-execution.md`
- `docs/phases/phase-20-comparison-webui.md`
- `docs/phases/phase-21-test-stabilization.md`

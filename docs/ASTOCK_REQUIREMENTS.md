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

如果继续推进需求，优先顺序建议为：

1. 统一 QMT / trade API 的真实能力边界
2. 建立实盘准入 checklist：账户、订单、成交、风控、审计、kill switch、reconciliation
3. 建立 `Strategy Lab` 模块边界，统一策略、回测、优化、绩效、动量轮动
4. 建立 `AI Research Center` 模块边界，统一 AI 分析、研究报告、数据上下文和审计
5. 建立 `Market Leaders` 单入口，收敛龙头动量、轮动、板块、资金线索和候选池

## 11. 关联文档

- `planning/codebase/ASTOCK_RESOURCE_PLAN.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
- `docs/phases/README.md`
- `docs/phases/phase-00-boundary-blueprint.md`
- `docs/phases/phase-09-trader-risk-portfolio.md`
- `docs/phases/phase-10-backtest-paper-trading.md`
- `docs/phases/phase-11-qmt-controlled-execution.md`
- `docs/phases/phase-20-comparison-webui.md`
- `docs/phases/phase-21-test-stabilization.md`

# Product Requirements Document

> 合并自 `ASTOCK_PRD.md` + `ASTOCK_REQUIREMENTS.md` + `ASTOCK_TECH_REQUIREMENTS.md`

---

## 1. 产品概述

### 1.1 产品名称

`TradingAgents-Astock`

### 1.2 产品定义

一个面向 A 股场景的多 Agent 投研与受控交易系统，覆盖研究、报告、回测、模拟盘、QMT 受控执行和产品化 WebUI。

### 1.3 产品目标

- 为 A 股研究与策略验证提供统一工作台
- 用多 Agent 研究链替代单一结论式分析
- 在研究、回测、模拟盘、受控执行之间建立连续闭环
- 保持安全边界，避免默认自动实盘

## 2. 目标用户

- 个人投资研究者
- 量化/策略验证用户
- 需要多 Agent 辅助研究的交易团队
- 需要受控执行而非默认自动交易的使用者

## 3. 用户核心场景

### 场景 A：研究驱动

用户输入股票代码、日期、运行模式后，系统生成 A 股研究报告，包括五层数据摘要、多空辩论结论和 advisory 决策结果。

### 场景 B：策略验证

用户选择策略、区间和参数，在 WebUI 或 API 中运行回测、对比收益/回撤/Sharpe，并查看绩效图表。

### 场景 C：模拟盘试跑

用户在不触发真实交易的情况下运行 PaperTrader，验证信号、仓位、交易记录和风控逻辑。

### 场景 D：受控执行

用户在 QMT 可用的环境下，通过安全模式执行受控下单，由人工确认和风控规则共同把关。

## 4. 产品范围

### 4.1 包含范围

- 五层数据能力
- 多 Agent 研究链
- advisory 决策链
- 报告展示
- 回测
- 模拟盘
- QMT 受控执行
- 数据存储与缓存
- Flask WebUI
- Streamlit 只读 viewer
- CLI

### 4.2 不包含范围

- 默认自动实盘
- 无风控、无确认的下单放开
- 多券商统一抽象
- 把所有前端入口合并成一套运行时 UI
- 安全与隐私专项、SLA 与故障分级、用户角色/RBAC 当前只登记，不进入核心功能需求

## 5. 产品能力需求

### PRD-01 数据能力

系统应覆盖：

- 行情层
- 研报层
- 新闻层
- 基础数据层
- 公告层

### PRD-02 研究能力

系统应支持：

- AStockAnalyst
- Bull Researcher
- Bear Researcher
- Research Manager

并形成统一研究输出。

### PRD-03 决策表达

系统应输出结构化 advisory 结果：

- ResearchConclusion
- TraderProposal
- RiskDecision
- PortfolioDecision

### PRD-04 展示能力

系统应支持：

- CLI 报告
- Streamlit 只读 viewer
- WebUI 报告与产品页面

### PRD-05 回测与策略能力

系统应支持：

- 多策略回测
- 批量回测
- 策略优化
- 策略对比
- 绩效分析

### PRD-06 交易模拟与受控执行

系统应支持：

- 模拟盘
- QMT 桥接
- 安全模式
- 人工确认
- 风控门

## 6. 安全与约束

### 6.1 默认安全边界

研究输出默认必须满足：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

### 6.2 执行约束

- `safety mode` 默认开启
- 用户必须显式选择 auto mode
- QMT 不可用时降级到模拟盘
- 风控门先于执行生效

## 7. 当前产品状态

当前仓库已正式归档到 `Phase 29`，大部分产品能力已落地，包括：

- 研究链
- advisory 链
- 回测与模拟盘
- QMT 受控执行
- 数据库与缓存
- WebUI
- 策略优化与绩效分析
- 全仓回归稳定化
- KLineChart、筛选器、板块/资金页面、动量轮动、AI Agent、专业交易页

## 8. 当前产品缺口

- QMT 在 provider 口径上的能力定义仍不完全收口
- trade state 属于 Paper Trading 路径，不代表真实账户状态
- 实盘账户、订单、成交、撤单、拒单、部分成交和券商回报 reconciliation 尚未闭环
- 策略、回测、优化、绩效、策略对比、动量轮动需要收敛为统一 Strategy Lab
- AI Agent、研究报告、新闻/公告/研报解读需要收敛为统一 AI Research Center
- 龙头相关入口需要收敛为一个顶层入口，内部用顶部 tab 切换动量、轮动、板块、资金线索和候选池
- 数据质量、回测反偏差、组合级风控和审计链路仍需加强
- 部分“模块已存在”和“产品能力完整”之间仍有差距

## 8.1 实盘分析判断

当前新功能可以支撑实盘前研究、盘中辅助观察、策略验证和受控执行试运行，但不应定义为完整实盘生产交易系统。

可用于实盘辅助分析的能力：

- 实时/准实时行情与 K 线展示
- 新闻、公告、研报、F10、估值等多源数据辅助
- AI research/advisory chain
- 策略回测、优化、绩效和模拟盘验证
- QMT managed mode / safety mode 的受控执行雏形

进入完整实盘生产前仍需补齐：

- 实盘账户、订单、成交和券商回报闭环
- kill switch、硬风控、权限、审计和异常恢复
- 数据质量分级、数据快照和可追溯 provenance
- 回测反偏差、out-of-sample、walk-forward 和过拟合检测
- 组合级风险、容量、流动性和绩效归因

## 9. 成功标准

- 用户可以完成从研究到回测、模拟盘、受控执行的连续流程
- 默认路径不触发自动实盘
- WebUI/CLI/viewer 角色清晰
- 回归稳定，产品迭代后可复验
- 所有页面明确标注 research / paper / managed / live-ready 能力边界
- 关键产品指标可被追踪，包括研究报告生成成功率、回测完成率、provider 可用率、任务失败率和审计事件覆盖率
- 后续 Phase 30-38 的每项需求都能在需求追踪矩阵中定位到模块、页面/API、测试和 phase 证据
- API、数据、运行、测试和风险披露均有独立文档约束，不依赖口头约定
- 每个 live-ready 声明都能追溯到准入清单、运行手册、测试验收和风险披露
- 商用交付前必须能回答“当前能力等级、数据来源、测试证据、失败处理、合规边界”五个问题

## 9.1 后续产品路线

后续路线以 `BACKLOG.md` 为准：

1. Phase 30：Live Trading Readiness
2. Phase 31：Data Quality & Bias Control
3. Phase 32：Strategy Lab
4. Phase 33：AI Research Center
5. Phase 34：Market Leaders
6. Phase 35：Trading & Execution
7. Phase 36：Portfolio Risk & Attribution
8. Phase 37：Ops & Audit
9. Phase 38：Product Navigation Cleanup

## 9.2 商用生产级文档要求

后续开发必须按以下文档闭环执行：

- API 变更先更新 `01-arch/API.md`，再进入代码实现。
- 数据字段、provider、质量标签、血缘和快照变更先更新 `03-ops/data-sources.md`。
- DuckDB、cache、schema、报告归档和回测结果结构变更先更新 `04-dev/PRD.md`。
- 受控执行、QMT、订单、风控、故障处理和回滚流程先更新 `03-ops/live-trading.md`。
- 每个 phase 必须按 `04-dev/test-plan.md` 留存测试命令、结果和阻断项。
- 页面、报告、AI 输出、回测结果和交易入口必须遵守 `03-ops/compliance.md`。
- 核心功能启动、依赖和健康检查必须遵守 `03-ops/deployment.md`。
- AI provider、prompt、模型输出和降级必须遵守 `03-ops/compliance.md`。
- WebUI 页面状态、能力标签和顶层导航必须遵守 `02-guide/USER_MANUAL.md`。
- WebUI 页面输入、输出、状态、错误态和截图证据必须遵守 `README.md`。
- API/data/AI/trading/UI 兼容性变化必须遵守 `03-ops/deployment.md`。
- 当前暂不纳入范围必须以 `README.md` 为准，不得隐式扩展。

## 10. 关联文档

- `04-dev/PRD.md`
- `04-dev/PRD.md`
- `BACKLOG.md`
- `04-dev/PRD.md`
- `BACKLOG.md`
- `04-dev/traceability-matrix.md`
- `03-ops/ops-metrics.md`
- `01-arch/API.md`
- `03-ops/data-sources.md`
- `04-dev/PRD.md`
- `03-ops/data-sources.md`
- `03-ops/compliance.md`
- `03-ops/live-trading.md`
- `03-ops/deployment.md`
- `04-dev/test-plan.md`
- `03-ops/deployment.md`
- `03-ops/compliance.md`
- `02-guide/USER_MANUAL.md`
- `README.md`
- `README.md`
- `phases/README.md`



---

## 2. 需求详情

> 以下内容来自 `ASTOCK_REQUIREMENTS.md`


## 1. 文档定位

本文档整理当前仓库的 A 股二次开发需求，统一以下三类信息：

- 产品目标与范围
- 功能/模块需求
- 当前实现边界与未闭环项

使用规则：

- 需求目标以本文档和 `planning/codebase/ASTOCK_RESOURCE_PLAN.md` 为准
- 当前实现事实以 `phases/README.md` 为准
- 每个阶段的实现证据以 `docs/phases/` 为准

配套拆分文档：

- `04-dev/PRD.md`：产品需求 PRD
- `04-dev/PRD.md`：技术需求与模块拆解
- `BACKLOG.md`：待开发 backlog
- `04-dev/PRD.md`：专业金融缺口、文档/代码/WebUI 边界与设计图
- `BACKLOG.md`：Phase 30-38 产品优化路线图
- `04-dev/traceability-matrix.md`：需求、模块、API/页面、测试、phase 追踪矩阵
- `03-ops/risk-register.md`：项目级技术、数据、交易、AI、UI、迁移风险台账
- `01-arch/ADR.md`：架构和产品边界关键决策记录
- `03-ops/ops-metrics.md`：产品指标、运行指标、告警和 Ops 需求
- `01-arch/API.md`：API envelope、错误码、能力等级和 schema 稳定性
- `03-ops/data-sources.md`：核心实体、数据质量、provider 血缘和快照要求
- `04-dev/PRD.md`：DuckDB、cache、schema 变化后的迁移策略
- `03-ops/data-sources.md`：核心数据源用途、来源标注和使用边界
- `03-ops/compliance.md`：AI provider、prompt、模型输出和降级治理
- `03-ops/live-trading.md`：实盘/受控执行运行流程、故障处理和回滚
- `03-ops/deployment.md`：核心功能环境、依赖、启动和健康检查
- `04-dev/test-plan.md`：测试分层、验收门槛和发布阻断条件
- `03-ops/deployment.md`：核心功能变更、兼容和回滚要求
- `03-ops/compliance.md`：风险披露、合规边界和禁止声明
- `02-guide/USER_MANUAL.md`：WebUI 信息架构、页面状态、能力标签和页面验收
- `README.md`：WebUI 页面输入、输出、状态、错误态和截图验收清单
- `README.md`：当前纳入范围和暂不纳入范围登记

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

指标定义和 Ops 要求以 `03-ops/ops-metrics.md` 为准。

### NFR-06 API 契约稳定性

所有新增或变更 API 必须满足：

- 标注 `research`、`paper`、`managed`、`live-ready` 能力等级
- 使用稳定 response envelope 或在 phase 中说明兼容例外
- 统一错误码、错误分类、retryable 语义和 request id
- mock/paper/managed/live-ready 不得混用或误导
- 交易相关 API 必须返回风控、确认和审计引用

API 口径以 `01-arch/API.md` 为准。

### NFR-07 数据字典与血缘

所有数据、回测、研究和交易输出必须逐步具备：

- 核心实体字段定义
- provider/source/fallback 轨迹
- freshness、quality、snapshot 标记
- 复权、交易日历、停牌、涨跌停、ST/退市等数据假设
- 可被 AI Research、Strategy Lab、Trading、Ops 复用的数据快照 ID

数据口径以 `03-ops/data-sources.md` 为准。

### NFR-08 测试验收与发布门槛

每个后续 phase 必须提供可复验的测试证据：

- unit / contract / integration / UI/API slice / regression 分层测试
- live provider、LLM、QMT 等外部依赖必须有 skip guard 或受控验证说明
- API/schema/store/UI 变化必须有对应验收项
- 失败、跳过、风险、回滚和 commit SHA 必须进入 phase 归档

测试与验收口径以 `04-dev/test-plan.md` 为准。

### NFR-09 风险披露与合规边界

系统必须在产品、页面、报告和文档中保持以下边界：

- AI 输出不是投资建议，不承诺收益
- 回测和模拟盘不代表未来实盘表现
- 数据源延迟、缺失、fallback 和质量风险必须显式披露
- 未完成 live-ready checklist 前，不得声称完整自动实盘生产能力
- 真实交易前必须保留人工确认、风控拦截和审计证据

风险与合规口径以 `03-ops/compliance.md` 为准。

### NFR-10 核心功能环境可复现

研究、回测、模拟盘、受控执行和 WebUI 等核心功能必须具备可复现环境说明：

- 环境类型
- 依赖清单
- 启动顺序
- provider / DuckDB / LLM / QMT 健康检查
- degraded 状态说明

环境口径以 `03-ops/deployment.md` 为准。

### NFR-11 AI 模型治理

AI Research 和 advisory 输出必须具备：

- model provider 和 model name
- prompt version
- input snapshot ids
- advisory-only 标记
- LLM 不可用时的 fail closed 或 degraded 行为

模型治理口径以 `03-ops/compliance.md` 为准。

### NFR-12 核心功能变更兼容

后续 phase 的 API、data、AI、strategy、trading、UI 变更必须记录：

- 需求 ID
- 影响模块
- schema 变化
- 测试命令
- 回滚路径
- 是否影响原 TradingAgents core

变更口径以 `03-ops/deployment.md` 为准。

### NFR-13 WebUI 页面级一致性

WebUI 核心页面必须统一：

- 顶层信息架构
- loading / empty / degraded / error / stale 页面状态
- research / paper / managed / live-ready / mock 能力标签
- 旧入口迁移策略

WebUI 口径以 `02-guide/USER_MANUAL.md` 为准。

### NFR-16 数据迁移与升级

DuckDB、cache、schema、报告归档和回测结果结构变化必须具备：

- 迁移前后 schema 摘要
- 迁移命令或脚本
- cache 清理/重建策略
- API/WebUI 回归验证
- 回滚或不可回滚说明

迁移口径以 `04-dev/PRD.md` 为准。

### NFR-17 WebUI 页面级验收

每个 WebUI 页面开发或重构必须记录：

- 页面入口、URL/route 和能力等级
- 输入、输出、API 依赖和数据来源
- loading、empty、success、stale、degraded、error 状态
- 错误码、用户提示和重试动作
- success、empty、error/degraded 截图或替代证据

页面验收口径以 `README.md` 为准。

## 8. 当前实现对照

截至当前仓库状态：

- 正式归档已执行到 `Phase 29`
- `Phase 0-29` 已在 `phases/README.md` 与 `docs/phases/README.md` 中标记完成
- 当前专业评审口径以 `04-dev/PRD.md` 为准：已完成能力不等同于完整实盘生产能力

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

后续需求主线以 `BACKLOG.md` 为准。当前建议顺序为：

1. Phase 30：Live Trading Readiness，先定实盘准入和能力口径。
2. Phase 31：Data Quality & Bias Control，补数据可信和回测可信。
3. Phase 32：Strategy Lab，收敛策略与回测产品线。
4. Phase 33：AI Research Center，收敛 AI 投研与报告审计。
5. Phase 34：Market Leaders，收敛龙头和资金线索入口。
6. Phase 35：Trading & Execution，补订单、成交、风控执行闭环。
7. Phase 36：Portfolio Risk & Attribution，升级到组合级专业能力。
8. Phase 37：Ops & Audit，统一运行、错误、审计和健康状态。
9. Phase 38：Product Navigation Cleanup，清理 UI 入口和体验一致性。

所有后续 phase 必须在 `04-dev/traceability-matrix.md` 中有需求 ID 映射。

## 11. 关联文档

- `planning/codebase/ASTOCK_RESOURCE_PLAN.md`
- `04-dev/PRD.md`
- `04-dev/PRD.md`
- `BACKLOG.md`
- `04-dev/PRD.md`
- `BACKLOG.md`
- `04-dev/traceability-matrix.md`
- `03-ops/ops-metrics.md`
- `01-arch/API.md`
- `03-ops/data-sources.md`
- `04-dev/PRD.md`
- `03-ops/data-sources.md`
- `03-ops/compliance.md`
- `03-ops/live-trading.md`
- `03-ops/deployment.md`
- `04-dev/test-plan.md`
- `03-ops/deployment.md`
- `03-ops/compliance.md`
- `02-guide/USER_MANUAL.md`
- `README.md`
- `README.md`
- `phases/README.md`
- `docs/phases/README.md`
- `docs/phases/phase-00-boundary-blueprint.md`
- `docs/phases/phase-09-trader-risk-portfolio.md`
- `docs/phases/phase-10-backtest-paper-trading.md`
- `docs/phases/phase-11-qmt-controlled-execution.md`
- `docs/phases/phase-20-comparison-webui.md`
- `docs/phases/phase-21-test-stabilization.md`



---

## 3. 技术需求

> 以下内容来自 `ASTOCK_TECH_REQUIREMENTS.md`


## 1. 文档目标

本文档从技术实现角度拆解当前项目需求，说明：

- 需要哪些模块
- 模块之间如何衔接
- 每个模块当前大致状态
- 哪些地方仍未完全闭环
- 专业金融系统视角下，哪些模块需要收敛为更清晰的产品/工程边界

## 2. 顶层架构需求

系统技术上应分为以下层次：

- 数据源与 provider 层
- 统一数据访问层
- A 股研究链
- advisory 决策链
- 执行层
- 存储层
- API 层
- 展示层
- 测试与验证层

下一阶段建议新增三个聚合模块边界：

- `Strategy Lab`：统一策略、回测、优化、绩效、策略对比、动量轮动
- `AI Research Center`：统一 AI Agent、A 股研究报告、新闻/公告/研报解读、报告归档与审计
- `Market Leaders`：统一龙头动量、轮动回测、板块强弱、资金线索和候选池

## 3. 模块需求拆解

### 3.1 Provider 与数据路由层

目标模块：

- `tradingagents/astock/data_sources/router.py`
- `tradingagents/astock/data_sources/adapters.py`
- `tradingagents/astock/data_sources/schema.py`
- `tradingagents/astock/data_sources/symbols.py`
- `tradingagents/astock/data_sources/cache.py`

技术要求：

- 五层能力映射到 provider
- symbol 标准化
- fallback
- 缓存
- 错误语义统一

当前状态：

- 主体已实现
- QMT provider 口径仍未完全收口

### 3.2 统一接口层

目标模块：

- `tradingagents/astock/interface.py`
- `tradingagents/astock/tools.py`

技术要求：

- 对上层暴露稳定 section 接口
- 输出统一 bundle
- 与具体 provider 解耦

当前状态：

- 已实现

### 3.3 A 股研究链

目标模块：

- `tradingagents/astock/analyst.py`
- `tradingagents/astock/runtime.py`
- `tradingagents/astock/runtime_profile.py`
- `tradingagents/astock/phase9_schemas.py`

技术要求：

- 支持 deterministic verification 与 live research
- 输出统一 `AStockGraphReport`
- 支持 advisory 字段扩展

当前状态：

- 已实现

### 3.4 advisory 决策链

目标模块：

- `ResearchConclusion`
- `TraderProposal`
- `RiskDecision`
- `PortfolioDecision`

技术要求：

- 结构化 schema
- CLI/UI 可渲染
- 保持 research-only 安全边界

当前状态：

- 已实现

### 3.5 执行层

目标模块：

- `tradingagents/astock/execution/backtest_engine.py`
- `tradingagents/astock/execution/paper_trader.py`
- `tradingagents/astock/execution/qmt_bridge.py`
- `tradingagents/astock/execution/qmt_execution.py`
- `tradingagents/astock/execution/risk_gate.py`
- `tradingagents/astock/execution/strategy_base.py`
- `tradingagents/astock/execution/optimizer.py`
- `tradingagents/astock/execution/batch_backtest.py`
- `tradingagents/astock/execution/scheduler.py`

技术要求：

- 回测
- 模拟盘
- QMT 桥接
- 风控门
- 多策略
- 参数优化
- 批处理与调度

当前状态：

- 主体已实现
- 部分 trade/QMT API 仍有 mock 或受限口径
- 策略与回测能力已经可用，但策略注册、参数 schema、回测数据约束、绩效归因和动量轮动入口仍需要收敛到统一 Strategy Lab

### 3.6 存储层

目标模块：

- `tradingagents/astock/store/schema.py`
- `tradingagents/astock/store/loader.py`

技术要求：

- DuckDB 本地存储
- 导入/导出
- 结果查询
- 回测/报告/数据缓存承载

当前状态：

- 已实现

### 3.7 API 层

目标模块：

- `tradingagents/astock/api/routes_backtest.py`
- `routes_dashboard.py`
- `routes_data.py`
- `routes_data_health.py`
- `routes_market.py`
- `routes_market_data.py`
- `routes_paper.py`
- `routes_qmt.py`
- `routes_reports.py`
- `routes_screener.py`
- `routes_sse.py`
- `routes_trade.py`

技术要求：

- 研究、市场、回测、模拟盘、QMT、trade、SSE、报告能力的统一 HTTP 暴露
- 返回格式稳定
- mock 与 real 能力边界清晰

当前状态：

- 主体已实现
- `routes_qmt.py` 和 `routes_trade.py` 中仍有部分 mock/占位实现

### 3.8 展示层

目标模块：

- `cli/main.py`
- `tradingagents/ui/*`
- `tradingagents/astock/web/*`

技术要求：

- CLI 研究入口
- Streamlit 只读 viewer
- Flask WebUI 产品端入口
- A 股与 legacy payload 兼容展示

当前状态：

- 已实现
- 专业交易页已完成 Phase 29 归档
- AI Agent、研究报告、策略工作台、龙头相关页面的产品入口仍需要进一步收敛

### 3.9 测试与验证层

目标模块：

- `tests/`
- `tests/conftest.py`
- `docs/phases/phase-21-test-stabilization.md`

技术要求：

- 全仓回归稳定
- A 股主链切片稳定
- 外部依赖测试有 guard
- 测试不依赖导入污染

当前状态：

- 已实现，Phase 21 记录为稳定基线

### 3.10 Strategy Lab 目标模块

策略开发的具体规范以 `02-guide/strategy-dev.md` 为准。该规范来自 Hermes `tradingagents-core` skill 的 Section 12 蒸馏内容，覆盖 `StrategyBase -> generate_signals` 生命周期、五类信号模式、三个策略注册点、优化器复合评分、多股票组合策略和 baostock 批量拉取约束。

目标模块：

- `BacktestEngine`
- `StrategyBase` 及所有策略实现
- `StrategyOptimizer`
- `BatchBacktestRunner`
- `momentum_rotation`
- WebUI `strategy_hub`
- API `routes_backtest.py` 与相关策略/绩效端点

技术要求：

- 建立统一策略注册表
- 建立统一参数 schema 与默认搜索空间
- 新增策略必须检查 `execution/__init__.py`、`routes_backtest.py` 的 `_STRATEGY_REGISTRY`、`routes_market.py` 的 `AVAILABLE_STRATEGIES`
- 单标的策略必须继承 `StrategyBase` 并实现 `generate_signals(data) -> pd.Series`
- 多股票组合策略允许保持 Standalone 模式，但必须输出组合净值、持仓、调仓记录和 benchmark
- 建立统一成本、滑点、T+1、停牌、涨跌停和成交量约束
- 建立统一 backtest result / trade detail / equity curve / benchmark 输出 schema
- 支持单标的、多标的、组合、批量、优化、对比、动量轮动
- 把策略运行结果写入 DuckDB 或统一结果仓库
- 参数优化默认使用复合评分：`0.35 * Sharpe + 0.30 * Return - 0.25 * Drawdown + 0.10 * TradeFrequency`
- 回测买入逻辑必须校验含费用后的 `net_cost <= cash`，避免负现金或死循环

当前状态：

- 策略、回测、优化、绩效、对比、动量轮动均已有实现
- 仍缺少统一模块边界和统一注册/结果 schema

### 3.11 AI Research Center 目标模块

目标模块：

- `AStockGraphRuntime`
- `AStockGraphReport`
- `routes_ai_agent.py`
- `routes_reports.py`
- WebUI `ai_agent.html`
- WebUI `research.html`
- PPT/Markdown/JSON 报告生成

技术要求：

- 统一 AI 研究任务入口
- 统一数据上下文：行情、财务、新闻、公告、研报、龙虎榜、北向、板块、策略结果
- 记录模型、prompt、输入数据版本、引用来源、生成时间和人工确认状态
- 所有 AI 输出默认保持 advisory，不直接下发真实交易指令
- 支持报告归档、复查和对比

当前状态：

- A 股 research runtime 与 AI Agent 页面已存在
- 缺少统一审计模型和 AI 分析产品边界

### 3.12 Market Leaders 目标模块

目标模块：

- 龙头动量总览
- 动量轮动回测
- 板块强弱
- 龙虎榜与北向资金线索
- 龙头候选池

技术要求：

- 顶层导航最多保留一个龙头入口
- 入口内部通过顶部 tab 切换子板块
- 旧页面保留兼容跳转或降级为子 tab
- 独立演示脚本不作为产品主入口

当前状态：

- 龙头动量、动量轮动、龙虎榜、北向、板块页面均已存在
- 入口分散，需要产品信息架构收敛

## 4. 模块间依赖关系

```text
data_sources
  -> interface/tools
  -> analyst/runtime
  -> advisory schemas
  -> execution
  -> api
  -> ui/web/cli
  -> tests
```

## 5. 技术缺口

- QMT provider 口径和执行层口径尚未完全统一
- QMT orders 查询仍是 mock 语义
- trade state 属于 PaperTrader 状态，不代表真实账户状态
- 缺少实盘级账户、订单、成交、撤单、拒单、部分成交和券商回报 reconciliation
- 缺少统一策略注册、参数 schema、结果 schema 和反过拟合验证流程
- 缺少 AI 分析审计链：prompt、模型、数据快照、引用来源、人工确认状态
- 龙头相关页面入口分散

## 6. 维护要求

- 新功能必须明确落在哪一层
- 不允许 UI 直接绕过 API/接口层读底层实现细节
- 不允许以 mock 能力冒充 real capability 写入状态文档
- phase 文档必须补 commit SHA 和测试证据

## 7. 关联文档

- `04-dev/PRD.md`
- `04-dev/PRD.md`
- `BACKLOG.md`
- `04-dev/PRD.md`
- `phases/README.md`


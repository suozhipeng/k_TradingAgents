# Product Requirements Document

> 本文档定义产品定位、目标用户、核心场景、能力需求和安全约束。详细需求分解和任务队列见 [`BACKLOG.md`](../BACKLOG.md)，模块技术细节见 [`full_function_documentation.md`](../full_function_documentation.md)。
>
> 合并自 ASTOCK_PRD.md + ASTOCK_REQUIREMENTS.md + ASTOCK_TECH_REQUIREMENTS.md

---

## 1. 产品概述

### 1.1 产品名称

`TradingAgents-Astock`

### 1.2 产品定义

一个面向 A 股场景的多 Agent 投研与受控交易系统，覆盖研究、报告、回测、模拟盘、QMT managed mock/read-only 边界和产品化 WebUI。

### 1.3 产品目标

- 为 A 股研究与策略验证提供统一工作台
- 用多 Agent 研究链替代单一结论式分析
- 在研究、回测、模拟盘、受控执行边界之间建立连续闭环
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

用户在当前阶段只能查看 QMT managed mock/read-only 状态；真实 QMT 下单、委托查询和券商回报对账属于 P3 准入后事项。

## 4. 产品范围

### 4.1 包含范围

- 五层数据能力
- 多 Agent 研究链
- advisory 决策链
- 报告展示
- 回测
- 模拟盘
- QMT managed mock/read-only 边界
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
- QMT mock/read-only 状态展示
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
- 当前不开放 auto mode
- QMT API/UI 固定 mock/read-only，不探测真实券商连接
- 风控门先于执行生效

## 7. 当前产品状态

当前仓库已正式归档到 `Phase 29`，大部分产品能力已落地，包括：

- 研究链
- advisory 链
- 回测与模拟盘
- QMT managed mock/read-only 边界
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

- `BACKLOG.md` — 待开发 backlog 和 Phase 30-39 路线图
- `04-dev/traceability-matrix.md` — 需求、模块、API/页面、测试、phase 追踪矩阵
- `03-ops/deployment.md` — 部署、环境、产品指标与监控
- `01-arch/API.md` — API 端点参考、错误码、能力等级
- `03-ops/data-sources.md` — 数据源授权、字典和血缘
- `03-ops/compliance.md` — 风险披露、合规边界与隐私声明
- `03-ops/live-trading.md` — 实盘运行手册
- `03-ops/risk-register.md` — 项目风险登记
- `04-dev/test-plan.md` — 测试验收计划
- `02-guide/USER_MANUAL.md` — WebUI 产品规范
- `02-guide/strategy-dev.md` — 策略开发规范
- `README.md` — 文档体系索引
- `phases/README.md` — 阶段索引
- `full_function_documentation.md` — 全功能文档
- `database_module_whitepaper.md` — 数据库模块白皮书


## 11. 维护要求

- 新功能必须明确落在哪一层
- 不允许 UI 直接绕过 API/接口层读底层实现细节
- 不允许以 mock 能力冒充 real capability 写入状态文档
- phase 文档必须补 commit SHA 和测试证据

---

> 本文档合并自 ASTOCK_PRD.md + ASTOCK_REQUIREMENTS.md + ASTOCK_TECH_REQUIREMENTS.md

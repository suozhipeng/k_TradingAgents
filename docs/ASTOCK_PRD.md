# TradingAgents-Astock 产品需求文档

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

## 10. 关联文档

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

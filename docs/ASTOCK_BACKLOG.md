# TradingAgents-Astock 待开发 Backlog

## 1. 文档目标

本文档整理当前仓库后续最值得推进的需求项，按优先级划分为：

- P0：必须尽快收口
- P1：高价值增强
- P2：后续优化

更完整的金融产品优化路线图见 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`。Backlog 负责记录执行队列，路线图负责说明为什么做、先做什么、每个模块如何达到金融产品可用口径。

## 2. P0

### BL-000 建立实盘准入清单

现状：

- 当前系统已经能支撑投研分析、回测、模拟盘和 QMT 受控执行
- 但专业金融系统的实盘生产闭环仍缺账户/订单/成交 reconciliation、审计、kill switch、数据质量和组合级风控门槛

目标：

- 建立 `Live Trading Readiness` checklist
- 明确哪些能力属于 `research`、`paper`、`managed`、`live-ready`
- 把实盘准入条件写入状态文档、技术文档和 phase 归档

完成标准：

- 有账户资产、持仓、委托、成交、撤单、拒单、部分成交、券商回报的状态模型要求
- 有 kill switch、最大亏损、最大仓位、最大单笔金额、交易时段、手工确认的硬约束
- 有审计要求：数据快照、AI prompt、模型版本、人工确认、订单回报全链路可追溯
- 文档明确当前系统“可实盘辅助分析”，但“不等于完整自动实盘生产系统”

### BL-001 统一 QMT 能力边界

现状：

- QMT 在执行层已存在
- QMT 在 blueprint/provider 口径里仍保留 placeholder 语义

目标：

- 统一 QMT 在 provider、execution、API、状态文档中的能力定义

完成标准：

- blueprint / status / phase / code 口径一致
- 不再同时出现“已完成执行”和“provider 仍占位”冲突

### BL-002 修正 `qmt/orders` 的 mock 语义

现状：

- `/api/v1/qmt/orders` 返回的是 mock/read-only 响应

目标：

- 接真实 QMT 订单/委托查询，或明确改名为 mock endpoint

完成标准：

- endpoint 语义与返回内容一致
- 文档不再误导为真实订单模块

### BL-003 修正 trade quote / trade state 的能力口径

现状：

- `trade/quote` 使用 EastMoney push2 实时报价 + Sina 降级 + 60s 缓存 — ✅ **已真实**
- `trade/state` 使用 PaperTrader 状态 + 实时报价估值 — ✅ **明确为 Paper Trading 路径**

目标：

- ✅ 已达成 — trade/quote 是实时数据（EastMoney → Sina → 缓存三级降级）
- trade/state 属于 Paper Trading，非实盘，文档已写明

完成标准：

- endpoint 语义与返回内容一致 — ✅ trade/quote 返回实时数据
- 用户不会把 mock 报价误认为真实交易报价 — ✅ trade/quote 已标注 source: "live"|"cache"；trade/state 通过 PaperTrader 路径

### BL-004 为专业交易页建立正式归档

现状：

- `trading.html`、`routes_trade.py`、相关测试已进入代码
- 已建立独立 phase 归档 `docs/phases/phase-29-trading-page.md`

目标：

- ✅ 已达成 — 有 scope、测试、风险说明、commit SHA

完成标准：

- 有 scope — ✅ `phase-29-trading-page.md`
- 有测试 — ✅ WebUI + API 切片 150 passed
- 有风险说明 — ✅ 实时报价依赖/缓存/持久化
- 有 commit SHA — ✅ `268d326`, `87e5b73`, `1960c65` 等

## 3. P1

### BL-100 Strategy Lab 模块整合

现状：

- 策略、回测、批量回测、优化、绩效、策略对比、动量轮动均已有实现
- 当前能力分散在 execution、API、WebUI 和独立动量入口中
- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` 已固化策略生命周期、注册点、复合评分和常见陷阱

目标：

- 将策略模块和回测能力统一到一个 Strategy Lab 产品/工程边界
- 统一策略注册、参数 schema、结果 schema、成本模型、风控约束和绩效归因

完成标准：

- 有 `phase-30-strategy-lab-consolidation.md` 归档
- 所有策略均可通过统一 registry 描述参数和适用场景
- 单标的策略符合 `StrategyBase -> generate_signals` 规范
- 动量轮动等组合策略明确使用 Standalone 模式或 StrategyBase 兼容模式
- `_STRATEGY_REGISTRY`、`AVAILABLE_STRATEGIES` 和包级导出不再各自漂移
- Backtest / Optimize / Compare / Performance / Momentum Rotation 在产品侧属于同一模块
- 旧入口有明确兼容策略或迁移计划

### BL-100A AI Research Center 模块整合

现状：

- AI Agent 页面、A 股 research runtime、报告中心、研究页面均已存在
- AI 分析的上下文、prompt、模型、引用、报告归档和人工确认状态尚未统一

目标：

- 将 AI Agent、A 股研究报告、新闻/公告/研报解读、策略解释整合为 AI Research Center
- 保持所有 AI 输出默认 advisory，不直接触发真实交易

完成标准：

- 有 `phase-31-ai-research-center.md` 归档
- AI 任务记录模型、prompt、输入数据快照、引用来源、生成时间和人工确认状态
- AI Research Center 可以调用行情、财务、公告、新闻、研报、策略结果和持仓风险作为上下文
- 报告中心统一管理 Markdown/JSON/PPT/Web report

### BL-100B 龙头相关单入口

现状：

- 龙头动量总览、动量轮动、龙虎榜、北向资金、板块页面已经存在
- 入口分散，用户会把龙头、板块、资金和动量策略理解成不同产品线

目标：

- 顶层最多保留一个龙头相关入口
- 在该入口内部用顶部 tab 切换不同子板块

完成标准：

- 有 `phase-32-market-leaders-entry.md` 归档
- 顶层导航只出现一个 `Market Leaders` / `龙头决策` 入口
- 内部 tab 至少覆盖：动量总览、轮动回测、板块强弱、资金线索、候选池
- 旧的 `momentum_dashboard`、`momentum_rotation`、`dragon_tiger`、`northbound`、`sectors` 有兼容跳转或明确降级策略

### BL-101 明确专业交易页的产品定位

候选定位：

- paper trading 控制台
- 受控执行控制台
- 研究辅助交易页

目标：

- ✅ 已达成 — 三种模式共存（Paper / 实盘 / 研究），通过模式切换器统一入口
- phase-29-trading-page.md 已更新多模式定位描述
- trading.html 已添加模式切换器 UI

### BL-102 完善 QMT fundamentals 替代策略

现状：

- QMT 不提供基本面数据

目标：

- 明确基本面永远走其他 provider，或补标准降级策略

### BL-103 收敛 phase 归档一致性

现状：

- 个别 phase 文档仍有 `pending` 或只留 commit 号

目标：

- phase 文档统一补齐 commit SHA、测试与风险

### BL-104 收紧 mock 与 real 的状态标识

目标：

- 在 API、页面、状态文档里显式标注 mock / paper / real / managed

### BL-105 数据质量与回测反偏差

目标：

- 建立交易日历、停复牌、涨跌停、复权、除权除息、ST、退市和 survivorship bias 的处理要求
- 明确回测禁止 look-ahead bias 和未来函数
- 为行情、财务、公告、新闻、研报建立数据质量分级和 provenance 记录

## 4. P2

### BL-201 补更清晰的模块需求追踪矩阵

目标：

- 建立“需求 -> 模块 -> 测试 -> phase”映射表

### BL-202 继续清理文档漂移

目标：

- 统一 phase 数量、端点数量、页面数量等口径

### BL-203 细化多入口职责

目标：

- 继续明确 CLI、Streamlit、Flask WebUI 各自职责

### BL-204 为真实交易能力补更明确的验收门槛

目标：

- 把真实执行前置条件写成 checklist，而不是散落在 phase 文档中

### BL-205 组合级风险与绩效归因

目标：

- 增加行业暴露、个股集中度、相关性、Beta、流动性、换手、VaR、压力测试和回撤归因要求
- 将单股/单策略分析升级为组合级投资工作台能力

## 5. 建议执行顺序

建议以 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` 中的 phase 顺序作为后续主线：

1. `Phase 30` / `BL-000`：Live Trading Readiness，先定实盘准入和能力口径
2. `Phase 31` / `BL-105`：Data Quality & Bias Control，补数据可信和回测可信
3. `Phase 32` / `BL-100`：Strategy Lab 模块整合
4. `Phase 33` / `BL-100A`：AI Research Center 模块整合
5. `Phase 34` / `BL-100B`：Market Leaders 龙头相关单入口
6. `Phase 35` / `BL-001` + `BL-002`：Trading & Execution，统一 QMT 能力边界和订单语义
7. `Phase 36` / `BL-205`：Portfolio Risk & Attribution，补组合级风险和绩效归因
8. `Phase 37`：Ops & Audit，统一任务、错误、审计和健康状态
9. `Phase 38` / `BL-203`：Product Navigation Cleanup，清理多入口和体验一致性

## 6. 关联文档

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

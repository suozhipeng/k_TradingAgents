# TradingAgents-Astock 技术需求与模块拆解

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

策略开发的具体规范以 `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` 为准。该规范来自 Hermes `tradingagents-core` skill 的 Section 12 蒸馏内容，覆盖 `StrategyBase -> generate_signals` 生命周期、五类信号模式、三个策略注册点、优化器复合评分、多股票组合策略和 baostock 批量拉取约束。

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

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

# TradingAgents-Astock 技术需求与模块拆解

## 1. 文档目标

本文档从技术实现角度拆解当前项目需求，说明：

- 需要哪些模块
- 模块之间如何衔接
- 每个模块当前大致状态
- 哪些地方仍未完全闭环

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
- 新增专业交易页已入代码，但还未形成新 phase 归档

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
- trade quote 仍为 synthetic quote
- trade state 仍基于 PaperTrader + mock price
- 新交易页尚未补 phase 归档与技术边界说明

## 6. 维护要求

- 新功能必须明确落在哪一层
- 不允许 UI 直接绕过 API/接口层读底层实现细节
- 不允许以 mock 能力冒充 real capability 写入状态文档
- phase 文档必须补 commit SHA 和测试证据

## 7. 关联文档

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

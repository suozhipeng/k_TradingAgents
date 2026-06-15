# Phase 18: Strategy Expansion + Parameter Optimizer

## Metadata

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-15`
- Owner: `Hermes`
- Branch: `xg_dev`
- Commits: `88b57a4`, `a1520d4`, `2c37feb`

## Product objective

扩展策略层从 7 个到 10 个策略，并新增策略参数优化器（网格搜索），支持通过 API 和 WebUI 自动搜索最优参数。

## Scope

### Included

1. **3 个新策略**：
   - `MACDTrendStrategy` — MACD 金叉/死叉趋势跟踪
   - `BollingerBandsReversionStrategy` — 布林带均值回归
   - `GridTradingStrategy` — 固定价格网格交易

2. **策略参数优化器**：
   - `StrategyOptimizer` 类（grid search 遍历参数组合）
   - `_composite_score` 综合评分：35% Sharpe + 30% 收益 − 25% 回撤 + 10% 交易次数
   - 全部 10 策略的默认搜索空间
   - `POST /api/v1/backtest/optimize` API 端点

3. **WebUI 策略优化面板**（`/strategies`）：
   - 策略下拉框（从 `/market/strategies` 自动加载）
   - 股票代码、日期范围输入
   - 开始优化按钮 + 取消支持
   - 排名结果表格：参数、综合评分、Sharpe、收益、回撤、胜率、交易次数

4. **API 注册**：
   - 所有 10 策略注册到 `_STRATEGY_REGISTRY` 和 `AVAILABLE_STRATEGIES`
   - `routes_backtest.py` + `routes_market.py` 更新

### Excluded

- 策略绩效分析图表（Phase 19）
- 实盘策略集成

## Product decisions

1. 网格策略的网格层数、间距、基准价全部可配置
2. 优化器评分使用 composite score 而非单一指标
3. 默认搜索空间覆盖每个策略的 3-27 种组合

## Tests

- 39 策略测试全部通过（含 45 subtests）
- 16 优化器测试全部通过
- Uniform constraints 覆盖全部 10 策略

## Risks

- 网格策略的 `base_price` 使用首日收盘价时，不同日期范围结果不同
- Mock 数据下优化器评分可能为 0（随机游走无信号）

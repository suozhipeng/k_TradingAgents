# A 股策略开发规范

| 更新时间：2026-07-08 |

本文档承接 Hermes `tradingagents-core` skill 的 Section 12 蒸馏内容，用于约束后续 Strategy Lab、回测、优化器和动量轮动相关开发。代码实现仍以仓库当前状态为准；本文提供新增策略和重构策略模块时的工程边界。

## 1. 策略生命周期

标准单标的策略必须继承 `StrategyBase`，并实现统一入口：

```python
generate_signals(data: pd.DataFrame) -> pd.Series
```

约定：

- 输入必须是按时间升序排列的行情数据，至少包含 `close`，按策略需要补充 `open`、`high`、`low`、`volume` 等列。
- 输出必须是与输入索引对齐的整数信号序列：`1` 表示买入或持有多头，`0` 表示空仓或无动作，`-1` 表示卖出或退出。
- 策略内部必须处理预热期 NaN，不允许把 NaN 信号直接交给回测引擎。
- 策略参数必须通过构造参数或配置字典显式声明，不能依赖页面或 API 的隐式默认值。

## 2. 信号生成模式

新增策略优先复用以下五类模式，避免重复发明不可验证的信号结构：

| 模式 | 典型用途 | 约束 |
|---|---|---|
| Crossover | 均线、MACD、价格突破 | 明确快慢线窗口，处理交叉当天和连续持有规则 |
| Deviation | 布林带、均值回归、估值偏离 | 明确偏离阈值、回归退出条件和极端行情保护 |
| Momentum | 龙头、行业轮动、强弱排序 | 明确 lookback、调仓周期、候选池和等权/加权规则 |
| Threshold | RSI、成交量放大、波动率过滤 | 明确阈值、滞回区间和重复触发去抖 |
| Grid | 网格交易、震荡策略 | 明确网格间距、资金分配、止损和趋势失效条件 |

## 3. 注册点

新增或迁移策略时，至少检查三个注册点：

- `tradingagents/astock/execution/__init__.py`：导出策略类，保证包级导入稳定。
- `tradingagents/astock/api/routes_backtest.py` 的 `_STRATEGY_REGISTRY`：保证 API、WebUI 和回测入口可选择该策略。
- `tradingagents/astock/api/routes_market.py` 的 `AVAILABLE_STRATEGIES`：保证市场分析、推荐策略和页面元数据可见。

如果后续 Phase 30 建立统一 Strategy Registry，上述注册点应收敛到单一 registry，再由 API/WebUI 派生展示配置。

## 4. 优化器评分

参数优化默认使用复合评分，避免只追逐收益或交易次数：

```text
score = 0.35 * Sharpe + 0.30 * Return - 0.25 * Drawdown + 0.10 * TradeFrequency
```

落地要求：

- Sharpe、收益、回撤和交易次数必须先做边界归一化，再进入复合评分。
- 最大回撤必须作为惩罚项，不能被高收益完全掩盖。
- 无交易、极低交易次数或数据不足的参数组合不能排在前列。
- 优化结果必须记录参数、得分、核心指标、数据区间、成本模型和 benchmark。

## 5. 多股票组合策略

多股票策略有两种模式：

| 模式 | 适用场景 | 边界 |
|---|---|---|
| Standalone 组合模式 | 动量轮动、行业轮动、候选池排序 | 可不继承 `StrategyBase`，但必须输出组合净值、持仓、调仓记录和 benchmark |
| StrategyBase 兼容模式 | 单标的策略批量运行、组合回测引擎统一调度 | 每只股票独立生成信号，再由组合层处理仓位和风控 |

动量轮动当前更接近 Standalone 组合模式。Phase 30 重构时应把它纳入 Strategy Lab，但不应强行改成单标的 `StrategyBase`。

## 6. 数据拉取规范

baostock 批量拉取必须使用游标模式：

```python
while rs.next():
    row = rs.get_row_data()
```

工程要求：

- 优先批量获取并本地聚合，避免单股票、单日期、单字段循环请求。
- 对远程 provider 失败要保留 provider、symbol、日期范围和错误原因。
- live provider 结果必须通过 `tradingagents/astock/verification_provenance.py` 或运行日志记录验证环境。
- 回测不能直接依赖实时接口，应优先使用 DuckDB/store 或可复现数据快照。

## 7. 已修复但必须防复发的问题

买入逻辑曾出现 `net_cost > cash` 永远为真的风险。新增回测或模拟盘逻辑时必须保留迭代收敛方案：

- 先按现金估算最大可买数量。
- 计算含佣金、印花税、过户费等费用后的 `net_cost`。
- 若 `net_cost > cash`，按费用重新缩小数量并重复校验。
- 最终仍超出现金时必须放弃交易或返回明确错误，不能产生负现金。

## 8. 常见陷阱

- 参数爆炸：网格搜索必须限制组合数，必要时分层搜索或使用 Top N 初筛。
- NaN 预热：指标窗口期产生的 NaN 必须在策略内转成 `0` 或延后信号生效。
- Mock 无趋势：测试数据如果没有趋势或波动，趋势策略和动量策略会出现假阴性。
- 未来函数：策略只能使用当前 bar 及之前数据，不得读取未来收益、未来最高/最低或回测结果。
- 成交约束：涨跌停、停牌、T+1、成交量容量和滑点必须逐步进入统一回测约束。
- 过拟合：优化结果必须展示样本内/样本外、walk-forward 或至少明确标记“未做样本外验证”。

## 9. Phase 30 接入要求

Strategy Lab 重构前，新增策略必须同时更新：

- 本文档。
- `04-dev/PRD.md` 的 Strategy Lab 目标模块。
- `BACKLOG.md` 中 `BL-100` 的完成标准。
- 对应测试：策略信号、回测结果、优化器排序、API registry。

Phase 30 的目标不是增加更多策略，而是把现有策略、回测、优化、绩效、对比和动量轮动收敛到一个可审计的产品/工程模块。

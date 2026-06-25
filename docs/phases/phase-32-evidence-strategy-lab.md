# Phase 32 — Strategy Lab 证据文档

## 策略注册点（32-01）

当前策略注册方式：

| 注册点 | 位置 | 说明 |
|--------|------|------|
| `execution/__init__.py` imports + `__all__` | 隐式 | 所有策略在 `__all__` 中列出，通过包导入注册 |
| `optimizer.py::DEFAULT_SEARCH_SPACES` | 显式 | 优化器搜索空间字典，key = 策略类名 |
| `strategy_registry.py::_STRATEGY_REGISTRY` | **Phase 32 新增** | 显式注册表，包含 category/params/search_space/suitability |

## Strategy Registry schema（32-02）

新增文件：`execution/strategy_registry.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 策略规范名 |
| `category` | string | `trend` / `mean_reversion` / `momentum` / `volatility` / `option` / `grid` / `valuation` |
| `description` | string | 一句话描述 |
| `params_schema` | dict | 参数名 → 默认值 |
| `search_space` | dict | 参数名 → 候选值列表 |
| `suitability` | list[string] | 适用市场条件 |

## Backtest Result schema（32-03）

已在 `backtest_engine.py::BacktestResult` 中定义，Phase 32 新增：

| 字段 | 来源 | 说明 |
|------|------|------|
| `data_assumption` | Phase 31 | 回测数据假设 |
| `data_quality` | Phase 31 | 数据质量标签 |

这些字段使回测结果可被策略对比、绩效归因、AI Research 复用。

## Optimize Result schema（32-04）

已在 `optimizer.py::StrategyOptimizer` 中定义，返回格式为 `list[dict]`，每个 dict 包含：

| 字段 | 说明 |
|------|------|
| `params` | 参数组合 |
| `total_return` | 总收益 |
| `sharpe_ratio` | 夏普比 |
| `max_drawdown` | 最大回撤 |

## Strategy Hub 当前 tab（32-05）

| Tab | 当前入口 | 目标入口 |
|-----|----------|----------|
| Backtest | `route_backtest.py` → API | Strategy Lab |
| Optimize | `optimizer.py` → API | Strategy Lab |
| Strategy | `strategy_base.py` | Strategy Lab |
| Momentum Rotation | `momentum_rotation.py` | Market Leaders |
| Compare | `routes_backtest.py::compare` | Strategy Lab |

## 旧入口迁移策略（32-06）

| 旧入口 | 迁移动作 | 优先级 |
|--------|----------|--------|
| `momentum_rotation.html` | 重定向到 Market Leaders | Phase 34 |
| `strategies.html` standalone | 合并到 Strategy Hub | Phase 38 |
| 各 standalone strategy API | 统一 registry 入口 | Phase 38 |

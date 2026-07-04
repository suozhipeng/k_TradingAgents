# Phase 32 Strategy Lab 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

## 0. 前置依赖

- Phase 31：BacktestDataAssumption schema、DataQualityTag（回测结果必须展示数据假设和质量标签）

## 1. Phase 目标

把策略、回测、优化、绩效、对比和动量轮动收敛为统一 Strategy Lab。要求保留现有策略能力，建立统一 registry、参数 schema、结果 schema 和页面入口。

## 2. 范围

后台模块：

- `tradingagents/astock/execution/strategy_base.py`
- `tradingagents/astock/execution/backtest_engine.py`
- `tradingagents/astock/execution/optimizer.py`
- `tradingagents/astock/execution/batch_backtest.py`
- `tradingagents/astock/execution/momentum_rotation.py`
- `tradingagents/astock/api/routes_backtest.py`
- `tradingagents/astock/api/routes_market.py`

前台模块：

- `strategy_hub.html`
- `strategies.html`
- `momentum_rotation.html`

API：

- `POST /api/v1/backtest/run`
- `GET /api/v1/backtest/results`
- `GET /api/v1/backtest/compare`
- `POST /api/v1/backtest/analyze`
- `POST /api/v1/backtest/optimize`
- `GET /api/v1/market/strategies`
- `POST /api/v1/market/momentum-rotation`

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 32-01 | 搜索所有策略注册点。 | docs；源码只读。 | `execution/__init__.py`、`_STRATEGY_REGISTRY`、`AVAILABLE_STRATEGIES` 不遗漏。 |
| 32-02 | 定义 Strategy Registry schema。 | strategy guide、API contracts。 | name/category/params/search_space/suitability 完整。 |
| 32-03 | 定义 Backtest Result schema。 | data dictionary、API contracts。 | metrics/equity/trades/assumption/benchmark 完整。 |
| 32-04 | 定义 Optimize Result schema。 | API contracts、strategy guide。 | score/top_n/in_sample/out_sample/walk_forward 明确。 |
| 32-05 | 梳理 Strategy Hub 当前 tab。 | WebUI checklist。 | 当前入口和目标入口不遗漏。 |
| 32-06 | 标记旧策略入口迁移策略。 | WebUI spec/checklist。 | keep/redirect/deprecate 结论明确。 |
| 32-07 | 更新 Strategy Lab 效果图。 | progress plan 或 WebUI spec。 | tab 和核心区域清晰。 |
| 32-08 | 如 registry 决策变化，更新 ADR。 | ADR。 | 新 ADR 或引用 ADR-004。 |
| 32-09 | 运行策略测试。 | phase evidence。 | `tests/test_astock_strategies.py -q` 有结果。 |
| 32-10 | 运行优化器测试。 | phase evidence。 | `tests/test_astock_optimizer.py -q` 有结果。 |

## 4. 测试命令

```bash
pytest tests/test_astock_strategies.py -q
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_optimizer.py -q
pytest tests/test_astock_api.py -q
```

## 5. 完成标准

- 新增策略只需注册一次即可被 API、WebUI、优化器识别。
- 回测结果可被策略对比、绩效归因、AI Research 复用。
- 动量轮动归属清晰，不破坏 standalone 组合策略能力。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `../_archived/phase-32-evidence-strategy-lab.md`

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

---
**Commit SHA**: b410074

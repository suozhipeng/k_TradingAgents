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

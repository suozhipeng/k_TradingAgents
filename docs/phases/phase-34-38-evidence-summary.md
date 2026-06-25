# Phase 34-38 — Evidence & Status Summary

## Unified Market Leaders (Phase 34)

| 任务 | 状态 | 说明 |
|------|------|------|
| LeaderPool schema | ✅ | `execution/leader_pool.py` — symbol/name/reason/score/source/refreshed_at/entry_reason/exit_reason 全部字段 |
| Sidebar consolidation | ✅ | 5 个旧入口（dragon_tiger/sectors/northbound/momentum_dashboard/momentum_rotation）→ 1 个 Market Leaders |
| Route `/market_leaders` | ✅ | Flask route + `market_leaders.html` 统一页面，5 个 tab（龙头/板块/北向/龙虎榜/动量轮动） |
| Old routes preserved | ✅ | `/dragon_tiger`、`/sectors`、`/northbound`、`/momentum_dashboard`、`/momentum_rotation` 仍可访问 |
| Fallback semantic (data source) | ✅ | LeaderPoolEntry 已有 `source` 字段标注数据来源 |

## Trading Execution Control (Phase 35)

| Schema | 文件 | 状态 |
|--------|------|------|
| `Order` | `phase33_37_schemas.py` | ✅ order_id/broker_order_id/mode/symbol/side/quantity/price/status/risk_status/confirmation/audit |
| `Fill` | `phase33_37_schemas.py` | ✅ fill_id/order_id/symbol/side/quantity/price/fees/timestamp |
| `Position` | `phase33_37_schemas.py` | ✅ symbol/quantity/avg_cost/current_price/market_value/pnl/pnl_pct |
| `Reconciliation` | `phase33_37_schemas.py` | ✅ local/external position/cost + matched/discrepancy |

## Portfolio Risk & Attribution (Phase 36)

| Schema | 文件 | 状态 |
|--------|------|------|
| `Portfolio` | `phase33_37_schemas.py` | ✅ portfolio_id/holdings/cash/nav/pnl_total |
| `RiskExposure` | `phase33_37_schemas.py` | ✅ industry_concentration/top_holding_pct/beta/liquidity/var_95/max_drawdown/stress_loss |
| `Attribution` | `phase33_37_schemas.py` | ✅ benchmark_return/selection_effect/timing_effect/cost_impact/slippage/residual |

## Ops & Audit Center (Phase 37)

| Schema | 文件 | 状态 |
|--------|------|------|
| `TaskRun` | `phase33_37_schemas.py` | ✅ task_id/task_type/status/progress/started_at/finished_at/error/result |
| `AuditEvent` | `phase33_37_schemas.py` | ✅ event_id/actor/action/input_snapshot/output_snapshot/model/confirmation/confirmed_by/created_at |
| `TaskType` | `phase33_37_schemas.py` | ✅ DATA_REFRESH/RESEARCH/BACKTEST/REPORT/TRADE |

## Navigation Cleanup (Phase 38)

| 模块 | 入口 | 状态 |
|------|------|------|
| Trading | `/` | ✅ 保留 |
| Dashboard | `/dashboard` | ✅ 保留 |
| Research | `/research` | ✅ 保留 |
| Strategy Hub | `/strategy_hub` | ✅ 保留 |
| Strategies | `/strategies` | ✅ 保留 |
| Paper Trading | `/paper` | ✅ 保留 |
| QMT | `/qmt` | ✅ 保留 |
| Risk | `/risk` | ✅ 保留 |
| Screener | `/screener` | ✅ 保留 |
| **Market Leaders** | **`/market_leaders`** | **✅ New — consolidated** |
| AI Agent | `/ai_agent` | ✅ 保留 |
| Settings | `/settings` | ✅ 保留 |
| Dragon Tiger | `/dragon_tiger` | ✅ Legacy — 保留但不在 sidebar |
| Sectors | `/sectors` | ✅ Legacy — 保留但不在 sidebar |
| North-bound | `/northbound` | ✅ Legacy — 保留但不在 sidebar |
| Momentum Dashboard | `/momentum_dashboard` | ✅ Legacy — 保留但不在 sidebar |
| Momentum Rotation | `/momentum_rotation` | ✅ Legacy — 保留但不在 sidebar |

## Test Status

```
pytest tests/test_astock_*.py -q
→ 264 passed, 4 skipped, 0 failed
```

## Schema Export Status

所有 Phase 33-38 schemas 已从 `tradingagents/astock/__init__.py` 导出。

# Phase 35 — Trading Execution Control

## Order schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | string | 本地订单 ID |
| `broker_order_id` | string/null | 券商订单 ID |
| `mode` | enum | paper/managed/live-ready |
| `symbol` | string | 标的 |
| `side` | enum | buy/sell |
| `quantity` | float | 数量 |
| `price` | float | 价格 |
| `status` | enum | created/submitted/confirmed/partial_filled/filled/cancelled/rejected/expired/error |
| `risk_status` | string | pending/allowed/blocked |
| `confirmation_status` | string | not_required/pending/confirmed/rejected |
| `audit_event_id` | string | 审计引用 |

## Fill schema — 支持部分成交

| 字段 | 说明 |
|------|------|
| `fill_id` | 成交 ID |
| `order_id` | 订单 ID |
| `quantity` | 本次成交数量 |
| `price` | 成交价 |
| `fees` | 手续费 |

## Position schema — paper/managed 共用

| 字段 | 说明 |
|------|------|
| `symbol` | 标的 |
| `quantity` | 持仓数量 |
| `avg_cost` | 平均成本 |
| `current_price` | 当前价 |
| `market_value` | 市值 |
| `pnl` | 盈亏 |
| `pnl_pct` | 盈亏百分比 |

## Reconciliation schema — 本地状态 vs 外部回报

| 字段 | 说明 |
|------|------|
| `matched` | 是否一致 |
| `discrepancy` | 差异值 |

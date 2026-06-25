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

## 实装接线 (2026-06-25)

### 35-01 PaperTrader 返回 Order/Fill
- `paper_trader.py`: `place_order()`, `_place_buy_order()`, `_place_sell_order()` 返回值从 dict → `Order` Pydantic
- 自动生成 order_id（格式: `po-{timestamp}-{hash4}`）
- Fill 对象嵌入 Order（支持部分成交结构）
- 向后兼容: `execute_cycle()` 路径不变，仍使用 dict trades

### 35-02 Trade API 使用 Order schema
- `routes_trade.py`: `POST /api/v1/trade/order` 返回 `Order.model_dump()` JSON
- `trade_state()` 返回的 positions 增加 `quantity` 字段

### 35-03 RiskGate 订单流接入
- `routes_trade.py`: `place_order()` 前必经 `RiskGate.check()` 预检
- 被阻塞时返回 403 + `blocked_by` 列表

### 35-04 Trading 页面 capability 标注
- `trading.html`: 已有 mode 切换器 (paper/live/research)
- 状态标签显式标注 mode 和能力

### 35-05 测试
- `test_astock_paper_trader.py`: 24 passed (已适配 Order 属性访问)
- `test_astock_adjustment.py`: 12 passed
- `test_suspension.py`: 55 passed
- `test_astock_backtest.py`: 26 passed

### 范围排除
- QMT 桥接 (`qmt_bridge.py`, `qmt_execution.py`) 保留接口占位，不纳入真实数据源
- 见 `.hermes/backlog.md` vNext 项 QMT-1/QMT-2

# Phase 30 交易 API 字段清单

生成时间：2026-06-25 | 用于 Phase 30-01 验收

## 1. POST /api/v1/trade/order

来源：`tradingagents/astock/api/routes_trade.py`（`place_order`）

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | A股标的代码（如 `600519.SH`） |
| `side` | enum | 是 | `buy` / `sell` |
| `price` | number | 是 | 限价/市价 |
| `quantity` | int | 是 | 股数 |

### 响应字段（200 OK）

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 固定 `"ok"` |
| `order` | object | 订单结果 |
| `order.filled` | bool | 是否成交 |
| `order.symbol` | string | 标的 |
| `order.side` | string | `buy` / `sell` |
| `order.price` | float | 成交价 |
| `order.quantity` | int | 成交数量 |
| `order.total` | float | 总金额 |
| `order.fees` | float | 手续费 |
| `order.cash_remaining` | float | 剩余现金 |
| `order.message` | string | 人类可读描述 |

### 响应字段（400/500）

| 字段 | 类型 | 说明 |
|------|------|------|
| `error` | string | 错误描述 |
| `status` | int | HTTP 状态码 |

### 缺失项

- ❌ 无 `meta.capability` 能力等级标记
- ❌ 无 `meta.request_id` 追踪 ID
- ❌ 无 `risk_status` 风控状态
- ❌ 无 `confirmation_status` 确认状态
- ❌ 无 `audit_event_id` 审计引用
- ❌ 响应无 `success`/`data`/`error`/`meta` 标准 envelope

---

## 2. GET /api/v1/trade/quote

来源：`routes_trade.py`（`get_quote`）

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | A股标的代码 |

### 响应字段（200 OK）

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 标的 |
| `last_price` | float | 最新价 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `change` | float | 涨跌额 |
| `change_pct` | float | 涨跌幅（%） |
| `volume` | int | 成交量 |
| `bid` | float | 买一价 |
| `ask` | float | 卖一价 |
| `timestamp` | string | ISO 时间戳 |
| `source` | string | 数据来源：`live` / `cache` |

### 响应字段（503）

| 字段 | 类型 | 说明 |
|------|------|------|
| `error` | string | `"quotes unavailable"` |
| `symbol` | string | 标的 |
| `last_price` | int | 固定 `0` |
| `source` | string | `"none"` |

### 缺失项

- ❌ 无 `meta.capability`
- ❌ 无 `meta.request_id`
- ❌ 无 `freshness` 或 `quality` 数据质量标记
- ❌ 无 `data_snapshot_id`

---

## 3. GET /api/v1/trade/state

来源：`routes_trade.py`（`trade_state`）

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `cash` | float | 现金余额 |
| `total_value` | float | 总资产 |
| `pnl` | float | 累计盈亏 |
| `positions` | array | 持仓列表 |
| `positions[].symbol` | string | 标的 |
| `positions[].shares` | float | 持仓数量 |
| `positions[].avg_cost` | float | 平均成本 |
| `positions[].current_price` | float | 当前价 |
| `positions[].market_value` | float | 市值 |
| `positions[].pnl` | float | 单股盈亏 |
| `positions[].pnl_pct` | float | 盈亏百分比 |
| `trade_count` | int | 历史成交数 |

### 缺失项

- ❌ 无 `execution_signal` / `decision_scope`
- ❌ 无 `meta.capability`
- ❌ 无 `trading_mode` 区分 paper/managed/live-ready
- ❌ `last_updated` 字段缺失

---

## 4. POST /api/v1/paper/cycle

来源：`routes_paper.py`（`paper_cycle`）

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `signals` | dict[string, float] | 是 | symbol → signal（1/-1/0） |
| `prices` | dict[string, float] | 是 | symbol → last price |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `positions` | dict | symbol → shares |
| `cash` | float | 现金余额 |
| `total_value` | float | 总资产 |
| `pnl` | float | 累计盈亏 |
| `trade_count` | int | 成交笔数 |
| `last_updated` | string | ISO 时间戳 |

### 缺失项

- ❌ 无 `execution_signal`（下层 `PaperTradeState` 有但未暴露）
- ❌ 无 `decision_scope`
- ❌ 无 `meta.capability`

---

## 5. GET /api/v1/paper/state

来源：`routes_paper.py`（`paper_state`）

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `positions` | dict | symbol → shares |
| `cash` | float | 现金余额 |
| `total_value` | float | 总资产 |
| `pnl` | float | 累计盈亏 |
| `trade_count` | int | 成交笔数 |
| `last_updated` | string | ISO 时间戳 |
| `execution_signal` | string | `"ResearchOnly"` |
| `decision_scope` | string | `"paper_trading_only"` |

### 缺失项

- ❌ 无 `meta.capability`
- ❌ 无 `trading_mode`

---

## 6. GET /api/v1/paper/trades

来源：`routes_paper.py`（`paper_trades`）

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `trades` | array | 历史成交 |
| `trades[].symbol` | string | 标的 |
| `trades[].type` | string | `buy` / `sell` |
| `trades[].price` | float | 成交价 |
| `trades[].shares` | float | 数量 |
| `trades[].fees` | float | 手续费 |
| `trades[].actionable` | bool | 固定 `false` |
| `trades[].decision_scope` | string | `paper_trading_only` |
| `trades[].timestamp` | string | ISO 时间戳 |
| `trades[].pnl` | float | 仅 sell 有 |

### 缺失项

- ❌ 无 `meta.capability`
- ❌ 无 `order_id` / `trade_id`

---

## 7. GET /api/v1/qmt/health

来源：`routes_qmt.py`（`qmt_health`）

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `real` | string | 否 | `"1"` 尝试真实连接检查 |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `healthy` | bool | 是否健康 |
| `mock_mode` | bool | 是否 mock |
| `host` | string | 主机 |
| `port` | int | 端口 |
| `real_healthy` | bool/null | 真实连接结果 |
| `real_error` | string/null | 真实连接错误 |

---

## 8. GET /api/v1/qmt/positions

来源：`routes_qmt.py`（`qmt_positions`）

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `positions` | array | 持仓列表 |
| `mock_mode` | bool | 是否 mock |

---

## 9. GET /api/v1/qmt/orders

来源：`routes_qmt.py`（`qmt_orders`）

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `orders` | array | 账户信息 |
| `orders[].account_id` | string | 账户 ID |
| `orders[].total_asset` | number | 总资产 |
| `orders[].cash` | number | 现金 |
| `orders[].market_value` | number | 市值 |
| `orders[].frozen_cash` | number | 冻结资金 |
| `orders[].available_cash` | number | 可用资金 |
| `mock_mode` | bool | 是否 mock |

---

## 总结：Phase 30 上下文

所有交易/paper/qmt API 当前都不具备：

1. **能力等级标记** ── 无 `meta.capability` 字段
2. **标准响应 envelope** ── `success/data/error/meta` 结构未采用
3. **风控状态** ── trade/order 未暴露 `risk_status`
4. **确认状态** ── 无 human-in-the-loop 确认机制
5. **审计引用** ── 无 `audit_event_id`
6. **数据语义** ── paper 状态未充分标注 ResearchOnly 语义

这些缺口将在 Phase 30-02 ~ 30-08 逐步填补，为 Phase 35（Trading & Execution）建立基础。

---
**Commit SHA**: b410074

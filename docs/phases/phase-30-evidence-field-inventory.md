# Phase 30 交易 API 字段清单

生成时间：2026-06-26 | 用于 Phase 30-01 验收

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

### 响应字段（降级成功，仍返回 200）

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 标的 |
| `name` | string | 合成名称，通常回落为 symbol |
| `last_price` | float | 确定性 mock 价格 |
| `open` | float | mock 开盘价 |
| `high` | float | mock 最高价 |
| `low` | float | mock 最低价 |
| `change` | float | mock 涨跌额 |
| `change_pct` | float | mock 涨跌幅 |
| `volume` | int | mock 成交量 |
| `bid` | float | mock 买一 |
| `ask` | float | mock 卖一 |
| `timestamp` | string | ISO 时间戳 |
| `source` | string | `"mock"` |

### 缺失项

- ❌ 无 `meta.capability`
- ❌ 无 `meta.request_id`
- ❌ 无 `freshness` 或 `quality` 数据质量标记
- ❌ 无 `data_snapshot_id`
- ⚠️ 当前在实时源和缓存都失败时不会返回 503，而是回落到 synthetic mock quote

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
6. **数据语义** ── `trade/state` 仍未暴露 `execution_signal` / `decision_scope`，paper 语义未完全透传
7. **降级语义** ── `trade/quote` 在失败时回落为 `source=mock` 的 200 响应，而非错误态

这些缺口将在 Phase 30-02 ~ 30-08 逐步填补，为 Phase 35（Trading & Execution）建立基础。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-30-evidence-paper-semantics.md`

# Phase 30 — Paper Trading 语义说明

## 概述

当前 TradingAgents 的 "Trading" 页面和 API 本质上是 **paper trading（模拟交易）**，不是实盘。所有交易操作使用虚拟资金，不涉及真实券商或实盘订单。

## PaperTrader 语义

| 属性 | 值 | 说明 |
|------|-----|------|
| `actionable` | `false` | 所有成交均为 advisory，不可用于实盘执行 |
| `execution_signal` | `"ResearchOnly"` | 固定值，表示仅用于研究目的 |
| `decision_scope` | `"paper_trading_only"` | 仅限于模拟交易上下文 |
| `initial_cash` | 100,000（默认） | 虚拟初始资金 |
| 数据源 | EastMoney / Sina | 实时行情来自公共市场数据，不代表券商报价 |
| 风控 | RiskGate | 模拟风控检查，不连接真实风控系统 |

## 代码证据

- `paper_trader.py:PaperTradeState.execution_signal` — 固定 `"ResearchOnly"`
- `paper_trader.py:PaperTradeState.decision_scope` — 固定 `"paper_trading_only"`
- `paper_trader.py` 所有 trade 记录携带 `"actionable": false`（`_execute_buy`、`_execute_sell`、`_place_buy_order`、`_place_sell_order`）
- `risk_gate.py:RiskGate.check` — 当 `proposal.get("actionable", False)` 为真时阻止

## WebUI 页面语义

- **Trading 页面** — 依赖 `PaperTrader` 实例，所有下单是虚拟成交。页面应标注 **Paper Trading（模拟交易）** 而非 Trading。
- **Paper 页面** — 与 Trading 页面共享同一 `PaperTrader` 实例，功能重复。后续 Phase 35 应合并或重定向。
- **Risk 页面** — 显示 RiskGate 检查结果，所有 `execution_signal` 为 ResearchOnly。
- **QMT 页面** — 当前为 mock 模式（`use_mock=True`），不连接真实 QMT 环境。

## API 语义

| API | 当前语义 | 正确标注 |
|-----|----------|----------|
| `POST /api/v1/trade/order` | paper order（虚拟） | `paper` |
| `GET /api/v1/trade/state` | paper state（虚拟） | `paper` |
| `GET /api/v1/trade/quote` | 真实市场行情 | `research` |
| `POST /api/v1/paper/cycle` | paper cycle | `paper` |
| `GET /api/v1/paper/state` | paper state | `paper` |
| `GET /api/v1/paper/trades` | paper trades | `paper` |
| `GET /api/v1/qmt/health` | mock health check | `managed` (mock) |
| `GET /api/v1/qmt/positions` | mock positions | `managed` (mock) |
| `GET /api/v1/qmt/orders` | mock orders | `managed` (mock) |

## 风险披露

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| 误标 live-ready | 页面显示 "Trading" 可能让用户误以为可实盘 | Phase 30: 增加能力等级标注 |
| ResearchOnly 混用 | paper 状态被当成真实账户状态 | 所有响应包含 `execution_signal` |
| 数据延迟 | 行情数据可能有5-30秒延迟 | 显示 `source` 和 `timestamp` |
| mock 数据误导 | QMT mock 数据可能被当成真实持仓 | 页面标注 `mock_mode: true` |

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-30-live-trading-readiness.md`

# Phase 30 Live Trading Readiness 需求与证据归档

| 状态：完成（文档口径与证据归档） | 更新时间：2026-06-26 |

## 0. 前置依赖

- 无前置 phase 依赖。Phase 30 是所有后续 phase 的基础（TradingMode enum、capability 标注、kill switch 定义）。

## 1. 结论

Phase 30 已完成的内容是“先定口径”：

- 明确 `research / paper / managed / live-ready` 的定义和准入边界。
- 明确当前 `/trade/order`、`/trade/state`、`/paper/*` 均仍属于 `paper` 语义。
- 明确当前 QMT 相关接口只能按 `managed` 的 mock/read-only 口径描述。
- 明确 `live-ready` 是准入状态，不是默认可执行模式。

Phase 30 没有完成、也不声称完成的内容：

- 交易 API 全量升级为标准 `success/data/error/meta` envelope。
- `/trade/order` 支持真实 managed 或 live-ready 下单。
- 券商账户/委托/成交/回报 reconciliation 闭环。
- 自动实盘生产运行。

## 2. Phase 目标

把当前 trading / paper / qmt / risk 能力从“页面和接口已存在”收敛为可验收的交易能力边界。当前 phase 不实现完整自动实盘，不把 QMT 纳入真实数据源要求，只定义 research / paper / managed / live-ready 的准入、API 标注、页面提示和测试证据。

## 3. 范围

后台模块：

- `tradingagents/astock/api/routes_trade.py`
- `tradingagents/astock/api/routes_paper.py`
- `tradingagents/astock/api/routes_qmt.py`
- `tradingagents/astock/execution/paper_trader.py`
- `tradingagents/astock/execution/risk_gate.py`

前台模块：

- `tradingagents/astock/web/templates/trading.html`
- `tradingagents/astock/web/templates/paper.html`
- `tradingagents/astock/web/templates/risk.html`
- `tradingagents/astock/web/templates/qmt.html`

API：

- `POST /api/v1/trade/order`
- `GET /api/v1/trade/quote`
- `GET /api/v1/trade/state`
- `POST /api/v1/paper/cycle`
- `GET /api/v1/paper/state`
- `GET /api/v1/paper/trades`
- `GET /api/v1/qmt/health`
- `GET /api/v1/qmt/positions`
- `GET /api/v1/qmt/orders`

真实数据源：

- `trade/quote` 使用 Sina -> EastMoney -> cache -> synthetic mock。
- paper/trade state 使用 PaperTrader 状态，不代表真实账户。
- QMT 相关真实数据不纳入本文真实数据源要求。

## 4. 任务与完成情况

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 30-01 | 搜索 `/trade`、`/paper`、`/qmt` API 当前返回字段，输出字段清单。 | docs only；源码只读。 | 已完成；见 `phase-30-evidence-field-inventory.md`。 |
| 30-02 | 为交易 API 标注 `research/paper/managed/live-ready/mock` capability。 | `01-arch/API.md`、本 phase 文档；代码 meta 变更需单独批准。 | 已完成文档口径；代码 meta 未在本 phase 强制落地。 |
| 30-03 | 梳理 `trade_state` paper 语义。 | runbook、风险披露、页面验收清单。 | 已完成；见 `phase-30-evidence-paper-semantics.md`。 |
| 30-04 | 定义 `TradingMode` enum。 | API contracts、runbook。 | 已完成文档 schema。 |
| 30-05 | 定义 `ExecutionCapability` schema。 | API contracts、runbook。 | 已完成文档 schema。 |
| 30-06 | 绘制订单生命周期状态机。 | runbook、本 phase 文档。 | 已完成；见 `phase-30-evidence-order-lifecycle.md`。 |
| 30-07 | 梳理 Risk Gate reason code。 | runbook、risk disclosure、test plan。 | 已完成；基于 `risk_gate.py` 当前枚举核对。 |
| 30-08 | 定义 kill switch 行为。 | runbook、risk disclosure。 | 已完成文档行为定义。 |
| 30-09 | 更新交易页页面验收清单。 | WebUI page acceptance checklist。 | 已完成文档核对；遗留 UI 标题/模式命名漂移已记录。 |
| 30-10 | 运行 paper/risk 最小验收并记录。 | phase evidence only。 | 已完成；见下方测试结果。 |

## 5. 测试结果

```bash
pytest tests/test_astock_paper_trader.py -q  -> 24 passed
pytest tests/test_astock_execution_risk_gate.py -q  -> 10 passed
pytest tests/test_astock_api.py -q  -> 47 passed
```

## 6. 证据文件

- `phase-30-evidence-field-inventory.md`
- `phase-30-evidence-paper-semantics.md`
- `phase-30-evidence-order-lifecycle.md`
- `phase-30-evidence-acceptance-checklist.md`

## 7. 完成标准判定

| 验收项 | 判定 | 说明 |
|---|---|---|
| 能力口径已定义 | 完成 | 文档已明确 research/paper/managed/live-ready 边界 |
| 当前真实落点已说清 | 完成 | `/trade/order` 与 `/trade/state` 明确仍属 paper |
| QMT 受控执行未被误写成自动实盘 | 完成 | 当前只按 managed mock/read-only 描述 |
| API 标准 envelope 已全部落代码 | 未纳入本 phase 完成条件 | 留给后续 phase/代码改造 |
| 真实券商闭环已完成 | 未完成 | 留给 Phase 35+ |

## 8. 风险与后续

- Trading 页面仍保留 `live` 按钮与“实盘”字样，但后端真实执行链路未切到 live-ready。
- `/trade/order` 当前忽略请求中的 `mode`，固定走 PaperTrader；这必须继续在页面/API 文档中明确。
- QMT `orders` 当前更接近账户资产占位信息，后续需在 Phase 35 继续收口语义。

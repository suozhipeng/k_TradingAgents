# Phase 35 Trading & Execution 需求与 Hermes 任务包

| 状态：done-with-exclusions | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 30：TradingMode enum、capability 标注、kill switch 定义（订单/交易页必须复用 Phase 30 的能力标签）
- Phase 34：LeaderPool schema（龙头交易上下文需要候选池信息）

## 1. Phase 目标

在 Phase 30 能力边界基础上，补订单、成交、持仓、reconciliation、风控前置门和交易页闭环。当前 phase 仍不默认自动实盘。

## 2. 范围

后台模块：

- `routes_trade.py`
- `routes_paper.py`
- `paper_trader.py`
- `risk_gate.py`
- `qmt_execution.py` 仅限能力边界，不纳入真实数据源要求

前台模块：

- `trading.html`
- `paper.html`
- `risk.html`

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 35-01 | 定义 Order schema。 | API contracts、runbook。 | 状态完整，兼容 paper/managed。 |
| 35-02 | 定义 Fill schema。 | API contracts、runbook。 | 支持部分成交。 |
| 35-03 | 定义 Position schema。 | API contracts、data dictionary。 | paper/managed 可共用。 |
| 35-04 | 定义 Reconciliation schema。 | runbook、API contracts。 | 本地状态 vs 外部回报可表达。 |
| 35-05 | 梳理 trade/order 当前行为。 | runbook、risk disclosure。 | 不误标 live-ready。 |
| 35-06 | 梳理 risk gate 前置条件。 | runbook、test plan。 | 下单前阻断条件明确。 |
| 35-07 | 更新 Trading 效果图。 | progress plan / WebUI spec。 | capability visible。 |
| 35-08 | 更新 runbook checklist。 | runbook。 | live-ready 前置条件完整。 |
| 35-09 | 运行 paper/risk 测试。 | phase evidence。 | paper/risk tests 有结果。 |
| 35-10 | 记录 QMT 真实数据范围排除。 | scope register/runbook。 | QMT 不纳入真实数据源要求。 |

## 4. 测试命令

```bash
pytest tests/test_astock_paper_trader.py -q
pytest tests/test_astock_execution_risk_gate.py -q
pytest tests/test_astock_qmt_execution.py -q
```
---
**Commit SHA**: `9c56dac` (Phase 35 Trading Execution initial commit), incremental in `e33b362`

## 5. 完成标准

- Order/Fill/Position/Reconciliation schema 明确。
- Trading 页面和 API 统一显示 capability。
- 风控前置门有 reason code 和审计引用。

### 排除项（明确不处理）

以下能力因产品定位调整（详见 `../BACKLOG.md` §1 "实盘交易降级为远期探索"）标记为 P3 暂不处理，不影响本 phase 的 done-with-exclusions 状态：

- 真实券商账户/委托/成交/回报 reconciliation
- `/qmt/orders` 从 mock 升级为真实 QMT 订单查询
- 自动实盘生产运行

### 完成标准判定

| 验收项 | 判定 | 说明 |
|--------|------|------|
| Order/Fill/Position/Reconciliation schema 已落地 | ✅ 完成 | `tradingagents/astock/schemas/trading_execution.py` 含全部 4 个 Pydantic schema |
| PaperTrader 返回 Order/Fill | ✅ 完成 | `paper_trader.py` `place_order()` 返回 Order Pydantic |
| Trade API 使用 Order schema | ✅ 完成 | `routes_trade.py` `POST /trade/order` 返回 Order JSON |
| RiskGate 订单流接入 | ✅ 完成 | `routes_trade.py` 下单前必经 `RiskGate.check()` 预检，拒绝时返回 403 + blocked_by |
| Trading 页面 mode 切换器 | ✅ 完成 | `trading.html` 含 paper/live/research 模式切换 |
| 真实券商 reconciliation | 🚫 排除 | P3 暂不处理（产品定位非实盘） |
| QMT real orders | 🚫 排除 | P3 暂不处理（仅保留接口占位） |

---
**Commit SHA**: b410074


---

> 以下内容合并自 `../_archived/phase-35-evidence-trading-execution.md`

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
- `trading.html`: 已有 mode 切换器 (paper/managed/research)，managed 当前阻断真实券商下单
- 状态标签显式标注 mode 和能力

### 35-05 测试
- `test_astock_paper_trader.py`: 24 passed (已适配 Order 属性访问)
- `test_astock_adjustment.py`: 12 passed
- `test_suspension.py`: 55 passed
- `test_astock_backtest.py`: 26 passed

### 范围排除
- QMT 桥接 (`qmt_bridge.py`, `qmt_execution.py`) 保留接口占位，不纳入真实数据源
- 见 `../.hermes/backlog.md` vNext 项 QMT-1/QMT-2

---
**Commit SHA**: b410074

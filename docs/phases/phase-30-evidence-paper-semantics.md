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

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
| 30-02 | 为交易 API 标注 `research/paper/managed/live-ready/mock` capability。 | `docs/ASTOCK_API_CONTRACTS.md`、本 phase 文档；代码 meta 变更需单独批准。 | 已完成文档口径；代码 meta 未在本 phase 强制落地。 |
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

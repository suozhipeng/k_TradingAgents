# Phase 30 Live Trading Readiness 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

## 1. Phase 目标

把当前 trading / paper / qmt / risk 能力从“页面和接口已存在”收敛为可验收的交易能力边界。当前 phase 不实现完整自动实盘，不把 QMT 纳入真实数据源要求，只定义 research / paper / managed / live-ready 的准入、API 标注、页面提示和测试证据。

## 2. 范围

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

- `trade/quote` 使用 Sina -> EastMoney -> cache。
- paper/trade state 使用 PaperTrader 状态，不代表真实账户。
- QMT 相关真实数据不纳入本文真实数据源要求。

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 30-01 | 搜索 `/trade`、`/paper`、`/qmt` API 当前返回字段，输出字段清单。 | docs only；源码只读。 | 字段清单覆盖所有交易相关 endpoint。 |
| 30-02 | 为交易 API 标注 `research/paper/managed/live-ready/mock` capability。 | `docs/ASTOCK_API_CONTRACTS.md`、本 phase 文档；代码 meta 变更需单独批准。 | paper/mock 不被描述为 real。 |
| 30-03 | 梳理 `trade_state` paper 语义。 | runbook、风险披露、页面验收清单。 | 明确非真实账户状态。 |
| 30-04 | 定义 `TradingMode` enum。 | API contracts、runbook。 | 包含 research/paper/managed/live-ready。 |
| 30-05 | 定义 `ExecutionCapability` schema。 | API contracts、runbook。 | 可被 API 与页面复用。 |
| 30-06 | 绘制订单生命周期状态机。 | runbook、本 phase 文档。 | 覆盖 created/submitted/confirmed/partial_filled/filled/cancelled/rejected/expired/error。 |
| 30-07 | 梳理 Risk Gate reason code。 | runbook、risk disclosure、test plan。 | 风控拦截 reason 可展示给前端。 |
| 30-08 | 定义 kill switch 行为。 | runbook、risk disclosure。 | kill switch 激活后默认阻断后续交易。 |
| 30-09 | 更新交易页页面验收清单。 | WebUI page acceptance checklist。 | 要求 success/empty/error/degraded/capability 截图。 |
| 30-10 | 运行 paper/risk 最小验收并记录。 | phase evidence only。 | `tests/test_astock_paper_trader.py -q` 和必要 risk tests 有结果记录。 |

## 4. 测试命令

```bash
pytest tests/test_astock_paper_trader.py -q
pytest tests/test_astock_execution_risk_gate.py -q
pytest tests/test_astock_api.py -q
```

## 5. 完成标准

- 所有交易相关 API 有 capability。
- paper、managed、live-ready 在页面和 API 中不混淆。
- live-ready checklist 明确但不声称已完成完整实盘生产。
- Phase 证据回填追踪矩阵、风险登记表和必要 ADR。

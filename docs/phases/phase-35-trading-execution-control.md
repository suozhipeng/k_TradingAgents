# Phase 35 Trading & Execution 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

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

## 5. 完成标准

- Order/Fill/Position/Reconciliation schema 明确。
- Trading 页面和 API 统一显示 capability。
- 风控前置门有 reason code 和审计引用。

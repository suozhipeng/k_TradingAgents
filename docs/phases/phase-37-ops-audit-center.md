# Phase 37 Ops & Audit Center 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

## 1. Phase 目标

统一数据刷新、回测、AI research、报告生成、交易动作的任务和审计记录，形成 Ops & Audit Center。

## 2. 范围

后台模块：

- `routes_sse.py`
- `execution/event_bus.py`
- `routes_dashboard.py`
- `routes_data_health.py`
- future task/audit store

前台模块：

- `data_health.html`
- future `ops_audit.html`
- Dashboard 任务摘要

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 37-01 | 定义 TaskRun schema。 | API contracts、metrics/Ops。 | type/status/start/end/error 字段明确。 |
| 37-02 | 定义 AuditEvent schema。 | API contracts、data dictionary。 | actor/input/output/snapshot/model/confirmation 明确。 |
| 37-03 | 梳理 SSE event 当前字段。 | metrics/Ops、release/change。 | 可迁移到 TaskRun。 |
| 37-04 | 梳理 data refresh 任务。 | metrics/Ops。 | 可追踪。 |
| 37-05 | 梳理 backtest 任务。 | metrics/Ops。 | 可追踪。 |
| 37-06 | 梳理 AI research 任务。 | metrics/Ops、model governance。 | 可追踪。 |
| 37-07 | 画 Ops Dashboard 效果图。 | progress plan / WebUI spec。 | 任务/错误/健康三区明确。 |
| 37-08 | 更新 metrics/Ops 文档。 | metrics/Ops。 | 指标可验收。 |
| 37-09 | 运行 SSE 测试。 | phase evidence。 | `tests/test_astock_sse.py -q` 有结果。 |
| 37-10 | 更新风险登记表。 | risk register。 | R-009/R-005 状态更新。 |

## 4. 测试命令

```bash
pytest tests/test_astock_sse.py -q
pytest tests/test_astock_api.py -q
pytest tests/test_astock_web.py -q
```

## 5. 完成标准

- TaskRun 和 AuditEvent schema 明确。
- Ops 页面能回答任务、错误、provider、数据、模型状态。
- 关键动作可追溯。

# Phase 37 — Ops & Audit Center

## TaskRun schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `task_type` | enum | data_refresh/research/backtest/report/trade |
| `status` | string | queued/running/success/failed/cancelled |
| `progress` | float | 0-100 |
| `started_at` | string/null | 开始时间 |
| `finished_at` | string/null | 结束时间 |
| `error` | dict/null | 错误信息 |
| `result` | dict/null | 执行结果 |

## AuditEvent schema

| 字段 | 说明 |
|------|------|
| `event_id` | 事件 ID |
| `actor` | 执行者（user/system/strategy） |
| `action` | 动作描述 |
| `input_snapshot` | 输入快照 |
| `output_snapshot` | 输出快照 |
| `model` | 使用模型 |
| `confirmation_required` | 是否需要确认 |
| `confirmed_by` | 确认人 |

## 完成标准

- TaskRun 和 AuditEvent schema 明确 ✅
- 关键动作可追溯 ✅

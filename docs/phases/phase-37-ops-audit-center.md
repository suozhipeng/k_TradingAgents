# Phase 37 Ops & Audit Center 需求与 Hermes 任务包

| 状态：完成 | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 30-36：所有前述 Phase 的 schema 和 API（TaskRun/AuditEvent 覆盖全部模块：数据刷新、回测、AI research、报告生成、交易动作）

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
---
**Commit SHA**: `3057979` (Phase 37 SSE standardization), incremental in `e33b362`

## 5. 完成标准

- TaskRun 和 AuditEvent schema 明确。
- Ops 页面能回答任务、错误、provider、数据、模型状态。
- 关键动作可追溯。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `../_archived/phase-37-evidence-ops-audit.md`

# Phase 37 — Ops & Audit Center (Evidence)

## 代码实装

### TaskRun/AuditEvent schema
- **文件**: `tradingagents/astock/schemas/ops_audit.py`
- **类**: TaskRun, AuditEvent, TaskType (Pydantic + Enum)
- **Commit**: `5c828f7`

### AuditStore 持久化层
- **文件**: `tradingagents/astock/execution/audit_store.py` (362 lines)
- **架构**: 内存字典 + 可选 DuckDB 持久化（INTO/ON CONFLICT）
- **API**:
  - `record_task()` / `update_task()` / `get_task()` / `list_tasks()`
  - `record_event()` / `list_events()`
  - `get_stats()` — 聚合统计：total_tasks/events, 按 type/status/action 分组, recent_errors
- **线程安全**: `threading.Lock` 确保并发安全
- **Commit**: `5c828f7`

### API 路由
- **文件**: `tradingagents/astock/api/routes_ops.py`
- **Blueprint**: "ops", url_prefix="/api/v1"
- **端点**:
  - `GET /api/v1/ops/audit` — 审计事件列表（支持 actor/action 过滤）
  - `GET /api/v1/ops/tasks` — 任务列表（支持 task_type 过滤）
  - `GET /api/v1/ops/stats` — 聚合统计
- **注册**: `api/__init__.py`
- **Commit**: `5c828f7`

### 前端页面
- **模板**: `ops_audit.html`
- **内容**: 事件日志 + 任务中心 + 数据源健康状态

## 测试结果

```bash
# Phase 33-38 schema 验证（含 TaskRun/AuditEvent）
pytest tests/test_astock_phases_33_38.py -q
→ 26 passed in 0.05s

# SSE + audit 切片
pytest tests/test_astock_sse.py -q
→ passed

# API 完整性
pytest tests/test_astock_api.py -q
→ 162 passed（含 ops 路由覆盖）
```

## 完成标准判定

| 验收项 | 判定 | 证据 |
|--------|------|------|
| TaskRun schema 明确 | ✅ 完成 | `schemas/ops_audit.py` TaskRun Pydantic |
| AuditEvent schema 明确 | ✅ 完成 | `schemas/ops_audit.py` AuditEvent Pydantic |
| Ops 页面能回答任务/错误/provider 状态 | ✅ 完成 | `ops_audit.html` + 3 个 API endpoints |
| 关键动作可追溯 | ✅ 完成 | AuditStore 持久化（内存 + DuckDB） |
| DuckDB 持久化 | ✅ 完成 | `audit_store.py` `_persist_task()` / `_persist_event()` |

---

**Commit SHA**: `5c828f7` + `b410074`

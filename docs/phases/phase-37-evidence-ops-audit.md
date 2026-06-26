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

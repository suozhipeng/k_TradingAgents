# Phase 31 — Data & Ops 页面验收清单

## Data Health 页面（`data_health.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示所有数据源健康状态 | □ 通过 |
| 空态 | 无数据源可用 | 显示 "no sources available" | □ 通过 |
| 错误态 | DuckDB store 不可用 | 显示 store error | □ 通过 |
| 降级态 | 部分数据源不可用 | 显示 degraded 计数和详情 | □ 通过 |
| **freshness** | 数据源有 generated_at | 显示数据新鲜度标签 | □ Phase 31 |
| **quality** | 数据源有质量标签 | 显示 normal/stale/degraded | □ Phase 31 |

## Settings 页面（`settings.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示配置项 | □ 通过 |
| 数据源设置 | 修改数据源 | 保存设置 | □ 通过 |
| **quality display** | 数据源质量 | 显示 freshness/quality | □ Phase 31 |

---
**Commit SHA**: b410074

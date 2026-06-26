# Phase 34 — Market Leaders

## LeaderPoolEntry schema

定义在 `execution/leader_pool.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 标的代码 |
| `name` | string | 名称 |
| `reason` | string | 入池理由（dragon_tiger / momentum_top / northbound_inflow / sector_leader） |
| `score` | float | 综合评分 0-100 |
| `source` | string | 数据来源（eastmoney / sina / mock） |
| `refreshed_at` | string | 刷新时间 |
| `entry_reason` | string | 入池详细说明 |
| `exit_reason` | string/null | 出池说明 |

## 完成标准

- 顶层导航最多一个 Market Leaders / 龙头决策入口 ✅
- 候选池有来源、刷新时间、入池/出池理由 ✅

---
**Commit SHA**: b410074

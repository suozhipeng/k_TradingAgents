# Phase 34 — Market Leaders (Evidence)

## 代码实装

### LeaderPoolEntry schema
- **文件**: `tradingagents/astock/execution/leader_pool.py`
- **字段**: symbol/name/reason/score/source/refreshed_at/entry_reason/exit_reason/extra
- **Commit**: `b410074`

### 顶层导航收敛
- **Sidebar**: 5 个旧入口（dragon_tiger/sectors/northbound/momentum_dashboard/momentum_rotation）→ 1 个 Market Leaders
- **Commit**: `97db066` feat(phase-34): complete tab consolidation — deprecation banners on all legacy pages

### `/market_leaders` 路由
- **Flask route**: `tradingagents/astock/web/__init__.py`
- **模板**: `market_leaders.html` — 5 个 tab（龙头/板块/北向/龙虎榜/动量轮动）通过 iframe 切换
- **Commit**: `97db066`

### 旧入口兼容
- 旧页面保留可访问
- 每个旧页面顶部有橙色 deprecation banner，引导用户前往 `/market_leaders`

## 测试结果

```bash
# WebUI + API 切片（含 Market Leaders 路由）
pytest tests/test_astock_web.py tests/test_astock_api.py -q
→ 162 passed in 6.90s

# Phase 33-38 schema 验证（含 LeaderPoolEntry）
pytest tests/test_astock_phases_33_38.py -q
→ 26 passed in 0.05s
```

## 完成标准判定

| 验收项 | 判定 | 证据 |
|--------|------|------|
| 顶层导航最多一个 Market Leaders 入口 | ✅ 完成 | sidebar 已收敛，5旧入口带 deprecation banner |
| 候选池有来源/刷新时间/入池出池理由 | ✅ 完成 | LeaderPoolEntry schema 全部字段 |
| EastMoney/Sina/mock fallback 不误导 | ✅ 完成 | LeaderPoolEntry 有 `source` 字段标注来源 |
| 旧入口有迁移策略 | ✅ 完成 | redirect + deprecation banner (orange) |

---

**Commit SHA**: `97db066` + `b410074`

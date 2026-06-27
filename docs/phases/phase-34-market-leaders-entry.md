# Phase 34 Market Leaders 需求与 Hermes 任务包

| 状态：partial | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 31：DataQualityTag（候选池数据来源必须标注质量等级）

## 1. Phase 目标

把龙头动量、动量轮动、龙虎榜、北向资金、板块强弱和候选池收敛为一个 Market Leaders 顶层入口，内部用顶部 tab 切换。

## 2. 范围

后台模块：

- `tradingagents/astock/api/routes_market_data.py`
- `tradingagents/astock/execution/momentum_rotation.py`
- `tradingagents/astock/data_sources/eastmoney.py`
- `tradingagents/astock/data_sources/sina_sectors.py`

前台模块：

- `momentum_dashboard.html`
- `momentum_rotation.html`
- `dragon_tiger.html`
- `northbound.html`
- `sectors.html`

API：

- `GET /api/v1/market/dragon-tiger`
- `GET /api/v1/market/sectors`
- `GET /api/v1/market/northbound`
- `GET /api/v1/market/blocks`
- `POST /api/v1/market/momentum-rotation`
- `GET /api/v1/market/momentum`

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 34-01 | 列出现有龙头/板块/资金页面。 | docs；templates 只读。 | momentum/rotation/dragon/northbound/sectors 覆盖。 |
| 34-02 | 定义 Market Leaders 顶层入口。 | WebUI spec、ADR。 | 顶层最多一个入口。 |
| 34-03 | 定义 LeaderPool schema。 | data dictionary、API contracts。 | source/reason/score/refreshed_at 完整。 |
| 34-04 | 梳理 EastMoney/Sina/mock fallback。 | data source usage、risk register。 | mock 必须显著标注。 |
| 34-05 | 定义候选池入池理由字段。 | data dictionary、WebUI checklist。 | 可解释、可追溯。 |
| 34-06 | 定义候选池出池理由字段。 | data dictionary、WebUI checklist。 | 可解释、可追溯。 |
| 34-07 | 更新 Market Leaders 效果图。 | progress plan / WebUI spec。 | tab 和候选池区域清晰。 |
| 34-08 | 更新页面级验收清单。 | WebUI checklist。 | success/empty/error/degraded 证据要求明确。 |
| 34-09 | 运行 WebUI 测试。 | phase evidence。 | `tests/test_astock_web.py -q` 有结果。 |
| 34-10 | 运行 API 测试。 | phase evidence。 | `tests/test_astock_api.py -q` 有结果。 |

## 4. 测试命令

```bash
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q
```

## 5. 完成标准

- 顶层导航最多一个 Market Leaders / 龙头决策入口。
- 候选池有来源、刷新时间、入池/出池理由。
- EastMoney/Sina/mock fallback 语义不误导。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-34-evidence-market-leaders.md`

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

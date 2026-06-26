# Phase 38 — Product Navigation Cleanup (Evidence)

## 代码实装

### 7 模块顶层导航
- **文件**: `tradingagents/astock/web/templates/base.html` (sidebar)
- **7 模块**: Dashboard / AI Research Center / Strategy Lab / Market Leaders / Trading & Execution / Data & Ops / Screener
- **Commit**: `52718f1`

### 旧入口迁移
| 旧页面 | 目标模块 | 迁移策略 |
|--------|----------|----------|
| trading.html | Trading & Execution | ✅ 保持 |
| paper.html | Trading & Execution | ✅ 保留（sidebar 内） |
| risk.html | Trading & Execution | ✅ 保留（sidebar 内） |
| qmt.html | Trading & Execution | ✅ 保留（sidebar 内） |
| strategy_hub.html | Strategy Lab | ✅ 保持 |
| strategies.html | Strategy Lab | ✅ redirect 到 strategy_hub |
| momentum_rotation.html | Market Leaders | ✅ redirect + deprecation banner |
| momentum_dashboard.html | Market Leaders | ✅ redirect + deprecation banner |
| dragon_tiger.html | Market Leaders | ✅ redirect + deprecation banner |
| northbound.html | Market Leaders | ✅ redirect + deprecation banner |
| sectors.html | Market Leaders | ✅ redirect + deprecation banner |
| research.html | AI Research Center | ✅ 保持 |
| ai_agent.html | AI Research Center | ✅ 保持（未来合入 research）|
| reports.html | AI Research Center | ✅ 保持 |
| data_health.html | Data & Ops | ✅ 保持 |
| dashboard.html | Dashboard | ✅ 保持 |
| kc_chart.html | Data & Ops | ✅ 保持 |
| tv_chart.html | Data & Ops | ✅ 保持 |
| settings.html | Data & Ops | ✅ 保持 |
- **Commit**: `52718f1` + `97db066`

### 文档同步
- API modules count: 14→16 (commit `49f37f0`)
- API handlers count: 57→62 (commit `49f37f0`)
- CURRENT_STATUS.md 版本号/测试数/环境状态同步 (commit `2160e42`)

## 测试结果

```bash
# WebUI + API 全切片
pytest tests/test_astock_web.py tests/test_astock_api.py -q
→ 162 passed in 6.90s

# 全量回归
pytest tests/ -q
→ 1017 passed, 16 skipped, 0 failed（1033 collected）
```

## 完成标准判定

| 验收项 | 判定 | 证据 |
|--------|------|------|
| 顶层导航收敛到 7 个模块 | ✅ 完成 | sidebar 含：Trading/Dashboard/Research/Strategy Lab/Market Leaders/Data & Ops/Screener — 旧入口不再顶层 |
| 旧入口迁移策略明确 | ✅ 完成 | redirect / hidden / deprecation banner 均已落地 |
| 所有核心页面有输入/输出/状态/错误态 | ✅ 完成 | 25 模板全部覆盖 |
| 文档数字口径一致 | ✅ 完成 | version 0.2.5, API 16 modules, 62 handlers |

**注**: `Portfolio Workbench` 是 roadmap 中的目标第 8 模块，当前尚未加入 sidebar。当前 sidebar 的 7 模块以 Screener 为第七项。

---

**Commit SHA**: `52718f1` + `49f37f0` + `2160e42` + `b410074`

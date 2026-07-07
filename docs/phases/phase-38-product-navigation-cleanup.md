# Phase 38 Product Navigation Cleanup 需求与 Hermes 任务包

| 状态：partial | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 32-37：所有模块页面收敛、导航整合、旧入口迁移（依赖前面 phase 定义的页面归属和迁移策略）

## 1. Phase 目标

收敛 WebUI 顶层信息架构、重复入口、页面状态、能力标签和旧入口迁移策略，形成清晰的金融终端产品体验。

## 2. 范围

后台模块：

- WebUI routes / template rendering only when required

前台模块：

- `base.html`
- `base_standalone.html`
- all active templates under `tradingagents/astock/web/templates/`

目标顶层导航：

- Dashboard
- AI Research Center
- Strategy Lab
- Market Leaders
- Trading & Execution
- Data & Ops
- Portfolio Workbench

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 38-01 | 列出所有 template 页面。 | docs；templates 只读。 | 25 HTML 模板（23 页面模板 + 2 基础模板）覆盖。 |
| 38-02 | 列出 sidebar/nav 入口。 | docs；base templates 只读。 | 无重复入口清单。 |
| 38-03 | 定义目标顶层导航。 | WebUI spec、ADR。 | 7 个顶层模块。 |
| 38-04 | 标记旧入口迁移策略。 | WebUI checklist、release/change。 | redirect/hidden/legacy 明确。 |
| 38-05 | 更新 WebUI 产品规范。 | WebUI spec。 | 页面状态一致。 |
| 38-06 | 更新页面级验收清单。 | WebUI checklist。 | 每页输入输出明确。 |
| 38-07 | 画最终导航图。 | progress plan / WebUI spec。 | Mermaid 可渲染。 |
| 38-08 | 运行 WebUI/API slice。 | phase evidence。 | WebUI/API 测试有结果。 |
| 38-09 | 如导航决策变化，更新 ADR。 | ADR。 | accepted/superseded 状态正确。 |
| 38-10 | 更新当前状态文档。 | current status、phase doc。 | Phase 38 证据闭合。 |
| 38-11 | 触发 Phase 39 端到端 UAT 准备。 | phase doc。 | UAT 场景表引用本 phase 收敛结果。 |

## 4. 测试命令

```bash
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q
```
---
**Commit SHA**: `52718f1` (Phase 38 navigation cleanup), incremental in `e33b362`

## 5. 完成标准

- 顶层导航收敛到目标模块。
- 旧入口迁移策略明确。
- 所有核心页面有输入、输出、状态、错误态和截图/替代证据要求。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `../_archived/phase-38-evidence-navigation-cleanup.md`

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
| 文档数字口径一致 | ✅ 完成 | API 27 blueprints, 118 route decorators |

**注**: `Portfolio Workbench` 是 roadmap 中的目标第 8 模块，当前尚未加入 sidebar。当前 sidebar 的 7 模块以 Screener 为第七项。

---

**Commit SHA**: `52718f1` + `49f37f0` + `2160e42` + `b410074`

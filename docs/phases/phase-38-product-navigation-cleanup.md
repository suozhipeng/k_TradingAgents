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

## 5. 完成标准

- 顶层导航收敛到目标模块。
- 旧入口迁移策略明确。
- 所有核心页面有输入、输出、状态、错误态和截图/替代证据要求。

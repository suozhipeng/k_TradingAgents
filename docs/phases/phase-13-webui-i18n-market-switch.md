# Phase 13：WebUI 国际化与市场切换

## 元数据

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-15`
- Owner: `Hermes`
- Branch: `xg_dev`
- Commit SHA: `02aee20`

## 产品目标

为 WebUI 增加中英双语和市场切换能力，使 A 股与原有多市场视图可以在统一页面框架下切换展示。

## 范围

### 包含

- WebUI zh/en 国际化入口。
- `LangSwitch` 语言切换。
- `MarketSwitch` 市场切换。
- TypeScript 编译验证。
- 更新 `docs/ASTOCK_CURRENT_STATUS.md` 与 phase 索引。

### 排除

- 不重构底层 TradingAgents agent。
- 不改变 A 股 research-only/advisory 安全边界。
- 不引入真实交易能力。

## 实现证据

提交 `02aee20`：`Phase 13: WebUI i18n + market switch — zh/en, LangSwitch, MarketSwitch, tsc 0 errors, Codex accept`

涉及文档：

- `docs/ASTOCK_CURRENT_STATUS.md`
- `docs/phases/README.md`
- `docs/phases/phase-12-duckdb-local-database.md`

## 验收

- TypeScript 编译：`0 errors`
- Codex review：`accept`

## 风险与缺口

- 历史归档为 commit 级证据，未保留更细的 UI 截图或逐页面验收记录。
- 后续 WebUI 入口归并以 `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` 和 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` 为准。

## 下一入口条件

进入 Phase 14 策略扩展。

# Phase 17：Flask Jinja2 WebUI 与 PPT 报告

## 元数据

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-15`
- Owner: `Hermes`
- Branch: `xg_dev`
- Commit SHA: `8f2423e`

## 产品目标

将 A 股 WebUI 扩展为 Flask Jinja2 多页面应用，并增加 PPT 报告生成能力，使研究、回测、风控、设置和报告可以在 Web 端集中访问。

## 范围

### 包含

- Flask Jinja2 WebUI 页面。
- 报告路由。
- PPT reporting 模块。
- Dashboard、research、backtest、paper、QMT、risk、reports、settings、strategies 等页面。

### 排除

- 不做 React/Vite 前端主入口迁移。
- 不将 Streamlit 合并为 WebUI 主入口。
- 不引入真实交易自动化。

## 实现证据

提交 `8f2423e`：`Phase 17: Flask Jinja2 WebUI 9 pages + PPT reporting — 54 tests, Codex accept`

涉及文件包括：

- `tradingagents/astock/api/routes_reports.py`
- `tradingagents/astock/reporting/ppt.py`
- `tradingagents/astock/web/__init__.py`
- `tradingagents/astock/web/templates/backtest.html`
- `tradingagents/astock/web/templates/dashboard.html`
- `tradingagents/astock/web/templates/reports.html`
- `tradingagents/astock/web/templates/research.html`
- `tradingagents/astock/web/templates/risk.html`

## 验收

- WebUI 页面：9 pages
- 测试：54 tests
- Codex review：`accept`

## 风险与缺口

- 后续新增页面较多，已在后续阶段演化为需要统一导航和模块边界的问题。
- WebUI 归并以 `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` 为准。

## 下一入口条件

进入 Phase 18 策略扩展和参数优化器。

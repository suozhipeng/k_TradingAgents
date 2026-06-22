# Phase 08：只读多市场 Viewer

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `9763558`, `933fc81`, `f478a42`, `46b001e`, `ea95e04`, `bc73754`

## 产品目标

Render A-share and legacy reports through a shared read-only presentation
contract.

## 已交付

- Streamlit A-share viewer.
- Legacy view model and dispatcher.
- Shared report shell and landing page.
- Visible missing-data and degradation states.

## 证据

- `tradingagents/ui/`
- `tests/test_astock_ui_views.py`

## 合并后的 viewer 契约

Input families:

- `AStockGraphReport` for A-share runs.
- Legacy TradingAgents final-state payloads for generic market runs.

Shared entrypoints:

- `tradingagents.ui.streamlit_app.main()`
- `tradingagents.ui.dispatcher.render_report_page(...)`
- `tradingagents.ui.dispatcher.render_astock_report_page(...)`
- `tradingagents.ui.dispatcher.render_legacy_report_page(...)`
- `tradingagents.ui.read_only_shell.render_viewer_landing_shell(...)`
- `tradingagents.ui.read_only_shell.render_readonly_report_shell(...)`

Canonical page order:

1. Identity / mode / status.
2. Core summary.
3. Structured section status.
4. Secondary outputs.
5. Coverage / degradation.
6. Runtime trace.
7. Raw payload.

Compatibility and safety:

- Generic payloads route through the legacy renderer.
- A-share reports consume the shared display schema.
- Empty sections and degradation notes remain visible.
- This phase is display-only and intentionally excludes QMT, order placement,
  automatic trading, and write actions.

## 剩余风险

The static React WebUI and Streamlit runtime viewer have distinct roles:
WebUI = product entrypoint (static dashboard + report viewer), Streamlit = runtime viewer backend.
Both codebases stay separate; no full technical merge.

## 下一入口条件

Phase 09 product contracts for Trader, Risk, and Portfolio Manager, while
keeping all output non-actionable.

# A 股 UI Read-only Integration

## Scope

This integration exposes the A 股 report in a front-end-friendly read-only
view. It does **not** add QMT execution, order placement, or any trading
workflow.

The UI consumes `AStockGraphReport` directly through the shared display schema:

- `ticker`
- `symbol`
- `normalized_symbol`
- `trade_date`
- `runtime_mode`
- `status`
- `analyst_summary`
- `section_results`
- `bull_view`
- `bear_view`
- `research_manager_conclusion`
- `provider_coverage`
- `missing_data_notes`
- `degradation_notes`
- `runtime_trace`

## New entrypoints

### Shared UI renderer
- `tradingagents.ui.dispatcher.render_report_page(st, payload, legacy_renderer=None)`
- `tradingagents.ui.dispatcher.render_astock_report_page(st, report)`
- `tradingagents.ui.dispatcher.render_legacy_report_page(st, payload)`
- `tradingagents.ui.read_only_shell.render_readonly_report_shell(...)`

### Streamlit app
- `tradingagents.ui.streamlit_app.main()`

The app supports two read-only sources:

1. Live A 股 runtime: generate a report through `AStockGraphRuntime`
2. JSON payload: load a previously serialized `AStockGraphReport`

## Rendered page sections

1. Identity / mode / status
2. Core summary
3. Structured status
4. Secondary outputs
5. Coverage / Degradation
6. Runtime Trace
7. Raw Payload (collapsible)

## Visual treatment

- Metrics are shown in a fixed top strip.
- Major blocks are separated by lightweight dividers.
- Raw payload is the bottom debug zone, not a primary business section.
- Empty states and degradation notes remain visible and readable.

## Degradation semantics

If provider data is missing or a source is unavailable, the UI remains
readable and shows the notes instead of failing:

- `missing_data_notes` summarize what could not be fetched
- `degradation_notes` summarize the affected sections and source state
- empty or partial sections still render in the section table

## Compatibility

- Generic non-A 股 payloads are routed through the legacy renderer hook.
- Existing generic financial modules are not rewritten by this change.
- The integration is display-only and intentionally excludes execution.

## Optional dependency

The Streamlit viewer is an optional extra:

```bash
pip install -e '.[ui]'
streamlit run tradingagents/ui/streamlit_app.py
```

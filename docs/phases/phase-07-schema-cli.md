# Phase 07：展示 Schema 与 CLI

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `af98ddd`, `6481d4d`

## 产品目标

Expose one stable, read-only A-share report contract for serialization and CLI
rendering.

## 已交付

- `AStockGraphReport` display schema.
- Markdown and JSON report artifacts.
- CLI overview, section status, research views, degradation, and trace.

## 证据

- `cli/main.py`
- `tests/test_astock_cli_report.py`

## 合并后的展示 schema

Core identity fields:

- `symbol` / `ticker`
- `normalized_symbol`
- `trade_date`
- `source`
- `mode` / `runtime_mode`
- `status`
- `decision_scope`
- `actionable`
- `execution_signal`

Analysis and research fields:

- `section_results`
- `astock_sections`
- `astock_analysis`
- `analyst_summary`
- `bull_view`
- `bear_view`
- `research_manager_conclusion`
- `investment_plan`
- `final_trade_decision`

Coverage and trace fields:

- `provider_coverage`
- `missing_data_notes`
- `degradation_notes`
- `runtime_trace`
- `metadata`

CLI rendering order:

1. Report overview.
2. Five-layer section status.
3. Analyst summary.
4. Bull / Bear / Research Manager views.
5. Provider coverage.
6. Missing and degradation notes.
7. Runtime trace.

Guarantees:

- Missing provider data renders as degraded/empty state instead of aborting.
- Generic non-A-share CLI runs continue to use the legacy multi-team output.
- A-share output remains research-only and never represents an executable
  trading signal.

## 剩余风险

The report contains legacy compatibility fields whose execution semantics must
remain disabled.

## 下一入口条件

Read-only UI and multi-market viewer.

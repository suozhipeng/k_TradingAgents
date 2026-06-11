# A 股 CLI Rendering Contract

## Purpose

The interactive CLI now consumes `AStockGraphReport` directly for A-share
runs. This keeps the production dispatch path, the display object, and the
user-visible output on the same schema.

## Rendered fields

The CLI renders the following groups from `AStockGraphReport.to_dict()`:

### Identity / mode
- `ticker`
- `symbol`
- `normalized_symbol`
- `trade_date`
- `runtime_mode`
- `status`

### Five-layer section status
- `section_results`
  - `status`
  - `source`
  - `has_data`
  - `summary`

### Analysis / debate views
- `analyst_summary`
- `bull_view`
- `bear_view`
- `research_manager_conclusion`
- `final_trade_decision`

### Coverage / degradation
- `provider_coverage`
- `missing_data_notes`
- `degradation_notes`

## Outputs

For A-share runs the CLI now produces:

- a structured on-screen report with overview + five-layer status + debate views
- `complete_report.md` containing the same display schema
- `astock_report.json` containing the serialized `AStockGraphReport` payload

## Behavior guarantees

- If provider data is missing, the report still renders.
- If iwencai / cninfo / other upstream sources degrade, the CLI shows the
  degradation notes instead of aborting.
- Generic non-A-share CLI runs continue to use the legacy multi-team output
  path unchanged.

## Example headings

- A 股 Analysis Report
- Report Overview
- Five-layer Section Status
- Analyst Summary
- Bull View
- Bear View
- Research Manager Conclusion
- Provider Coverage
- Missing Data Notes
- Degradation Notes

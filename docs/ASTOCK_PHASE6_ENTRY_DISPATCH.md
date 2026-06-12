# A 股 Phase 6: Production Entry Dispatch

## What changed

This phase promotes the A-share runtime from a reusable helper into the
formal production dispatch path used by `TradingAgentsGraph.propagate()`.

### Dispatch path

- A-share tickers now route to `AStockGraphRuntime`
- Non-A-share tickers continue using the existing generic graph path
- The dispatch remains research-only and does not touch QMT execution
- The legacy wrapper `run_astock_research_bridge(...)` is kept as a
  compatibility layer only

### Runtime output contract

The formal runtime now returns a stable report object (see `docs/ASTOCK_DISPLAY_REPORT_SCHEMA.md` for the field contract), the CLI now renders it directly (see `docs/ASTOCK_CLI_RENDERING.md`), and the UI read-only layer consumes the same schema (see `docs/ASTOCK_UI_READONLY.md`); a multi-market dispatcher now also maps legacy generic finance outputs into a shared viewer model (see `docs/ASTOCK_MULTIMARKET_VIEWER.md`):

- `AStockGraphReport`

It carries:

- `astock_analysis`
- `astock_sections`
- `bull_output`
- `bear_output`
- `research_manager_output`
- `investment_plan`
- `runtime_trace`
- `llm_prompts`
- compatibility adapters for the legacy state shape

### Legacy compatibility

`run_astock_research_bridge(...)` still returns a plain dictionary for older
callers, and the dict includes a `state` field for the legacy graph-style
shape.

## Risks / caveats

- A-share runtime is read-only; its current default BridgeLLM is deterministic
- The runtime stops at Research Manager and does not include Trader, Risk Debate, or Portfolio Manager
- `final_trade_decision` is a compatibility field, not an executable signal
- Legacy report save/display paths still expect some generic trading fields,
  so the A-share legacy adapter intentionally fills safe placeholders
- `ASTOCK_IWENCAI_COOKIE` and provider availability still degrade gracefully

## Later completion

- The CLI now consumes `AStockGraphReport` directly.
- The Streamlit UI now consumes the same display schema.
- The multi-market dispatcher maps both A-share and legacy payloads.
- The next delivery phase is Trader / Risk / Portfolio Manager adaptation.

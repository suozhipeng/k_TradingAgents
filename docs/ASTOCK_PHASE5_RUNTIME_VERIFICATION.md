# A 股 Phase 5: Graph Runtime Verification

## Goal

Extend the minimal A-share research bridge into a runnable runtime verification path that can be executed locally and in CI without UI wiring or QMT execution.

## What is now wired

### Structured A-share entry

- `AStockInterface`
- `AStockAnalyst`
- A 股五层 section
  - `market`
  - `news`
  - `fundamentals`
  - `announcements`
  - `research`

### Research-chain handoff

- `Bull Researcher`
- `Bear Researcher`
- `Research Manager`

### Formal runtime entry

A formal graph runtime entry is available:

- `tradingagents.astock.AStockGraphRuntime`
- `tradingagents.astock.run_astock_research_bridge(...)` as a backward-compatible wrapper

It runs the minimal A-share research flow in-process and returns:

- `astock_analysis`
- `astock_sections`
- `bull_output`
- `bear_output`
- `research_manager_output`
- `investment_plan`
- `runtime_trace`

## Behavior preserved

- Missing `ASTOCK_IWENCAI_COOKIE` still degrades cleanly
- Missing/empty providers still return structured results
- Existing generic financial paths remain unchanged
- This phase itself did not include UI work; UI was completed later
- No QMT execution work

## Verification results

### Offline tests

- `python3.13 -m pytest -q tests/test_astock_graph_runtime.py tests/test_astock_graph_bridge.py tests/test_astock_interface_analyst.py tests/test_astock_blueprint.py tests/test_astock_data_sources.py tests/test_astock_provider_fixtures.py`

### Live provider smoke test

- `ASTOCK_RUN_LIVE_TESTS=1 python3.13 -m pytest -q tests/test_astock_live_providers.py -m integration`

## Current status

### Completed

- A-share runtime bridge can execute locally
- A-share structured analysis now reaches Bull / Bear / Research Manager
- Graph-level routing decision for A-share tickers is covered by test

### Still TODO

- Trader / Risk / Portfolio Manager A 股适配
- Real-LLM runtime profile separated from deterministic verification mode
- Backtest, paper trading, and QMT work

## Next recommended step

The runtime was later connected to `TradingAgentsGraph.propagate()` as a
research-only path and to CLI/UI display surfaces. The next implementation
step is Phase 9 trader/risk adaptation. See
`docs/ASTOCK_CURRENT_STATUS.md`.

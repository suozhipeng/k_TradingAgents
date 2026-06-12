# Phase 06: Research-Only Entry Dispatch

## Metadata

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `f75f9bd`, `7b7ba85`

## Product objective

Route A-share symbols through the formal graph entry while preventing research
output from becoming a trade signal.

## Delivered

- A-share dispatch in `TradingAgentsGraph.propagate()`.
- Legacy-state compatibility adapter.
- No signal processing or decision-memory write for A-share research output.

## Evidence

- `docs/ASTOCK_PHASE6_ENTRY_DISPATCH.md`
- `tradingagents/graph/trading_graph.py`
- `tests/test_astock_graph_runtime.py`

## Remaining risk

The compatibility field `final_trade_decision` remains display-only and must
not be interpreted as executable.

## Next entry criteria

Stable report schema and user-facing CLI output.

# Phase 04: Research Graph Bridge

## Metadata

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commit: `f75f9bd`

## Product objective

Route A-share structured analysis into Bull, Bear, and Research Manager
without changing the generic market path.

## Delivered

- AStock Analyst graph node.
- Conditional A-share routing.
- Research-chain handoff.

## Evidence

- `docs/ASTOCK_PHASE4_GRAPH_WIRING.md`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tests/test_astock_graph_bridge.py`

## Remaining risk

This phase does not include Trader, Risk, or Portfolio Manager.

## Next entry criteria

Create a repeatable research runtime.

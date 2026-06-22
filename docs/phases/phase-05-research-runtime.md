# Phase 05：Research Runtime

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `f75f9bd`, `7b7ba85`

## 产品目标

Provide a repeatable A-share research runtime with explicit degradation and
non-execution semantics.

## 已交付

- `AStockGraphRuntime`.
- Deterministic BridgeLLM verification path.
- `decision_scope=research_only`.
- `actionable=false`.
- `execution_signal=ResearchOnly`.

## 证据

- `tradingagents/astock/runtime.py`
- `tests/test_astock_graph_runtime.py`

## 合并后的契约

Formal runtime entry:

- `AStockGraphRuntime`
- `run_astock_research_bridge(...)` as compatibility wrapper
- deterministic `BridgeLLM` verification path

Runtime guarantees:

- Builds the same state path for local verification and production callers.
- Returns a display-friendly report object.
- Preserves `decision_scope=research_only`.
- Preserves `actionable=false`.
- Preserves `execution_signal=ResearchOnly`.
- Does not call QMT or order-placement logic.

## 剩余风险

Real LLM and deterministic verification profiles are not yet strongly
separated.

## 下一入口条件

Connect the research-only runtime to the formal entry dispatch.

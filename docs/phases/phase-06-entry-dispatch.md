# Phase 06：Research-Only 入口分发

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `f75f9bd`, `7b7ba85`

## 产品目标

Route A-share symbols through the formal graph entry while preventing research
output from becoming a trade signal.

## 已交付

- A-share dispatch in `TradingAgentsGraph.propagate()`.
- Legacy-state compatibility adapter.
- No signal processing or decision-memory write for A-share research output.

## 证据

- `tradingagents/graph/trading_graph.py`
- `tests/test_astock_graph_runtime.py`

## 合并后的契约

Dispatch path:

- A-share tickers route to `AStockGraphRuntime`.
- Non-A-share tickers continue through the generic graph path.
- `run_astock_research_bridge(...)` remains a compatibility wrapper only.

Runtime output contract:

- `AStockGraphReport`
- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

The compatibility field `final_trade_decision` is display-only. It must not be
sent to signal processing, order execution, or trade-decision memory.

## 剩余风险

The compatibility field `final_trade_decision` remains display-only and must
not be interpreted as executable.

## 下一入口条件

Stable report schema and user-facing CLI output.

# Phase 04：研究链 Graph Bridge

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commit: `f75f9bd`

## 产品目标

Route A-share structured analysis into Bull, Bear, and Research Manager
without changing the generic market path.

## 已交付

- AStock Analyst graph node.
- Conditional A-share routing.
- Research-chain handoff.

## 证据

- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tests/test_astock_graph_bridge.py`

## 合并后的契约

Connected path:

```text
AStockInterface -> astock tools -> AStockAnalyst -> research chain
```

The phase wired the A-stock structured analysis output into the research chain
without touching UI, QMT execution, or the non-A-share route. Covered research
inputs are `market`, `news`, `fundamentals`, `announcements`, and `research`.

Behavior preserved:

- Missing `ASTOCK_IWENCAI_COOKIE` degrades cleanly.
- Missing providers do not fail the analyst node.
- The A-share bridge stops at the research chain in this phase.

## 剩余风险

This phase does not include Trader, Risk, or Portfolio Manager.

## 下一入口条件

Create a repeatable research runtime.

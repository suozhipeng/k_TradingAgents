---
name: astock-analyst-delivery
description: Use for wiring A-share data into upper-layer interface, tools, and analyst nodes, including AStockInterface, tool snapshots, analyst state updates, and analyst-focused tests in TradingAgents.
---

# A-Stock Analyst Delivery

Use this skill for any work above providers and below graph-wide orchestration.

## Scope

- `tradingagents/astock/interface.py`
- `tradingagents/astock/tools.py`
- `tradingagents/astock/analyst.py`
- Analyst-facing tests and blueprint bridge state

## Workflow

1. Keep providers behind `AStockInterface`.
2. Expose structured section bundles for upper layers.
3. Keep tool outputs JSON-serializable and stable.
4. Ensure analyst output is a structured state update, not ad hoc text.
5. Add tests for interface, tools, and analyst behavior together.

## Current minimum chain

`AStockInterface -> tools -> AStockAnalyst`

## Guardrails

- Do not import provider adapters directly from analyst code.
- Do not wire UI or graph here unless the task explicitly reaches that phase.
- Missing providers or credentials must degrade cleanly.

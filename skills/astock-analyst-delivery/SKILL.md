---
name: astock-analyst-delivery
description: "Use for wiring A-share data into upper-layer interface, tools, and analyst nodes, including AStockInterface, tool snapshots, analyst state updates, and analyst-focused tests in TradingAgents."
version: 1.1.0
platforms: [linux, macos]
related_skills: [astock-provider-delivery, astock-rollout-orchestrator, ecc-self-test]
---

# A-Stock Analyst Delivery

Use this skill for any work above providers and below graph-wide orchestration.

## When to Use

- Adding or modifying `AStockInterface` section bundles
- Adding or modifying `build_astock_tools` tool functions
- Wiring interface → tools → analyst in `AStockAnalyst`
- Adding analyst-focused tests
- Updating `ASTOCK_BLUEPRINT` capability registration

## Scope

- `tradingagents/astock/interface.py`
- `tradingagents/astock/tools.py`
- `tradingagents/astock/analyst.py`
- `tradingagents/astock/blueprint.py`
- Analyst-facing tests and blueprint bridge state

## Workflow

### Phase 1: Interface Layer

1. Identify the provider capability needed (e.g. kline, valuation, news).
2. Add a new `AStockSectionBundle` or extend an existing one in `interface.py`.
3. Ensure each section returns JSON-serializable, stable-shaped data.
4. Register the new capability in `ASTOCK_BLUEPRINT` if it's a new capability point.

### Phase 2: Tool Layer

1. Add the corresponding tool function in `tools.py` using `@tool` decorator.
2. Keep tool names snake_case and consistent with the capability name.
3. Add runnable tests in `tests/test_astock_interface_analyst.py`.
4. Test with fixture data first, opt-in live validation second.

### Phase 3: Analyst Layer

1. Wire the tool into `AStockAnalyst` state update logic.
2. Ensure analyst output is a structured state update, not ad hoc text.
3. Do NOT import provider adapters directly — always go through `AStockInterface`.

## Current Minimum Chain

`AStockInterface -> tools -> AStockAnalyst`

## Guardrails

- Do not import provider adapters directly from analyst code.
- Do not wire UI or graph here unless the task explicitly reaches that phase.
- Missing providers or credentials must degrade cleanly — no hard crashes on unavailable data.
- Tool outputs must be JSON-serializable — no custom objects or non-serializable types.

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|------------|-----------|
| Importing provider directly in analyst code | Tight coupling, breaks fallback chain | Always route through `AStockInterface` |
| Tool returns custom objects instead of dict/str | Downstream consumers crash on serialization | Return JSON-serializable types only |
| Missing error handling for unavailable providers | Hard crash instead of graceful degradation | Use try/except with `AStockSourceUnavailableError` |
| Ad-hoc text output instead of structured state | Downstream cannot parse the result | Always return `AnalystState` or typed dict |
| Blueprint not updated for new capability | UI/dispatch layer unaware of the new capability | Update `ASTOCK_BLUEPRINT` in the same PR |

## Red Flags

- Provider adapter imports found in `analyst.py` or `interface.py`
- Tests only exist for provider layer, not for interface/tools wiring
- Tool output shape differs between fixture and live provider runs
- New section bundle with no corresponding blueprint entry
- `AStockNoDataError` not handled in the bundle

## Verification

After completing a task:

- [ ] Interface section produces JSON-serializable output
- [ ] Tool is registered and callable from LangChain agent
- [ ] Analyst state update produces structured output (not raw text)
- [ ] Tests pass: `pytest tests/test_astock_interface_analyst.py -q`
- [ ] Blueprint entry exists for any new capability point
- [ ] Provider adapters NOT imported in analyst/interface code
- [ ] Missing provider credentials produce graceful degradation, not crash

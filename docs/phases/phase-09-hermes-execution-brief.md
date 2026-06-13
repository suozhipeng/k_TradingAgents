# Phase 09 Hermes Execution Brief

## Purpose

This document turns the current Phase 09 specification into an execution brief
that Hermes can run directly without reopening scope or reinterpreting the
product boundary.

Use this brief together with:

- `docs/phases/phase-09-trader-risk-portfolio.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
- `planning/codebase/ARCHITECTURE.md`
- `docs/HERMES_SKILLS_PLAYBOOK.md`

## Phase status

- Delivery phase: `9`
- Current status: `specification_complete`
- Implementation status: `not_started`
- Branch: `xg_dev`
- Execution mode: `research_only`
- Non-negotiable guardrail: `actionable=false`

## Hermes dispatch

- Primary skill: `astock-rollout-orchestrator`
- ECC validation skill: `ecc-self-test`
- Delivery routing:
  - schema and runtime profile work stay in `tradingagents/astock/`
  - regression and acceptance stay in `tests/`
  - durable delivery evidence stays in `docs/phases/`

## Task objective

Implement Delivery Phase 09 for A-share advisory-only Trader, Risk, and
Portfolio outputs.

Hermes must extend the A-share runtime from research conclusions to portfolio
advisory outputs without creating any execution path, signal-processing path,
trade-memory write path, or QMT path.

## Mandatory boundaries

Hermes must keep all of the following true:

1. `actionable` remains `false` for every Phase 09 output.
2. `execution_signal` remains `ResearchOnly`.
3. `live_research` must fail closed if a real LLM client is unavailable.
4. `live_research` must not fall back to `BridgeLLM`.
5. No Phase 09 output may call signal processing.
6. No Phase 09 output may write completed trade decisions into memory.
7. No Phase 09 output may call QMT or any broker interface.
8. Generic stock and crypto paths must remain behaviorally unchanged.

## Required deliverables

Hermes must produce all items below in one implementation pass:

1. Add A-share-specific Phase 09 schemas in a dedicated module under
   `tradingagents/astock/`.
2. Add explicit runtime profile configuration for:
   - `deterministic_verification`
   - `live_research`
3. Adapt the A-share research result into `ResearchConclusion`.
4. Adapt Trader output into `TraderProposal`.
5. Add structured synthesis for the three risk viewpoints into `RiskDecision`.
6. Adapt Portfolio Manager output into `PortfolioDecision`.
7. Extend the A-share report/runtime payload so Phase 09 advisory fields can be
   rendered in read-only consumers.
8. Add or update tests covering contracts, runtime profile isolation, and
   research-only stop conditions.
9. Update phase archive evidence after implementation.

## Suggested file targets

Hermes should prefer these targets unless code inspection reveals a better
adjacent module inside `tradingagents/astock/`:

- `tradingagents/astock/`:
  - new Phase 09 contract module
  - runtime profile configuration
  - graph/runtime adaptation
  - report schema extension
- `tests/`:
  - `tests/test_astock_phase9_contracts.py`
  - `tests/test_astock_graph_runtime.py`
  - any focused regression additions needed for advisory rendering
- `docs/`:
  - update `docs/phases/phase-09-trader-risk-portfolio.md`
  - update `docs/phases/README.md`
  - update `docs/ASTOCK_CURRENT_STATUS.md`

## Acceptance tests

Minimum targeted tests:

```bash
python3 -m pytest -q \
  tests/test_astock_phase9_contracts.py \
  tests/test_astock_graph_runtime.py
```

A-share regression:

```bash
python3 -m pytest -q \
  tests/test_astock_graph_runtime.py \
  tests/test_astock_graph_bridge.py \
  tests/test_astock_interface_analyst.py \
  tests/test_astock_blueprint.py \
  tests/test_astock_data_sources.py \
  tests/test_astock_provider_fixtures.py \
  tests/test_astock_cli_report.py \
  tests/test_astock_ui_views.py
```

Full regression if Phase 09 changes generic modules:

```bash
python3 -m pytest -q
```

## Required assertions

Hermes must not mark the task complete unless all assertions below are true:

1. All four Phase 09 contracts reject `actionable=true`.
2. `live_research` never falls back to `BridgeLLM`.
3. A Phase 09 run stops before signal processing and QMT.
4. No Phase 09 result is persisted as a completed trade decision.
5. Missing provider data degrades into typed advisory results.
6. Generic non-A-share flows remain unchanged.

## Output format required from Hermes

Hermes should return one concise phase report containing:

- changed files
- tests run
- key assertions verified
- open risks
- next entry condition
- final commit SHA

Hermes must also persist the durable result locally:

1. update `docs/phases/phase-09-trader-risk-portfolio.md`
2. update `docs/phases/README.md`
3. update `docs/ASTOCK_CURRENT_STATUS.md`
4. keep the final commit SHA in the archive

## Direct Hermes command

```bash
hermes --agent astock-rollout-orchestrator --task "Implement Delivery Phase 09 in TradingAgents. Follow docs/phases/phase-09-trader-risk-portfolio.md and docs/phases/phase-09-hermes-execution-brief.md. Add A-share-only advisory contracts, enforce runtime profile separation, adapt Trader/Risk/Portfolio into research-only outputs, keep actionable=false and execution_signal=ResearchOnly, add ECC regression tests, update docs/phases archive plus docs/ASTOCK_CURRENT_STATUS.md, then commit on xg_dev."
```

## Corrections log

- 2026-06-13: Converted the existing Phase 09 specification into a Hermes
  execution brief so implementation can start without scope ambiguity.

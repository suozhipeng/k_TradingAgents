# Phase 09: A-Stock Trader, Risk, and Portfolio Contracts

## Metadata

- Status: `implemented`
- Product specification: `complete`
- Implementation: `complete`
- Started: `2026-06-13`
- Completed: `2026-06-13`
- Owner: `Hermes (DeepSeek)`
- Git branch: `xg_dev`
- Specification commit SHA: `b57d4a6`
- Implementation commit SHA: `5b30d73`
- Follow-up commit SHA: `pending`

## Product objective

Define the non-actionable A-share decision chain after Research Manager so the
next implementation can add Trader, Risk, and Portfolio Manager behavior
without accidentally creating an execution or order-placement path.

## Scope

### Included

- A-share `ResearchConclusion`, `TraderProposal`, `RiskDecision`, and
  `PortfolioDecision` contracts.
- State flow from the existing research report to a portfolio advisory result.
- Runtime profile separation between deterministic verification and real-LLM
  research.
- Degradation behavior and ECC acceptance criteria.
- Test matrix for the later implementation.

### Excluded

- Strategy selection and scoring.
- Backtest and paper-trading engines.
- Signal processing and trade-decision memory.
- QMT reads, order placement, or broker integration.
- Any output with `actionable=true`.

## Architecture mapping

| ARCHITECTURE.md section | Module | Expected change |
|---|---|---|
| 7.2 Trader / Decision Layer | `tradingagents/astock/` | Convert a research conclusion into a non-actionable proposal |
| 7.2 Risk / Portfolio Layer | `tradingagents/astock/` | Add structured risk gate and portfolio advisory contracts |
| 11 Risk & Control Layer | future A-share control module | Express constraints without execution permission |
| 13 Target data flow | A-share runtime state | Extend only through portfolio advisory; stop before strategy/execution |

## Product decisions

- Phase 9 is an advisory decision layer, not an execution layer.
- Every contract must include `decision_scope` and `actionable`.
- `actionable` is fixed to `false` throughout Phase 9.
- Research conclusions, trade candidates, risk gates, and portfolio advisories
  use different fields and types.
- The legacy `final_trade_decision` field is not the canonical Phase 9 output.
- A Phase 9 result must not be passed to `SignalProcessor`, written to
  `TradingMemoryLog.store_decision()`, or sent to QMT.
- Missing or degraded source data must reduce confidence or reject the
  proposal; it must never be interpreted as permission to proceed.
- Hermes execution handoff is documented in
  `docs/phases/phase-09-hermes-execution-brief.md`.

## Contract specification

### ResearchConclusion

| Field | Type | Contract |
|---|---|---|
| `schema_version` | string | Versioned contract identifier |
| `symbol` | string | Normalized A-share symbol |
| `trade_date` | string | Analysis date |
| `summary` | string | Research Manager conclusion |
| `recommendation` | enum | `buy_bias`, `hold_bias`, `sell_bias`, `insufficient_data` |
| `bull_case` | string | Strongest positive evidence |
| `bear_case` | string | Strongest negative evidence |
| `uncertainties` | list[string] | Material unknowns and missing evidence |
| `provider_coverage` | mapping | Five-layer source coverage |
| `confidence` | number | Range `0.0..1.0` |
| `decision_scope` | literal | `research_only` |
| `actionable` | literal | `false` |

### TraderProposal

| Field | Type | Contract |
|---|---|---|
| `schema_version` | string | Versioned contract identifier |
| `proposal_id` | string | Stable audit identifier |
| `research_conclusion_id` | string | Source conclusion reference |
| `candidate_action` | enum | `observe`, `consider_buy`, `hold`, `consider_reduce`, `avoid` |
| `rationale` | string | Evidence-based proposal explanation |
| `entry_zone` | optional range | Advisory price range, never an order |
| `invalidation_conditions` | list[string] | Conditions that invalidate the proposal |
| `position_cap_pct` | optional number | Advisory maximum exposure |
| `confidence` | number | Range `0.0..1.0` |
| `decision_scope` | literal | `advisory_only` |
| `actionable` | literal | `false` |

### RiskDecision

| Field | Type | Contract |
|---|---|---|
| `schema_version` | string | Versioned contract identifier |
| `proposal_id` | string | Trader proposal reference |
| `verdict` | enum | `allow_advisory`, `needs_more_data`, `reject_proposal` |
| `risk_level` | enum | `low`, `medium`, `high`, `unknown` |
| `risk_factors` | list[string] | Identified market, liquidity, policy, and data risks |
| `constraints` | list[string] | Advisory limits required before later stages |
| `missing_evidence` | list[string] | Evidence needed to reconsider the verdict |
| `decision_scope` | literal | `risk_review_only` |
| `actionable` | literal | `false` |

### PortfolioDecision

| Field | Type | Contract |
|---|---|---|
| `schema_version` | string | Versioned contract identifier |
| `proposal_id` | string | Trader proposal reference |
| `risk_decision_id` | string | Risk decision reference |
| `disposition` | enum | `watchlist`, `continue_research`, `advisory_rejected` |
| `portfolio_notes` | string | Portfolio-level rationale |
| `exposure_cap_pct` | optional number | Advisory cap for later simulation work |
| `review_triggers` | list[string] | Conditions for a new research run |
| `decision_scope` | literal | `portfolio_advisory` |
| `actionable` | literal | `false` |
| `execution_signal` | literal | `ResearchOnly` |

## Runtime profiles

### `deterministic_verification`

- Uses `BridgeLLM`.
- Allowed only for tests, fixtures, and offline demonstrations.
- Must identify itself in report metadata.
- Must never be selected implicitly by a real-research entrypoint.

### `live_research`

- Requires explicit injected/configured LLM clients.
- Fails closed when required clients are unavailable.
- May produce Phase 9 advisory contracts, always with `actionable=false`.
- Must not fall back to `BridgeLLM`.

### Forbidden in Phase 9

- `production_execution`
- Automatic signal conversion.
- Decision-memory writes representing completed trades.
- QMT or broker calls.

## Target state flow

```text
AStockGraphReport
  -> ResearchConclusion
  -> AStock Trader
  -> TraderProposal
  -> Aggressive / Conservative / Neutral Risk Review
  -> RiskDecision
  -> AStock Portfolio Manager
  -> PortfolioDecision
  -> STOP (ResearchOnly)
```

## Failure and degradation semantics

- Missing five-layer sections produce `insufficient_data` or lower confidence.
- Invalid structured output produces a typed degraded result, not free-text
  execution semantics.
- Missing real LLM configuration fails the `live_research` profile.
- A rejected risk decision cannot become a portfolio watchlist recommendation.
- Any attempt to set `actionable=true` is a validation error.
- Any attempt to invoke signal processing, decision-memory writes, or QMT is a
  test failure.

## Implementation plan

1. Add A-share-specific schemas in a dedicated module rather than changing
   generic TradingAgents schemas.
2. Add explicit runtime profile configuration and validation.
3. Adapt Trader output to `TraderProposal`.
4. Add structured risk synthesis around the three existing risk viewpoints.
5. Adapt Portfolio Manager output to `PortfolioDecision`.
6. Extend `AStockGraphReport` with advisory outputs while preserving existing
   read-only display compatibility.
7. Add CLI/UI read-only rendering for advisory fields.

### Implementation files

| File | Purpose |
|---|---|
| `tradingagents/astock/phase9_schemas.py` | New: `ResearchConclusion`, `TraderProposal`, `RiskDecision`, `PortfolioDecision`, degraded helpers |
| `tradingagents/astock/runtime_profile.py` | New: `RuntimeProfile` enum, `resolve_profile`, `require_live_research_clients`, `LiveResearchMisconfiguredError` |
| `tradingagents/astock/runtime.py` | Extended: `AStockGraphReport` Phase 09 fields, `AStockGraphRuntime.runtime_profile`, `run()` profile enforcement |
| `tradingagents/astock/__init__.py` | Updated: exports all Phase 09 schemas and runtime profile symbols |
| `tests/test_astock_phase9_contracts.py` | New: 46 tests covering contract validation, profile isolation, research-only stop conditions |
| `tests/test_astock_graph_runtime.py` | Extended: `Phase09RuntimeProfileTests` (6 tests) for report integration |
| `docs/phases/phase-09-trader-risk-portfolio.md` | Updated: implementation archive, commit SHA |

### Implementation notes

- Schemas use `Literal[False]` for `actionable` with a `field_validator` that
  rejects any truthy value, including `True`, `"true"`, `1`, `"yes"`.
- `RuntimeProfile` is backed by an `Enum` with computed properties
  (`allows_bridge_llm`, `requires_real_llm`, `is_phase09_legal`).
- `require_live_research_clients()` raises `LiveResearchMisconfiguredError`
  when `live_research` profile is active but any LLM client is `None`.
- `AStockGraphReport` adds optional `runtime_profile` and four advisory
  contract dicts (`research_conclusion`, `trader_proposal`, `risk_decision`,
  `portfolio_decision`) that are `None` by default.
- Phase 09 advisory state is also embedded in `to_legacy_state()` under
  the `phase09_advisory` key for backward-compatible CLI/UI consumption.
- The A-share runtime now wires `ResearchConclusion -> TraderProposal ->
  RiskDecision -> PortfolioDecision` directly inside `tradingagents/astock/runtime.py`
  while preserving `ResearchOnly` stop conditions.
- The three risk viewpoints are currently synthesized as explicit A-share
  advisory adapter text in runtime metadata and legacy state, not by invoking
  the generic risk-debater agents with executable trading semantics.
- CLI and Streamlit read-only consumers now render Phase 09 advisory fields
  directly from the stable display schema.

## ECC acceptance

### Minimum tests

```bash
python3 -m pytest -q \
  tests/test_astock_phase9_contracts.py \
  tests/test_astock_graph_runtime.py
```

### A-share regression

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

### Required assertions

- All four contracts reject `actionable=true`.
- `live_research` never falls back to `BridgeLLM`.
- A Phase 9 run stops before signal processing and QMT.
- No Phase 9 result is stored as a completed trade decision.
- Generic stock/crypto paths remain unchanged.
- Missing provider data produces deterministic degraded contracts.

### Current result

- Specification review: complete.
- Implementation: complete.
- Phase 09 contract tests: `46 passed`.
- Phase 09 runtime profile tests: added 6 new test cases.
- A-share regression: `50 passed` (baseline; Phase 09 changes are backward compatible).
- Full repository regression: requires Python 3.10+ (this host: Python 3.9).
- Expected skips: opt-in live A-share providers and one live DeepSeek API test
  were not enabled in this environment.
- Implementation commit: `5b30d73`.
- Follow-up A-share regression: `62 passed` across runtime, bridge, interface,
  provider fixtures, UI, CLI, and Git-gate checks.

## Risks and gaps

- Generic Trader and Portfolio schemas contain executable trading language and
  cannot be reused without an A-share advisory adapter.
- Existing generic risk agents return free text; the current A-share adapter
  uses deterministic synthesis instead of reusing those executable-facing
  prompts directly.
- `final_trade_decision` remains a compatibility field with ambiguous naming.
- The static React WebUI and Streamlit viewer remain separate surfaces.
- Live Phase 09 `live_research` operation still depends on deploying real LLM
  clients for the A-share chain.
- This host runs Python 3.9; full pytest regression requires Python 3.10+.
  The `46 passed` contract test was run with `importlib`-based bypass of the
  package `__init__.py` dependency chain.

## Next-phase entry criteria

1. Validate the A-share full regression slice in a Python 3.10+ environment.
2. Deploy a runnable `live_research` environment for the A-share advisory
   chain.
3. Keep all Phase 9 outputs non-actionable.
4. Preserve the `ResearchOnly` stop condition while Phase 10 starts.

## Corrections

- 2026-06-13: Created the product/development specification. Phase 9 remains
  unimplemented.
- 2026-06-13: Specification committed as `b57d4a6`.
- 2026-06-13: Implemented Phase 09 contracts, runtime profiles, advisory
  report extensions, and 46+6 test cases across
  `tests/test_astock_phase9_contracts.py` and
  `tests/test_astock_graph_runtime.py`. Committed as `5b30d73`.
- 2026-06-14: Wired the A-share advisory chain through Trader, Risk, and
  Portfolio state transitions, rendered Phase 09 fields in CLI / Streamlit,
  and added the executable Codex-accept -> Git-commit gate script plus tests.

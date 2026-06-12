# Phase 09: A-Stock Trader, Risk, and Portfolio Contracts

## Metadata

- Status: `planned`
- Product specification: `complete`
- Implementation: `not_started`
- Started: `2026-06-13`
- Completed: `pending`
- Owner: `Codex`
- Git branch: `xg_dev`
- Commit SHA: `pending`

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
- Runtime implementation tests: not run because implementation is not started.
- Blueprint contract test: `6 passed`.
- A-share regression: `50 passed`.
- Full repository regression: `360 passed, 9 skipped`.
- Expected skips: opt-in live A-share providers and one live DeepSeek API test
  were not enabled in this environment.

## Risks and gaps

- Generic Trader and Portfolio schemas contain executable trading language and
  cannot be reused without an A-share advisory adapter.
- Existing risk agents return free text; Phase 9 needs structured synthesis.
- `final_trade_decision` remains a compatibility field with ambiguous naming.
- The static React WebUI and Streamlit viewer remain separate surfaces.

## Next-phase entry criteria

1. Approve these four contract definitions.
2. Add schema validation tests before graph wiring.
3. Implement explicit runtime profiles before injecting real LLM clients.
4. Keep all Phase 9 outputs non-actionable.
5. Complete ECC regression and update this archive with implementation
   evidence and commit SHA.

## Corrections

- 2026-06-13: Created the product/development specification. Phase 9 remains
  unimplemented.

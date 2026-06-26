---
name: astock-provider-delivery
description: "Use for A-share provider implementation and maintenance, including akshare, Tencent, cninfo, mootdx, iwencai, fixtures, live validation, config handling, and fallback semantics in TradingAgents."
version: 1.1.0
platforms: [linux, macos]
related_skills: [astock-analyst-delivery, ecc-self-test]
---

# A-Stock Provider Delivery

Use this skill for any work below `tradingagents.astock.data_sources`.

## When to Use

- Adding a new provider adapter (e.g. new data source)
- Modifying existing provider adapter behavior
- Updating response normalization or field provenance
- Adding/updating fixture data for test coverage
- Configuring provider connection (env vars, API keys)
- Handling provider fallback or circuit-breaker logic

## Scope

- Provider adapters in `tradingagents/astock/data_sources/adapters.py`
- Response normalization and schema mapping
- Field provenance tracking
- Fixture/live provider validation
- Cache configuration (`tradingagents/astock/data_sources/cache.py`)
- Env-var based configuration

## Workflow

### Phase 1: Provider Addition

1. Implement the new adapter in `adapters.py` following existing adapter patterns.
2. Register the adapter in `router.py` with proper priority and fallback slots.
3. Add fixture coverage in `tests/fixtures/astock_providers/` — use real response samples.
4. Add opt-in live validation only when the provider supports it safely.
5. Record provider status in `ASTOCK_BLUEPRINT` and relevant docs.

### Phase 2: Schema & Normalization

1. Map provider-specific fields to unified `AStockRequest`/`AStockResponse` schema.
2. Handle NaN → None conversion in `DataCleaner`.
3. Preserve original field provenance where possible.

### Phase 3: Fallback & Error Handling

1. Define fallback chain in `router.py` — primary source → backup source → known failure.
2. Use `AStockSourceUnavailableError` for graceful degradation.
3. Never hard crash when a provider is unavailable — let the router try the fallback.

## Repo Anchors

- `tradingagents/astock/data_sources/adapters.py`
- `tradingagents/astock/data_sources/router.py`
- `tradingagents/astock/data_sources/schema.py`
- `tradingagents/astock/data_sources/cache.py`
- `tradingagents/astock/data_sources/errors.py`
- `planning/codebase/ASTOCK_PROVIDER_CONFIG.md`

## Guardrails

- Never hardcode credentials.
- Never bypass unified error semantics (`AStockNoDataError`, `AStockSourceUnavailableError`).
- Never add QMT execution logic in this layer.
- Never commit live API keys or tokens.
- Always treat third-party API responses as untrusted — validate at the adapter boundary.

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|------------|-----------|
| Hardcoded API key in adapter | Credential leak in git history | Always use env vars, never string literals |
| Missing NaN/None normalization | Downstream pandas operations crash | Run `DataCleaner` on all numeric fields |
| Inconsistent response schema between fixtures and live | Tests pass on fixtures, break in production | Run fixtured + live validation before merge |
| Provider error unhandled (raises bare exception) | Router can't fallback, whole chain crashes | Use `AStockSourceUnavailableError` for provider errors |
| New provider not registered in blueprint | UI/dispatch layer doesn't know about it | Update `ASTOCK_BLUEPRINT` in the same PR |

## Red Flags

- Provider adapter without fixture coverage
- Provider throws raw exception instead of `AStockSourceUnavailableError`
- Response normalization differs from the previously established schema
- Prod credentials visible in source code or git diff
- New provider registered in `adapters.py` but not in `router.py` fallback chain
- `akshare` / `mootdx` adapter uses a deprecated API version

## Verification

After completing provider work:

- [ ] Adapter tests pass: `pytest tests/test_astock_data_sources.py -q -k <provider>`
- [ ] Fixture tests pass: `pytest tests/test_astock_provider_fixtures.py -q`
- [ ] Live validation runs (if opt-in): `pytest tests/test_astock_live_providers.py -q -k <provider>`
- [ ] Provider registered in `router.py` fallback chain
- [ ] Blueprint updated with new provider capability
- [ ] No credentials in source code (check `git diff --cached`)
- [ ] Error semantics use unified exception classes
- [ ] NaN values cleaned — `DataCleaner` applied

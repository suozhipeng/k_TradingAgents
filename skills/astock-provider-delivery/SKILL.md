---
name: astock-provider-delivery
description: Use for A-share provider implementation and maintenance, including akshare, Tencent, cninfo, mootdx, iwencai, fixtures, live validation, config handling, and fallback semantics in TradingAgents.
---

# A-Stock Provider Delivery

Use this skill for any work below `tradingagents.astock.data_sources`.

## Scope

- Provider adapters
- Response normalization
- Field provenance
- Fixture/live provider validation
- Env-var based configuration

## Workflow

1. Update or add provider behavior inside `tradingagents/astock/data_sources/`.
2. Preserve router, schema, cache, and fallback contracts.
3. Add fixture coverage first.
4. Add opt-in live validation only when the provider supports it safely.
5. Record provider status in the blueprint and docs.

## Repo anchors

- `tradingagents/astock/data_sources/adapters.py`
- `tradingagents/astock/data_sources/router.py`
- `tradingagents/astock/data_sources/schema.py`
- `planning/codebase/ASTOCK_PROVIDER_CONFIG.md`

## Guardrails

- Never hardcode credentials.
- Never bypass unified error semantics.
- Never add QMT execution logic in this layer.

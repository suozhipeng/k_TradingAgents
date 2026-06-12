# Phase 01: Provider Routing

## Metadata

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `fa46b09`, `9c6cfec`

## Product objective

Provide read-only A-share data access with deterministic routing, fallback,
cache, and normalized error semantics.

## Delivered

- Provider adapters and router.
- Symbol normalization.
- History, snapshot, and summary cache buckets.
- Fixture and opt-in live provider tests.

## Evidence

- `tradingagents/astock/data_sources/`
- `tests/test_astock_data_sources.py`
- `tests/test_astock_provider_fixtures.py`
- `planning/codebase/ASTOCK_PROVIDER_CONFIG.md`

## Remaining risk

Live verification depends on optional packages, network access, and iwencai
credentials.

## Next entry criteria

Expose all five layers as a stable capability matrix.

# Phase 01：Provider 路由

## 元数据

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `fa46b09`, `9c6cfec`

## 产品目标

Provide read-only A-share data access with deterministic routing, fallback,
cache, and normalized error semantics.

## 已交付

- Provider adapters and router.
- Symbol normalization.
- History, snapshot, and summary cache buckets.
- Fixture and opt-in live provider tests.

## 证据

- `tradingagents/astock/data_sources/`
- `tests/test_astock_data_sources.py`
- `tests/test_astock_provider_fixtures.py`
- `planning/codebase/ASTOCK_PROVIDER_CONFIG.md`

## 剩余风险

Live verification depends on optional packages, network access, and iwencai
credentials.

## 下一入口条件

Expose all five layers as a stable capability matrix.

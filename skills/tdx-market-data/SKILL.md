---
name: tdx-market-data
description: "Use for Hermes-managed Tongdaxin market data integration in TradingAgents-Astock: pytdx online quotes, local vipdoc files, CSV/SQLite cache, and consumers including TradingAgents, Obsidian, and backtest modules."
version: 0.1.0
platforms: [linux, macos, windows]
related_skills: [tradingagents-core, astock-provider-delivery, astock-rollout-orchestrator, ecc-self-test]
---

# TDX Market Data

Project-local skill for Tongdaxin data ingestion and distribution.

## When to Use

Load this skill after `tradingagents-core` when work touches:

- `pytdx` online market quotes.
- Tongdaxin local `vipdoc` files.
- Local CSV / SQLite cache for A-share market data.
- Feeding TDX data into TradingAgents research, WebUI, Strategy Lab, backtests, or Obsidian notes.
- Provider fallback, freshness, cache provenance, or TDX data validation.

## Target Chain

```text
Hermes
  -> tdx-market-data skill
     -> pytdx online quotes
     -> Tongdaxin local vipdoc files
     -> local CSV / SQLite cache
     -> TradingAgents / Obsidian / backtest modules
```

## Boundaries

- Treat TDX data as market data only. Do not mix it with QMT order or account execution.
- Keep QMT / miniQMT under `Trading & Execution`; keep TDX market data under `Data & Ops`.
- All outputs must include source, freshness, cache state, and degraded/stale flags where possible.
- Do not silently replace live quotes with stale cache. Mark fallback explicitly.
- Do not write generated cache files into git unless they are tiny deterministic fixtures.

## Preferred Provider Order

Use this order unless a phase says otherwise:

1. `pytdx` online quote or kline request.
2. Local Tongdaxin `vipdoc` history files.
3. Local CSV cache.
4. Local SQLite cache.
5. Existing A-stock provider fallback chain.

## Implementation Checklist

- Define the configured TDX root and cache root through env/config, not hard-coded user paths.
- Normalize symbols to the project A-stock symbol schema.
- Record provenance: provider, file path or host, timestamp, period, adjustment mode, and fallback reason.
- Validate OHLCV schema before exposing data to research or backtest consumers.
- Add stale/degraded handling for missing pytdx server, missing vipdoc files, parse errors, and cache misses.
- Add tests with small fixtures; live TDX checks must be opt-in.

## Consumer Contracts

| Consumer | Requirement |
|---|---|
| TradingAgents research | Read through A-stock data interface/router, not direct file reads |
| WebUI / Dashboard | Show source, updated_at, stale/degraded state |
| Strategy Lab / Backtest | Require deterministic data snapshot or cache key |
| Obsidian | Export summarized market snapshots or links, not large raw datasets |


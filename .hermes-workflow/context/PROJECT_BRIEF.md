# TradingAgents xg_dev Recovery

- Source of truth: `docs/TradingAgents_xg_dev_修复与Hermes低Token自动化实施方案_V1.5.md`
- Release target: `0.3.3`
- Source branch: `xg_dev`
- Integration branch: `fix/xg-dev-data-loop-v033`
- Integration worktree: `.worktrees/xg-integration`
- Phase order: PR-1 → PR-2 → PR-3 → PR-4 → PR-5 → PR-5A → PR-5B → PR-6
- One implementation worker at a time.

## Product path

Install → Provider health → normalize/quality gate → transactional upsert → Canonical DuckDB → Dashboard/K-line → market review → stock analysis → canonical A-share backtest → restart persistence.

## Canonical business database

`~/.tradingagents/astock/astock.duckdb`

No second K-line database, no SQLite/DuckDB business dual-write, no implicit mock, and no Provider call from backtest.

## Frozen scope

QMT, paper trading, automatic trading, PostgreSQL, TimescaleDB, ClickHouse, SSE, Scheduler, Notifications, Alerts, multi-user/RBAC, multi-worker deployment, new Providers and unrelated pages.

## Roles

DeepSeek: orchestration, small patches and deterministic scripts. Agnes: main implementation and ordinary review. Codex: high-risk Gate and independent Acceptance. Scripts: Git, tests, database and Evidence checks.

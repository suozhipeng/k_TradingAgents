# Repository Map

## Runtime

- `tradingagents/astock/api/`: Flask app factory, hooks, health, dashboard, market data, data jobs, ingest, analysis and backtest routes.
- `tradingagents/astock/data_sources/`: Provider adapters, router, normalization and source metadata.
- `tradingagents/astock/store/`: DuckDB schema, backend, jobs and repositories; existing PostgreSQL files are outside local-release scope.
- `tradingagents/astock/web/`: Jinja2 blueprints, templates and static JS.
- `tradingagents/astock/execution/`: frozen execution boundary; do not expand during recovery.
- `scripts/run_astock_api.py`: local Web entry point.

## Existing anchors verified during preflight

- `tradingagents/astock/api/__init__.py`: app factory and local-release configuration.
- `tradingagents/astock/api/app_hooks.py`: research-only/local-release request guards.
- `tradingagents/astock/api/routes_health.py`: `/api/v1/health`, `/api/v1/health/live`, `/api/v1/health/ready`.
- `tradingagents/astock/api/routes_dashboard.py`: `/api/v1/dashboard/overview`.
- `tradingagents/astock/api/routes_data_jobs.py`: data refresh job endpoints.
- `tradingagents/astock/api/routes_data_query.py`: K-line and market data queries.
- `tradingagents/astock/api/routes_backtest.py`: existing backtest endpoints; PR-5B must bind them to Canonical DuckDB.
- `tradingagents/astock/store/backend.py`: current DB path/mock configuration seam.
- `tradingagents/astock/store/schema.py` and `schema_defs.py`: DuckDB schema anchors.
- `tests/`: 1252 tests collected with project Python when Hermes `PYTHONPATH` is removed.

## Existing first-run gap to verify

Current code has data-health, data-job and dashboard endpoints, but the V1.5 Setup/Data Hub/Market Review/Stock Analysis contracts are not yet present. Implement only the phase contract's files and verify each phase before expanding.

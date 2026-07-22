# Deterministic Quality Gates

1. `git status --short` and `git rev-parse HEAD` recorded before every task.
2. Changed paths match the Task Contract; one implementation task only; max 8 production files.
3. `git diff --check` passes.
4. Project commands run with `env -u PYTHONPATH -u PYTHONHOME .venv/bin/python -m ...` because Hermes desktop injects its own Python 3.11 paths.
5. `ASTOCK_LOCAL_RELEASE=true` remains research-only; execution/QMT/paper/scheduler boundaries stay blocked.
6. `ASTOCK_MOCK_DATA_ENABLED` defaults false. Any mock response must be explicit and tagged `source=mock`, `quality=mock`, `is_real_data=false`.
7. Canonical DB is exactly `~/.tradingagents/astock/astock.duckdb`; no second business DB.
8. Real data ordering is Raw → Normalize → Core Quality Gate → per-symbol transaction Upsert → post-write verification.
9. Repeated Bootstrap/review/analysis/backtest operations are idempotent and leave no duplicate primary keys.
10. Every successful phase writes machine Evidence containing `base_sha`, `head_sha`, commands, exit codes and no blockers.
11. Review is diff-only; Acceptance is read-only and independent.
12. Do not mark a phase complete from natural-language output. Controller accepts only valid Evidence and matching Git SHA.

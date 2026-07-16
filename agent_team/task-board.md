# A-share local workbench recovery

## Completed and adopted

- Database health probe — serialized DuckDB access, migration discovery and backend configuration precedence.
- Backend diagnosis — app-scoped scheduler/services and safe background-job shutdown.
- Web diagnosis — canonical API routes, envelope parsing and local-release-safe controls.
- Storage and data-job concurrency audit — protected DuckDB query/result lifecycles, job admission/shutdown, and TDX cache access.
- API, scheduler, and lifecycle concurrency audit — app-scoped runtime state, request-drain shutdown, and scheduler-cycle coordination.
- Local-release verification — explicit Pydantic/Parquet dependencies and a real browser smoke gate.
- Shutdown deadline — bounded executor drain that keeps the store open when a provider thread is stuck.
- Provider preflight — reproducible credentials/configuration checks and read-only live-provider probes.

## Reserved

- One retry or escalation slot.
- One lead-agent integration and verification slot.

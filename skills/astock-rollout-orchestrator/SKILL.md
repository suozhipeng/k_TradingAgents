---
name: astock-rollout-orchestrator
description: Use for staging Hermes work across ECC general skills and A-share delivery skills, selecting the correct phase, sequencing validation, and writing durable rollout notes into docs for TradingAgents.
---

# A-Stock Rollout Orchestrator

Use this skill when a task spans planning, implementation, validation, and project documentation.

## Dispatch rule

1. Choose one A-stock delivery skill for the implementation surface.
2. Choose one ECC skill for review or validation.
3. Sequence work by phase; do not mix later-phase wiring into earlier-phase tasks.

## Phase map

- Phase 3: interface, tools, analyst
- Phase 4: research chain
- Phase 5: research runtime verification
- Phase 6: research-only production entry dispatch
- Phase 7: display schema and CLI
- Phase 8: read-only UI and multi-market viewer
- Phase 9: trader, risk, and portfolio-manager adaptation
- Phase 10: backtest and paper trading
- Phase 11: QMT read-only to controlled execution

## Documentation rule

Write durable outcomes to `docs/phases/`, not only to chat:

- phase objective
- product decisions and scope boundary
- files changed
- tests run
- known gaps
- next phase entry criteria
- final commit SHA

Use `docs/phases/TEMPLATE.md`. A phase cannot be marked complete or handed off
until its archive entry and `docs/phases/README.md` index are updated.

## Repo anchor

- `docs/HERMES_SKILLS_PLAYBOOK.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
- `docs/phases/README.md`

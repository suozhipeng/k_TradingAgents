---
name: astock-rollout-orchestrator
description: "Use for staging Hermes work across ECC general skills and A-share delivery skills, selecting the correct phase, sequencing validation, and writing durable rollout notes into docs for TradingAgents."
version: 1.1.0
platforms: [linux, macos]
related_skills: [astock-analyst-delivery, astock-provider-delivery, ecc-readonly-review, ecc-self-test]
---

# A-Stock Rollout Orchestrator

Use this skill when a task spans planning, implementation, validation, and project documentation.

## When to Use

- Starting a new phase rollout
- Task touches both A-stock delivery and ECC review/test skill
- Need to write durable phase documentation
- Deciding which phase boundary applies to a feature

## Dispatch Rule

1. Choose one A-stock delivery skill for the implementation surface.
2. Choose one ECC skill for review or validation.
3. Sequence work by phase; do not mix later-phase wiring into earlier-phase tasks.

## Phase Decision Tree

```
Is this about provider implementation or data source?
  ├── YES → astock-provider-delivery + ecc-self-test
  │
  └── NO → Is this about interface/tools/analyst wiring?
       ├── YES → astock-analyst-delivery + ecc-self-test
       │
       └── NO → Is this about rollout planning/review?
            └── YES → astock-rollout-orchestrator + ecc-readonly-review
```

## Phase Map

| Phase | Focus | Skills | Validation |
|-------|-------|--------|-----------|
| 3 | Interface, tools, analyst | `astock-analyst-delivery` + `ecc-self-test` | Fixture-based test pass |
| 4 | Research chain | `astock-rollout-orchestrator` + `ecc-readonly-review` | Architecture consistency |
| 5 | Research runtime verification | `astock-rollout-orchestrator` + `ecc-self-test` | Test pass + live validation |
| 6 | Research-only production dispatch | `astock-rollout-orchestrator` + `ecc-self-test` | Smoke pass |
| 7 | Display schema + CLI | `astock-rollout-orchestrator` + `ecc-readonly-review` | CLI manual check |
| 8 | Read-only UI + multi-market | `astock-rollout-orchestrator` + `ecc-readonly-review` | UI consistency |
| 9 | Trader/risk/portfolio adaptation | `astock-rollout-orchestrator` + `ecc-self-test` | Integration test pass |
| 10 | Backtest + paper trading | `astock-rollout-orchestrator` + `ecc-self-test` | Regression pass |
| 11 | QMT controlled execution | `astock-rollout-orchestrator` + `ecc-self-test` | Safety+regression pass |
| 12+ | Store/API/optimization | `astock-rollout-orchestrator` + `ecc-self-test` | Per-module regression |

## Documentation Rule

Write durable outcomes to `docs/phases/`, not only to chat:

- Phase objective
- Product decisions and scope boundary
- Files changed (with paths)
- Tests run (exact commands)
- Known gaps and unresolved risks
- Next phase entry criteria
- Final commit SHA

Use `docs/phases/TEMPLATE.md`. A phase cannot be marked complete or handed off until its archive entry and `docs/phases/README.md` index are updated.

## Documentation Flow

```
task complete → write phase archive in docs/phases/
             → update docs/ASTOCK_CURRENT_STATUS.md
             → update docs/phases/README.md index
             → commit all docs together with code
```

## Common Anti-Patterns

| Anti-Pattern | Problem |
|---|---|
| Writing later-phase wiring in an earlier-phase task | Causes rework when earlier assumptions change |
| Skipping phase archive thinking "we'll document later" | Context is lost; next agent can't pick up |
| Merging astock-provider-delivery with astock-analyst-delivery in a single task | Blurs provider vs. interface responsibility |
| Marking phase complete without Codex review | Review gate is load-bearing; phase is not complete |
| Phase docs written after commit (not alongside code) | Easy to forget details; docs diverge from code |

## Rollback Triggers

- ECC review returns `fail` with blocking bug
- Live provider validation reveals schema mismatch
- Phase boundary violation detected (wiring future-phase logic now)
- Test suite regression that affects previously passing modules

## Red Flags

- Phase archive written but no Codex acceptance
- Implementation in one PR spans multiple phases
- Docs/phases not updated before moving to next phase
- Phase objective does not match `ASTOCK_CURRENT_STATUS.md`
- Non-blocking review findings ignored without documentation

## Repo Anchors

- `docs/HERMES_SKILLS_PLAYBOOK.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
- `docs/phases/README.md`
- `docs/phases/TEMPLATE.md`

## Verification

After a rollout cycle:

- [ ] Phase archive written to `docs/phases/phase-N-*.md`
- [ ] `docs/phases/README.md` index updated
- [ ] `docs/ASTOCK_CURRENT_STATUS.md` reflects new phase status
- [ ] Codex review accepted (`accept` or `partial` with documented gaps)
- [ ] ECC validation passed (review or self-test)
- [ ] Commit SHA recorded in phase archive
- [ ] Next phase entry criteria documented
- [ ] No code from a future phase leaked into this PR

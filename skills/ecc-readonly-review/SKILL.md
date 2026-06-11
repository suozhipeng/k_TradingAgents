---
name: ecc-readonly-review
description: Use for static codebase review, module coverage checks, architecture-to-implementation consistency, planning drift detection, and read-only acceptance review in this TradingAgents repo.
---

# ECC Readonly Review

Use this skill when the task is to inspect, review, compare, or accept work without changing runtime behavior first.

## Scope

- Read `planning/codebase/` and `planning/review/` before judging drift.
- Compare code, docs, tests, and WebUI/static artifacts.
- Prioritize findings: blocking bug, behavior risk, missing test, documentation drift.

## Workflow

1. Inspect the relevant source files and the matching planning/review docs.
2. Check whether the implementation matches the declared phase boundary.
3. Confirm whether tests exist for the changed surface.
4. Produce a concise verdict: `pass`, `partial`, or `fail`, with evidence.

## Repo anchors

- `planning/review/ECC_REVIEW.md`
- `planning/review/SELF_TEST_REPORT.md`
- `planning/codebase/ARCHITECTURE.md`
- `planning/codebase/TASKS.md`

## Output shape

- What was checked
- Result
- Evidence
- Open risks
- Next required step

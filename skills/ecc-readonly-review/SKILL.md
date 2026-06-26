---
name: ecc-readonly-review
description: "Use for static codebase review, module coverage checks, architecture-to-implementation consistency, planning drift detection, and read-only acceptance review in this TradingAgents repo."
version: 1.1.0
platforms: [linux, macos]
related_skills: [ecc-self-test, astock-rollout-orchestrator, code-reviewer]
---

# ECC Readonly Review

Use this skill when the task is to inspect, review, compare, or accept work without changing runtime behavior first.

## When to Use

- After a phase implementation is merged — verify architecture consistency
- Before self-test — check scope boundary and code quality
- Detecting planning drift: does the implementation match the declared phase boundary?
- Module coverage check: are all planned modules implemented?
- Read-only acceptance: does the artifact pass before Codex review?

## Scope

- Read `planning/codebase/` and `planning/review/` before judging drift.
- Compare code, docs, tests, and WebUI/static artifacts.
- Prioritize findings: blocking bug > behavior risk > missing test > documentation drift.

## Finding Severity Levels

| Level | Label | Meaning | Action |
|-------|-------|---------|--------|
| P0 | Blocking | Breaking bug or security issue | Must fix before merge |
| P1 | High | Behavior risk or missing critical test | Fix recommended before merge |
| P2 | Medium | Missing test or minor inconsistency | Fix in same or next PR |
| P3 | Low | Documentation drift or style | Fix when convenient |

## Workflow

### Step 1: Gather Context

1. Read the relevant planning docs: `planning/codebase/ARCHITECTURE.md`, `planning/codebase/TASKS.md`.
2. Check the phase archive in `docs/phases/` for the declared scope.
3. Read `docs/ASTOCK_CURRENT_STATUS.md` for current baseline.

### Step 2: Inspect Implementation

1. Walk the changed files — focus on the diff, not the full file.
2. Compare against the declared phase boundary:
   - Does the implementation stay within scope?
   - Does it leak future-phase logic or UI wiring?
3. Check test coverage for the changed surface.

### Step 3: Produce Verdict

A concise verdict with evidence:

```
Verdict: [pass | partial | fail]

What was checked:
- [area 1]: [finding] → [severity]
- [area 2]: [finding] → [severity]

Evidence:
- [file:line] — [quote or observation]

Open risks:
- [risk description]

Next required step:
- [action to unblock]
```

## Common Biases to Watch For

| Bias | Trap | Correction |
|------|------|-----------|
| Confirmation bias | Finding only what you expect to find | Actively look for violations of the declared scope |
| Familiarity blindness | Overlooking issues in code you've seen before | Treat each review as if seeing it fresh |
| Authority deference | Not questioning patterns written by a previous phase | Patterns can be wrong — flag drift regardless of origin |
| Scope creep acceptance | "Close enough" to phase boundary | Phase boundary is a contract — deviation must be documented |

## Repo Anchors

- `planning/review/ECC_REVIEW.md`
- `planning/review/SELF_TEST_REPORT.md`
- `planning/codebase/ARCHITECTURE.md`
- `planning/codebase/TASKS.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

## Output Shape

- What was checked
- Result (`pass`, `partial`, or `fail`)
- Evidence (file paths, line numbers, quotes)
- Open risks
- Next required step

## Red Flags

- Implementation adds code outside the declared phase scope
- Planning docs reference modules that don't exist in code
- Tests cover less than 50% of the changed surface
- Implementation contradicts `planning/codebase/ARCHITECTURE.md`
- Phase archive status doesn't match actual implementation
- No `docs/ASTOCK_CURRENT_STATUS.md` update accompanying the change

## Verification

After completing a review:

- [ ] Verdict recorded: `pass`, `partial`, or `fail` with evidence
- [ ] Scope boundary verified — no future-phase code leaked
- [ ] Test coverage assessed for the changed surface
- [ ] Planning drift detected and documented
- [ ] Open risks identified with severity levels
- [ ] Next step communicated (fix, test, or escalate)

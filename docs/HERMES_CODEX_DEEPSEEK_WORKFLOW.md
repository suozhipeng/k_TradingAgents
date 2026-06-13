# Hermes, Codex, DeepSeek Workflow

This document defines the operating contract for this repository when Hermes,
Codex, and DeepSeek collaborate on phased delivery.

## Goal

Use one controller, one coder, and one reviewer:

- `Hermes`: project manager, dispatcher, and phase owner
- `DeepSeek`: code implementation worker
- `Codex`: independent review, correction, and acceptance gate

This separation is mandatory for non-trivial project work. The same agent must
not both implement and self-accept a phase conclusion without an explicit
Codex review pass.

## Role boundaries

### Hermes

Hermes owns:

- phase selection and sequencing
- task decomposition
- scope and out-of-scope boundary
- assignment to repo-local skills
- progress tracking and next-step scheduling
- packaging the coding brief for DeepSeek
- collecting changed files, test evidence, and open risks
- updating durable phase artifacts after Codex acceptance

Hermes must not:

- skip the ECC review gate for meaningful code changes
- mark a phase complete from chat-only confidence
- reopen a later phase while the current phase still has blocking review gaps

### DeepSeek

DeepSeek owns:

- code edits inside the current Hermes phase boundary
- local implementation notes
- returning exact changed files
- returning commands run and raw pass/fail outcomes
- surfacing uncertainty instead of silently widening scope

DeepSeek must not:

- redefine the product boundary
- claim phase completion without test evidence
- bypass Codex review by treating self-tests as final acceptance

### Codex

Codex owns:

- validating the Hermes task split before or during implementation
- checking whether the coding plan matches the active phase
- reviewing changed files and claimed conclusions
- judging whether tests are sufficient for the changed surface
- detecting scope drift, unsupported assumptions, and documentation mismatch
- issuing `accept`, `partial`, or `fail`
- forcing rework when the implementation evidence does not support the claim

Codex should prioritize:

1. blocking bug or incorrect conclusion
2. scope drift or product-boundary violation
3. missing regression coverage
4. documentation drift

## Required execution loop

1. Hermes selects the phase and loads the relevant skills.
   For cross-phase A-share work, start with `astock-rollout-orchestrator`.
2. Hermes writes a coding brief for DeepSeek.
   The brief must include:
   - objective
   - included scope
   - excluded scope
   - exact target files or module area
   - tests to run
   - acceptance criteria
   - required docs updates
3. DeepSeek implements only the scoped work and returns:
   - changed files
   - key behavior changes
   - tests run
   - pass/fail/skip results
   - open risks and assumptions
4. Codex performs the review gate using `ecc-readonly-review` or
   `ecc-self-test`, depending on whether the acceptance is static or
   execution-based.
5. If Codex returns `partial` or `fail`, Hermes must create a correction brief
   and send it back to DeepSeek.
6. Only after Codex returns `accept` may Hermes:
   - update `docs/phases/`
   - update `docs/phases/README.md`
   - update `docs/ASTOCK_CURRENT_STATUS.md` if repo status changed
   - commit the approved changes to the Git repository
   - record the final commit SHA

## Codex review gate

Codex review is required when any of the following is true:

- Python source changed
- tests changed
- docs claim a phase result is complete
- a phase archive is being updated
- a runtime or schema contract changed
- a provider or execution boundary changed

Codex must produce a compact verdict with:

- what was checked
- result: `accept`, `partial`, or `fail`
- evidence
- open risks
- next required step

## Handoff format

### Hermes -> DeepSeek

```text
Phase:
Objective:
Included scope:
Excluded scope:
Files/modules:
Tests to run:
Acceptance criteria:
Docs to update:
Return format:
```

### DeepSeek -> Codex

```text
Changed files:
Behavior summary:
Tests run:
Results:
Open risks:
Assumptions:
```

### Codex -> Hermes

```text
Review scope:
Verdict: accept | partial | fail
Evidence:
Drift or defects:
Required corrections:
```

## Direct Hermes command pattern

Hermes is installed on this machine and currently reports:

- provider: `DeepSeek`
- model: `deepseek-v4-flash`

Recommended command shape for this repo:

```bash
hermes chat -q "Phase objective here. Follow AGENTS.md and docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md. Use astock-rollout-orchestrator for phase control, use DeepSeek for coding, and prepare output for Codex review before phase acceptance." \
  --skills astock-rollout-orchestrator,ecc-readonly-review
```

When the task is implementation-heavy and requires regression execution:

```bash
hermes chat -q "Implement the scoped phase work only. Follow AGENTS.md and docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md. Return changed files, tests, risks, and unresolved assumptions for Codex review." \
  --skills astock-rollout-orchestrator,ecc-self-test
```

## Repo-specific rules

- The canonical phase archive remains `docs/phases/`.
- `docs/HERMES_SKILLS_PLAYBOOK.md` remains the top-level skill dispatch
  contract.
- `docs/ASTOCK_CURRENT_STATUS.md` remains the current factual repo baseline.
- A phase may not be closed on DeepSeek output alone.
- A phase may not be closed on Hermes narration alone.
- Codex review evidence is part of the acceptance path, not an optional extra.
- After Codex accepts a committable change set with no blocking issues, Hermes
  must create the Git commit before handoff.

## Correction policy

If Codex rejects the current result, Hermes must explicitly state:

- which conclusion was unsupported
- which files or tests were insufficient
- whether the issue is scope drift, missing implementation, or weak evidence
- what exact correction DeepSeek must make next

Do not continue to the next phase until the rejected issue is either corrected
or explicitly re-scoped by the human owner.

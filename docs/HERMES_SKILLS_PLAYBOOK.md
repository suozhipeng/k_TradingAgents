# Hermes Skills Playbook

This document is the repo-local dispatch contract for Hermes.

## Goal

Use a stable two-class skill model:

- ECC general skills for review and validation
- A-stock skills for A-share feature delivery

## Installed repo-local skills

### ECC general

- `ecc-readonly-review`
- `ecc-self-test`

### A-stock dedicated

- `astock-provider-delivery`
- `astock-analyst-delivery`
- `astock-rollout-orchestrator`

## Dispatch policy

### Step 1: load existing ECC general skills

Use ECC skills when the task is:

- read-only acceptance
- drift review
- module coverage check
- regression execution
- self-test reporting

### Step 2: load A-stock dedicated skills

Use A-stock skills when the task is:

- provider implementation or validation
- AStockInterface or tool wiring
- analyst integration
- staged A-share rollout work

### Step 3: let Hermes schedule both classes

When a task contains both delivery and acceptance:

1. Start with `astock-rollout-orchestrator`
2. Route implementation into one A-stock skill
3. Route review or regression into one ECC skill
4. Return a phase result with:
   - changed files
   - tests run
   - open risks
   - next entry condition

Hermes is the project manager for this routing layer. By default in this repo:

- `Hermes` owns phase scheduling, task decomposition, and progress control
- `DeepSeek` is the default coding engine used by Hermes
- `Codex` is the independent review gate for decomposition quality, coding
  conclusion verification, and drift correction

See `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` for the full operating loop.

### Step 4: persist durable results

Persist outcomes into `docs/phases/`:

- update this playbook when the skill inventory changes
- create or update one archive file for every phase
- use `docs/phases/TEMPLATE.md`
- update `docs/phases/README.md` and `docs/ASTOCK_CURRENT_STATUS.md`
- include the final commit SHA or mark it `pending` until the next checkpoint
- keep chat-only conclusions out of the critical path

No phase may be marked complete or handed off without a local archive record.

## Acceptance governance

- Do not accept a phase based only on DeepSeek self-report.
- Use `ecc-readonly-review` when the main question is correctness, drift, or
  scope compliance.
- Use `ecc-self-test` when the main question is regression execution and result
  triage.
- Codex should issue `accept`, `partial`, or `fail` before Hermes updates the
  phase archive to `complete`.

## Current phase mapping

- Phase 3: `astock-analyst-delivery` + `ecc-self-test`
- Phase 4: `astock-rollout-orchestrator` + `ecc-readonly-review`
- Phase 5: `astock-rollout-orchestrator` + `ecc-self-test`
- Phase 6: `astock-rollout-orchestrator` + `ecc-self-test`
- Phase 7: `astock-rollout-orchestrator` + `ecc-readonly-review`
- Phase 8: `astock-rollout-orchestrator` + `ecc-readonly-review`
- Phase 9: `astock-rollout-orchestrator` + `ecc-self-test`
- Phase 10: `astock-rollout-orchestrator` + `ecc-self-test`
- Phase 11: `astock-rollout-orchestrator` + `ecc-self-test`

The canonical phase scope and completion status are maintained in
`docs/ASTOCK_CURRENT_STATUS.md`.

## Current repo boundary

- Keep `tradingagents/dataflows/interface.py` intact unless a phase explicitly requires broader migration.
- Keep all A-share outputs non-actionable until controlled execution is explicitly delivered in Phase 11.
- Do not treat `final_trade_decision` from the current A-share bridge as an executable signal.
- Keep QMT as read-only or placeholder until Phase 11.
- Use `docs/phases/` as the canonical milestone archive.
- Use `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` as the canonical repo-level
  collaboration contract for controller, coder, and reviewer separation.

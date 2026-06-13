<!-- agent-ninja-START -->
## Agent Skills

Project-local skills are installed in `skills/` and should be treated as the default Hermes playbook for this repo.

### ECC General Skills

- `ecc-readonly-review`
  Use for static review, module coverage checks, WebUI/codebase consistency checks, and read-only acceptance gates.
- `ecc-self-test`
  Use for local validation, regression execution, result triage, and producing concise acceptance reports.

### A-Stock Skills

- `astock-provider-delivery`
  Use for A-share provider implementation, fixture/live provider validation, config hardening, and fallback semantics.
- `astock-analyst-delivery`
  Use for wiring `AStockInterface -> tools -> analyst`, structured section outputs, and analyst-facing tests.
- `astock-rollout-orchestrator`
  Use when Hermes needs to choose between ECC general skills and A-stock delivery skills, stage work, and write phase outputs to `docs/`.

### Hermes Dispatch Rule

1. For review / acceptance / regression tasks, start with ECC skills.
2. For A-share feature delivery, start with the matching A-stock skill.
3. For cross-phase work, invoke `astock-rollout-orchestrator` first, then route into one ECC skill and one A-stock skill.
4. Write durable project findings into `docs/HERMES_SKILLS_PLAYBOOK.md` or adjacent `docs/` artifacts, not transient chat only.
5. Every Delivery Phase must be recorded under `docs/phases/` before handoff and Git commit.
6. A phase archive must include scope, product decisions, implementation evidence, tests, risks, next entry criteria, and commit SHA.

### Role Contract

- `Hermes` is the project manager and dispatcher.
  Hermes owns phase sequencing, task decomposition, scope boundary, handoff packaging, and progress tracking for the whole repo.
- `Codex` is the independent reviewer and correction gate.
  Codex owns task-breakdown review, implementation conclusion verification, drift detection, regression judgment, and forcing rework when evidence is weak.
- `DeepSeek` is the implementation engine used by Hermes for coding by default.
  DeepSeek should change code only within the current Hermes phase boundary and must return changed files, tests, open risks, and unresolved assumptions.

### Required Loop

1. Hermes defines or updates the current phase objective, scope, exclusions, acceptance tests, and deliverables.
2. Hermes dispatches coding work to DeepSeek with the relevant repo-local skills.
3. Codex reviews the task split, changed files, test evidence, and product conclusion before the phase is accepted.
4. If Codex finds drift, missing tests, or unsupported conclusions, the task returns to Hermes for re-planning and DeepSeek rework.
5. Only after Codex acceptance may Hermes mark the phase complete, update `docs/phases/`, commit the approved changes to the Git repository, and then hand off.

See `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` for the durable operating procedure.

<!-- agent-ninja-END -->

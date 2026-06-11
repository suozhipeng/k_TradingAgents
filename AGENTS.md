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

<!-- agent-ninja-END -->

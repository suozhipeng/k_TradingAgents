<!-- agent-ninja-START -->
## Agent Skills

Installed project-local skills:

- `.agents/skills/codex-model-routing-team`: bounded, model-routed background
  work for complex and genuinely parallel tasks.

## Codex background model-routing authorization

- The user authorizes Codex to use `$codex-model-routing-team` automatically
  for complex, parallelizable tasks, create independent background tasks, and
  assign a model and reasoning level to each task. Before dispatch, briefly
  state the number of tasks, model, reasoning level, and responsibility. No
  additional confirmation is required.
- The lead agent keeps its current model and owns planning, file ownership,
  integration, verification, and final delivery.
- Run at most 6 background tasks concurrently and create at most 8 for one
  root task. Background tasks must not create more background tasks or
  subagents.
- Background tasks must not use Ultra. Terra is excluded from automatic
  routing by default. If Codex App background-task tools are unavailable,
  complete the work locally and do not use MultiAgentV2 `spawn_agent` as a
  substitute for model routing.
- Do not auto-dispatch simple questions, status checks, small single-file
  edits, strongly sequential work, publishing, sending, payment, deletion,
  account, or production operations.

<!-- agent-ninja-END -->

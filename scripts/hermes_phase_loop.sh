#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE="continue"
EXTRA_INSTRUCTION=""

usage() {
  cat <<'EOF'
Usage:
  scripts/hermes_phase_loop.sh [--mode continue|refresh] [--extra "instruction"]

Purpose:
  Run Hermes in one-shot project-manager mode for this repository so Hermes can
  keep the active phase moving forward with minimal manual prompting.

Modes:
  continue   Default. Continue the current phase or phase-transition work.
  refresh    Refresh Hermes's understanding after rules/docs changed.

Output contract:
  Hermes must end in one of these states:
  - PHASE_ADVANCED
  - BLOCKED_ON_CODEX
  - BLOCKED_ON_HUMAN_INPUT
  - BLOCKED_ON_ENVIRONMENT
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --extra)
      EXTRA_INSTRUCTION="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "${MODE}" in
  continue)
    MODE_INSTRUCTION="Continue the active phase or phase-transition work in this repository."
    ;;
  refresh)
    MODE_INSTRUCTION="Refresh the current project-management context using the latest repo rules and docs, then continue only if no new ambiguity remains."
    ;;
  *)
    echo "Unsupported mode: ${MODE}" >&2
    exit 2
    ;;
esac

read -r -d '' PROMPT <<EOF || true
${MODE_INSTRUCTION}

You are Hermes the project manager for the TradingAgents repository at:
${REPO_ROOT}

Mandatory rules:
- Follow AGENTS.md, docs/HERMES_SKILLS_PLAYBOOK.md, docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md, docs/phases/README.md, and docs/ASTOCK_CURRENT_STATUS.md.
- Treat the repo-local skills declared in AGENTS.md and docs/HERMES_SKILLS_PLAYBOOK.md as the project playbook even if Hermes global skill registry does not list those names explicitly.
- Use astock-rollout-orchestrator semantics for stage control.
- Use the narrow Hermes-only exception only for doc-only factual reconciliation.
- Do not imply or invent a Codex accept verdict.
- Do not change docs/phases/README.md status vocabulary unless the repo contract is explicitly changed first.
- If code or tests must change, package the work for DeepSeek instead of widening scope yourself.
- If a Codex gate is required, stop before acceptance and output BLOCKED_ON_CODEX with the exact review packet.
- If a human decision or credential is required, output BLOCKED_ON_HUMAN_INPUT or BLOCKED_ON_ENVIRONMENT.
- If you successfully move the phase forward without needing Codex or human input, output PHASE_ADVANCED.
- If all numbered phases in docs/phases/README.md are complete, do NOT stop only because there is no "Phase 12".
  In that case, automatically switch to backlog / maintenance mode and continue from the highest-priority documented gap in docs/ASTOCK_CURRENT_STATUS.md section 5 or other explicit repo TODO evidence.
- Only output BLOCKED_ON_HUMAN_INPUT when the next smallest action truly requires a human product decision, approval, missing credential, or an undocumented new scope.
- Treat branch drift as actionable project state:
  - if the branch is ahead of origin, mention the exact ahead count and whether pushing is the next smallest action
  - if there are uncommitted tracked changes, mention them explicitly
  - if there are untracked phase docs or implementation files, inspect whether they represent unfinished repo work before concluding the roadmap is complete
- Do not invent files, scripts, tests, commits, pushes, or environment facts.
  Every such claim must be grounded in locally verifiable repository evidence.
- Only reference repository files that actually exist in the current checkout.
- When discussing live environment verification, prefer the repo's existing
  script names and env checks as written in the checkout. Do not substitute
  imaginary helpers.
- When discussing credential gaps, distinguish between:
  - credential missing from the current process environment
  - credential missing from repo-local docs/examples
  - credential present but live network validation still unverified
  Do not collapse these into one statement.

Reasoning priority:
1. Active blocked phase work
2. Uncommitted or unpushed accepted work
3. Highest-priority documented gap (P0 before P1 before P2)
4. Only then human-defined new scope

Required output shape:
1. Current phase state
2. Next smallest action
3. Exact files involved
4. Whether DeepSeek is needed
5. Whether Codex is needed
6. Final status line containing exactly one of:
   PHASE_ADVANCED
   BLOCKED_ON_CODEX
   BLOCKED_ON_HUMAN_INPUT
   BLOCKED_ON_ENVIRONMENT

${EXTRA_INSTRUCTION}
EOF

cd "${REPO_ROOT}"
exec hermes --oneshot "${PROMPT}" --accept-hooks

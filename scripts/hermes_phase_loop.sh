#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ENV="${REPO_ROOT}/.env"
STATE_DIR="${REPO_ROOT}/.hermes"
RUN_DIR="${STATE_DIR}/runs"
HERMES_BIN="${HERMES_BIN:-}"

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

resolve_hermes_bin() {
  if [[ -n "${HERMES_BIN}" && -x "${HERMES_BIN}" ]]; then
    return 0
  fi

  local candidate=""
  candidate="$(command -v hermes 2>/dev/null || true)"
  if [[ -n "${candidate}" && -x "${candidate}" ]]; then
    HERMES_BIN="${candidate}"
    return 0
  fi

  for candidate in /Users/szp/.local/bin/hermes /opt/homebrew/bin/hermes /usr/local/bin/hermes; do
    if [[ -x "${candidate}" ]]; then
      HERMES_BIN="${candidate}"
      return 0
    fi
  done

  echo "Unable to locate hermes executable." >&2
  exit 127
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

if [[ -f "${REPO_ENV}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${REPO_ENV}"
  set +a
fi

mkdir -p "${RUN_DIR}"
resolve_hermes_bin

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

timestamp="$(date +"%Y%m%d-%H%M%S")"
tmp_output="$(mktemp)"

set +e
"${HERMES_BIN}" --oneshot "${PROMPT}" --accept-hooks >"${tmp_output}" 2>&1
hermes_rc=$?
set -e

cat "${tmp_output}"

latest_output="${STATE_DIR}/phase_loop_latest.txt"
run_output="${RUN_DIR}/${timestamp}.txt"
cp "${tmp_output}" "${latest_output}"
cp "${tmp_output}" "${run_output}"

terminal_state="$(
  grep -E '^(PHASE_ADVANCED|BLOCKED_ON_CODEX|BLOCKED_ON_HUMAN_INPUT|BLOCKED_ON_ENVIRONMENT)$' "${tmp_output}" | tail -n 1 || true
)"

printf 'timestamp=%s\nmode=%s\nstatus=%s\n' "${timestamp}" "${MODE}" "${terminal_state:-UNKNOWN}" > "${STATE_DIR}/phase_loop_status.env"

case "${terminal_state}" in
  BLOCKED_ON_CODEX)
    cp "${tmp_output}" "${STATE_DIR}/codex_review_request.md"
    rm -f "${STATE_DIR}/human_input_request.md"
    ;;
  BLOCKED_ON_HUMAN_INPUT|BLOCKED_ON_ENVIRONMENT)
    cp "${tmp_output}" "${STATE_DIR}/human_input_request.md"
    rm -f "${STATE_DIR}/codex_review_request.md"
    ;;
  PHASE_ADVANCED)
    rm -f "${STATE_DIR}/codex_review_request.md" "${STATE_DIR}/human_input_request.md"
    ;;
esac

rm -f "${tmp_output}"

if [[ -n "${terminal_state}" ]]; then
  exit 0
fi

exit "${hermes_rc}"

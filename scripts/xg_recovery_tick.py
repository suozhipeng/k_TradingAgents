#!/usr/bin/env python3
"""Deterministic xg_dev recovery controller.

This controller never edits production code, Acceptance evidence, or the Kanban DB
in dry-run mode. It reports machine-checkable preflight/control state only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PHASES = ("PR-1", "PR-2", "PR-3", "PR-4", "PR-5", "PR-5A", "PR-5B", "PR-6")
REQUIRED_WORKFLOW_FILES = (
    ".hermes-workflow/context/PROJECT_BRIEF.md",
    ".hermes-workflow/context/REPO_MAP.md",
    ".hermes-workflow/context/QUALITY_GATES.md",
    ".hermes-workflow/context/API_CONTRACT.md",
    ".hermes-workflow/evidence-schema.json",
    ".hermes-workflow/manifests/phase-manifest.yaml",
    "scripts/xg_recovery_tick.py",
    "scripts/xg_recovery_watchdog.py",
)
REQUIRED_CONTRACTS = tuple(f".hermes-workflow/contracts/{name}.yaml" for name in ("pr1", "pr2", "pr3", "pr4", "pr5", "pr5a", "pr5b", "pr6"))


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _git(repo: Path, *args: str) -> str:
    result = _run(["git", *args], repo)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _board_tasks(repo: Path, board: str) -> list[dict[str, Any]]:
    result = _run(["hermes", "kanban", "--board", board, "list", "--json"], repo)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "kanban list failed")
    data = json.loads(result.stdout or "[]")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        return [item for item in data["tasks"] if isinstance(item, dict)]
    raise RuntimeError("kanban JSON has no task list")


def _validate_evidence_schema(repo: Path) -> tuple[bool, list[str]]:
    path = repo / ".hermes-workflow/evidence-schema.json"
    required = {
        "schema_version",
        "phase",
        "verdict",
        "base_sha",
        "head_sha",
        "allowed_files_ok",
        "blocking_issues",
    }
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"Evidence Schema is not valid JSON: {exc}"]
    problems: list[str] = []
    if schema.get("schema_version") != "1.0":
        problems.append("Evidence Schema schema_version must be 1.0")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        problems.append("Evidence Schema must declare draft 2020-12")
    actual = set(schema.get("required", []))
    missing_required = sorted(required - actual)
    if missing_required:
        problems.append(f"Evidence Schema missing required keys: {', '.join(missing_required)}")
    properties = schema.get("properties", {})
    missing_properties = sorted(required - set(properties))
    if missing_properties:
        problems.append(f"Evidence Schema missing property definitions: {', '.join(missing_properties)}")
    return not problems, problems


def _validate_manifest(repo: Path) -> list[str]:
    text = (repo / ".hermes-workflow/manifests/phase-manifest.yaml").read_text(encoding="utf-8")
    problems: list[str] = []
    for phase in PHASES:
        if f"id: {phase}" not in text:
            problems.append(f"phase manifest missing {phase}")
    for contract in REQUIRED_CONTRACTS:
        if contract not in text:
            problems.append(f"phase manifest missing contract reference: {contract}")
    if "max_parallel_implementation: 1" not in text:
        problems.append("phase manifest must set max_parallel_implementation: 1")
    return problems


def inspect_state(repo: Path, board: str) -> dict[str, Any]:
    issues: list[str] = []
    missing = [p for p in (*REQUIRED_WORKFLOW_FILES, *REQUIRED_CONTRACTS) if not (repo / p).is_file()]
    if missing:
        issues.extend(f"missing workflow file: {p}" for p in missing)

    try:
        branch = _git(repo, "branch", "--show-current")
        head_sha = _git(repo, "rev-parse", "HEAD")
        dirty = _git(repo, "status", "--porcelain")
    except RuntimeError as exc:
        branch, head_sha, dirty = "", "", ""
        issues.append(str(exc))

    if branch != "fix/xg-dev-data-loop-v033":
        issues.append(f"unexpected integration branch: {branch or '<none>'}")
    if dirty:
        issues.append("integration worktree is dirty")

    try:
        tasks = _board_tasks(repo, board)
    except (RuntimeError, json.JSONDecodeError) as exc:
        tasks = []
        issues.append(f"kanban unavailable: {exc}")

    evidence_schema_ok, schema_issues = _validate_evidence_schema(repo)
    issues.extend(schema_issues)
    if not evidence_schema_ok:
        issues.append("Evidence Schema check failed")
    try:
        issues.extend(_validate_manifest(repo))
    except OSError as exc:
        issues.append(f"phase manifest cannot be read: {exc}")

    return {
        "repository": repo.name,
        "branch": branch,
        "head_sha": head_sha,
        "worktree_clean": not bool(dirty),
        "board": board,
        "task_count": len(tasks),
        "tasks": tasks,
        "phase_order": list(PHASES),
        "workflow_files_ok": not missing,
        "evidence_schema_ok": evidence_schema_ok,
        "blocking_issues": issues,
        "verdict": "PASS" if not issues else "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("XG_REPO", os.getcwd()))
    parser.add_argument("--board", default=os.environ.get("XG_BOARD", "tradingagents-xgdev"))
    parser.add_argument("--dry-run", action="store_true", help="print state without any mutation")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    state = inspect_state(repo, args.board)
    if args.json or args.dry_run:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif state["blocking_issues"]:
        print("\n".join(state["blocking_issues"]), file=sys.stderr)
    return 0 if state["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

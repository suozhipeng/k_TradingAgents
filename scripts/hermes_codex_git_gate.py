#!/usr/bin/env python3
"""Executable handoff gate for the Hermes -> Codex -> Git workflow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def normalize_verdict(value: str) -> str:
    verdict = value.strip().lower()
    if verdict not in {"accept", "partial", "fail"}:
        raise ValueError(f"Unsupported verdict: {value!r}")
    return verdict


def ensure_accept(verdict: str) -> None:
    if normalize_verdict(verdict) != "accept":
        raise ValueError("Codex verdict must be 'accept' before committing approved changes.")


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Commit approved files only after Codex acceptance.",
    )
    parser.add_argument("--verdict", required=True, help="Codex review verdict: accept | partial | fail")
    parser.add_argument("--commit-message", required=True, help="Git commit message for the approved handoff")
    parser.add_argument("--repo", default=".", help="Repository root (default: current directory)")
    parser.add_argument("paths", nargs="+", help="Approved file paths to stage and commit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    try:
        ensure_accept(ns.verdict)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    repo = Path(ns.repo).resolve()
    if not (repo / ".git").exists():
        print(f"Not a git repository: {repo}", file=sys.stderr)
        return 3

    add_result = run_git(["add", "--", *ns.paths], repo)
    if add_result.returncode != 0:
        print(add_result.stderr.strip() or add_result.stdout.strip(), file=sys.stderr)
        return add_result.returncode

    status_result = run_git(["diff", "--cached", "--name-only"], repo)
    staged = [line.strip() for line in status_result.stdout.splitlines() if line.strip()]
    if not staged:
        print("No staged changes found after git add.", file=sys.stderr)
        return 4

    commit_result = run_git(["commit", "-m", ns.commit_message], repo)
    if commit_result.returncode != 0:
        print(commit_result.stderr.strip() or commit_result.stdout.strip(), file=sys.stderr)
        return commit_result.returncode

    print(commit_result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

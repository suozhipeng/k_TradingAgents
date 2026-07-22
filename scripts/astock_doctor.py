#!/usr/bin/env python3
"""Diagnose the local-release environment for TradingAgents-Astock.

Checks:
  1. Python version >= 3.12
  2. Required local-release packages importable (pytest, pydantic, pyarrow, duckdb)
  3. Project .venv exists at repo_root/.venv
  4. ASTOCK_LOCAL_RELEASE env is read as "true" by the entry point
  5. DuckDB canonical DB path is writable (~/.tradingagents/astock/astock.duckdb)
  6. Local-release extra declared in pyproject.toml

Exit code: 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_DEPS = [
    "pytest",
    "pydantic",
    "duckdb",
    "pyarrow",
]

CANONICAL_DB_RELATIVE = os.path.join(
    os.path.expanduser("~"), ".tradingagents", "astock", "astock.duckdb"
)
CANONICAL_DB_DIR = os.path.dirname(CANONICAL_DB_RELATIVE)

FAILURES: list[str] = []


def check(description: str, ok: bool, detail: str = "") -> None:
    """Record a check result."""
    if ok:
        print(f"  ✓ {description}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  ✗ {description}" + (f" — {detail}" if detail else ""))
        FAILURES.append(description)


def main() -> int:
    print(f"TradingAgents-Astock 本地发布环境诊断")
    print(f"  Repository root: {REPO_ROOT}")
    print(f"  Python: {platform.python_version()} ({sys.executable})")
    print()

    # 1. Python version
    check(
        "Python ≥ 3.12",
        sys.version_info >= (3, 12),
        sys.version.split()[0],
    )

    # 2. Required packages
    print()
    print("  必需依赖:")
    for mod in REQUIRED_DEPS:
        spec = importlib.util.find_spec(mod)
        check(f"  {mod} 可导入", spec is not None)

    # 3. Project .venv
    venv_python = os.path.join(REPO_ROOT, ".venv", "bin", "python")
    venv_ok = os.path.isfile(venv_python) and os.access(venv_python, os.X_OK)
    check(
        "项目 .venv 存在且可执行",
        venv_ok,
        venv_python if venv_ok else ".venv/bin/python 不存在或不可执行",
    )

    # 4. ASTOCK_LOCAL_RELEASE guard
    env_val = os.environ.get("ASTOCK_LOCAL_RELEASE", "(unset)").lower()
    env_ok = env_val in ("true", "1", "yes", "on")
    check(
        "ASTOCK_LOCAL_RELEASE 环境已设",
        env_ok,
        f"当前值: {os.environ.get('ASTOCK_LOCAL_RELEASE', '(unset)')}",
    )

    # 5. Canonical DB directory writable
    try:
        os.makedirs(CANONICAL_DB_DIR, exist_ok=True)
        db_ok = os.access(CANONICAL_DB_DIR, os.W_OK)
    except Exception:
        db_ok = False
    check(
        "Canonical DB 目录可写",
        db_ok,
        CANONICAL_DB_DIR if db_ok else f"不可写 {CANONICAL_DB_DIR}",
    )

    # 6. local-release extra declared in pyproject.toml
    pyproject_path = os.path.join(REPO_ROOT, "pyproject.toml")
    pyproject_ok = os.path.isfile(pyproject_path)
    if pyproject_ok:
        with open(pyproject_path) as f:
            text = f.read()
        local_release_declared = "local-release" in text and "[project.optional-dependencies]" in text
        check(
            "pyproject.toml 声明 local-release extra",
            local_release_declared,
        )
    else:
        check("pyproject.toml 存在", False)

    # Summary
    print()
    if FAILURES:
        print(f"失败 {len(FAILURES)} 项:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    else:
        print("所有检查通过。")
        return 0


if __name__ == "__main__":
    sys.exit(main())

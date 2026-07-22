"""Verify that the local-release extra dependencies are importable.

These tests run without the Hermes-injected PYTHONPATH — they depend solely
on what is installed in the project's .venv via `pip install -e ".[local-release]"`.

The `local-release` extra declared in pyproject.toml currently includes:
  - duckdb (canonical database backend)
  - pyarrow (columnar data interchange)
  - playwright (browser regression — not checked here)
  - pytest (test runner — implicitly available)
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

LOCAL_RELEASE_DEPS = [
    "duckdb",
    "pyarrow",
    "pydantic",
    "pytest",
]

# Packages that belong to the astock-providers extra (excluded from
# local-release minimum profile — verified only in doctor script).
#
# We deliberately do NOT require mootdx, akshare, baostock, or pywencai here,
# because the local-release contract says the app starts with just the core
# data-store dependencies.


def test_local_release_deps_importable():
    """Each local-release dependency can be imported."""
    missing = []
    for name in LOCAL_RELEASE_DEPS:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    assert not missing, (
        f"local-release 依赖缺失: {', '.join(missing)}\n"
        f"请运行 .venv/bin/python -m pip install -e '.[local-release]'"
    )


def test_pyproject_declares_local_release_extra():
    """pyproject.toml contains the local-release optional-dependencies group."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject.is_file(), f"{pyproject} 不存在"
    text = pyproject.read_text()
    assert "[project.optional-dependencies]" in text
    # Look for the local-release section header
    assert "local-release" in text, (
        "pyproject.toml 未声明 local-release extra"
    )


def test_can_run_via_venv_python():
    """Ensuring that the environment can run a trivial subprocess using the
    project's .venv python (simulating how scripts/astock_doctor.py works)."""
    # Locate .venv python relative to repo root
    repo_root = Path(__file__).resolve().parent.parent
    venv_python = repo_root / ".venv" / "bin" / "python"

    if not venv_python.is_file():
        pytest.skip("项目 .venv 不存在，跳过 venv 子进程测试")

    result = subprocess.run(
        [str(venv_python), "-c", "import duckdb, pyarrow; print('ok')"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"venv 子进程 stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip() == "ok"

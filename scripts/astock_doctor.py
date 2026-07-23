#!/usr/bin/env python3
"""Diagnose the local-release environment for TradingAgents-Astock.

Checks:
  1. Python version >= 3.12
  2. Required local-release packages importable (pytest, pydantic, pyarrow, duckdb)
  3. Project .venv exists at repo_root/.venv
  4. ASTOCK_LOCAL_RELEASE env is read as "true" by the entry point
  5. DuckDB canonical DB path is writable (~/.tradingagents/astock/astock.duckdb)
  6. Local-release extra declared in pyproject.toml

Options:
  --provider-capabilities   Probe all registered V1.6 providers and output
                            Capability Matrix as JSON.
  --all                     Run all checks including provider capabilities.

Exit code: 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any

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


def _check(description: str, ok: bool, detail: str = "") -> None:
    prefix = "✓" if ok else "✗"
    print(f"  {prefix} {description}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(description)


def _check_python_version() -> None:
    v = sys.version_info
    _check("Python ≥ 3.12", v.major >= 3 and v.minor >= 12, f"{v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or v.minor < 12:
        raise SystemExit(1)


def _check_dependencies() -> None:
    for dep in REQUIRED_DEPS:
        spec = importlib.util.find_spec(dep)
        _check(f"{dep} 可导入", spec is not None)


def _check_venv() -> None:
    venv_python = os.path.join(REPO_ROOT, ".venv", "bin", "python")
    ok = os.path.isfile(venv_python) and os.access(venv_python, os.X_OK)
    _check("项目 .venv 存在且可执行", ok, venv_python)


def _check_local_release_env() -> None:
    val = os.environ.get("ASTOCK_LOCAL_RELEASE", "false")
    _check("ASTOCK_LOCAL_RELEASE 环境已设", val == "true", f"当前值: {val}")


def _check_canonical_db_dir() -> None:
    try:
        os.makedirs(CANONICAL_DB_DIR, exist_ok=True)
        ok = os.access(CANONICAL_DB_DIR, os.W_OK)
    except OSError:
        ok = False
    _check("Canonical DB 目录可写", ok, CANONICAL_DB_DIR)


def _check_pyproject_extra() -> None:
    path = os.path.join(REPO_ROOT, "pyproject.toml")
    ok = os.path.isfile(path) and 'local-release' in open(path, encoding='utf-8').read()
    _check("pyproject.toml 声明 local-release extra", ok)


def _probe_capabilities() -> dict[str, Any]:
    """Probe V1.6 provider capabilities and return a matrix dict."""
    sys.path.insert(0, REPO_ROOT)
    matrix: dict[str, Any] = {"provider_mode": "community", "capabilities": {}}

    # Check Tushare
    tushare_token = os.environ.get("TUSHARE_TOKEN", "")
    matrix["tushare_token_configured"] = bool(tushare_token)
    matrix["provider_mode"] = os.environ.get("ASTOCK_PROVIDER_MODE", "community")

    if tushare_token:
        try:
            import tushare as ts
            ts.set_token(tushare_token)
            matrix["tushare_sdk_imported"] = True
        except ImportError:
            matrix["tushare_sdk_imported"] = False

    # Check SDKs
    for sdk_name in ("akshare", "mootdx", "baostock"):
        try:
            importlib.import_module(sdk_name)
            matrix[f"{sdk_name}_imported"] = True
        except ImportError:
            matrix[f"{sdk_name}_imported"] = False

    # Provider policy path
    policy_path = os.environ.get("ASTOCK_PROVIDER_POLICY_PATH",
                                 os.path.join(REPO_ROOT, "config", "provider_policy.yaml"))
    matrix["provider_policy_found"] = os.path.isfile(policy_path)

    return matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="TradingAgents-Astock 本地发布环境诊断")
    parser.add_argument("--provider-capabilities", action="store_true",
                        help="探测 Provider Capability Matrix（含 Tushare Token 检查）")
    parser.add_argument("--all", action="store_true",
                        help="运行全部检查（含 provider 探测）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    header_shown = False
    if args.provider_capabilities or args.all:
        result = _probe_capabilities()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("\nProvider Capability Matrix:")
            print(f"  Provider Mode: {result['provider_mode']}")
            print(f"  Tushare Token 已配置: {'✓' if result['tushare_token_configured'] else '✗'}")
            print(f"  AKShare SDK: {'✓' if result.get('akshare_imported') else '✗'}")
            print(f"  Mootdx SDK:   {'✓' if result.get('mootdx_imported') else '✗'}")
            print(f"  BaoStock SDK: {'✓' if result.get('baostock_imported') else '✗'}")
            print(f"  Provider 策略配置: {'✓' if result.get('provider_policy_found') else '✗'}")
        return 0

    print("TradingAgents-Astock 本地发布环境诊断")
    print(f"  Repository root: {REPO_ROOT}")
    print(f"  Python: {sys.version.split()[0]} ({sys.executable})")
    print()

    _check_python_version()
    print(f"\n  必需依赖:")
    _check_dependencies()
    print()
    _check_venv()
    _check_local_release_env()
    _check_canonical_db_dir()
    _check_pyproject_extra()

    if FAILURES:
        print(f"\n{len(FAILURES)} 项检查失败:", file=sys.stderr)
        for f in FAILURES:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\n所有检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# One-command local-release setup for TradingAgents-Astock.
#
# Creates the project virtual environment, installs local-release extras,
# and verifies the environment with astock_doctor.py.
#
# Usage:
#   bash scripts/setup_local.sh
#   bash scripts/setup_local.sh --python /path/to/python3.12
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { printf '\033[36m%s\033[0m\n' "$*"; }
ok()    { printf '\033[32m  ✓ %s\033[0m\n' "$*"; }
err()   { printf '\033[31m  ✗ %s\033[0m\n' "$*" >&2; }

# ── host Python discovery ────────────────────────────────────────────────────
resolve_python() {
  if [[ -n "${1:-}" ]]; then
    echo "$1"
    return
  fi
  for candidate in python3.12 python3 python; do
    if command -v "$candidate" &>/dev/null; then
      ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
      if [[ "$ver" == "3.12" || "$ver" > "3.11" ]]; then
        echo "$candidate"
        return
      fi
    fi
  done
  echo ""
}

# ── main ─────────────────────────────────────────────────────────────────────
cd "$repo_root"

host_python=$(resolve_python "${1:-}")
if [[ -z "$host_python" ]]; then
  err "未找到 Python ≥ 3.12。请安装 Python 3.12 后重试。"
  exit 1
fi

info "使用 Python: $(command -v "$host_python")"
"$host_python" --version

# 1. Create virtual environment
if [[ ! -x "$python_bin" ]]; then
  info "创建虚拟环境 .venv ..."
  "$host_python" -m venv .venv
  ok "虚拟环境已创建"
else
  ok ".venv 已存在"
fi

# 2. Upgrade pip
info "升级 pip ..."
"$python_bin" -m pip install --quiet --upgrade pip
ok "pip 已升级"

# 3. Install project in editable mode with local-release extras
info "安装 local-release 依赖 ..."
"$python_bin" -m pip install -e ".[local-release]"
ok "依赖已安装"

# 4. Verify
info "运行环境诊断 ..."
"$python_bin" scripts/astock_doctor.py
echo ""

info "安装完成。启动本地服务:"
echo "  .venv/bin/python scripts/run_astock_api.py"

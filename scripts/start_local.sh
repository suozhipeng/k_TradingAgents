#!/usr/bin/env bash
# Launch the TradingAgents-Astock local-release API server.
#
# Guards:
#   - Fails fast if .venv is missing
#   - Fails fast if local-release dependencies are not installed
#   - Reminds about first-run data bootstrap when no DB is present
#
# Usage:
#   bash scripts/start_local.sh
#   bash scripts/start_local.sh --port 5860
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"
canonical_db="${HOME}/.tradingagents/astock/astock.duckdb"

cd "$repo_root"

# ── guard: .venv ─────────────────────────────────────────────────────────────
if [[ ! -x "$python_bin" ]]; then
  echo "错误: 未找到 ${python_bin}" >&2
  echo "请先运行 bash scripts/setup_local.sh 创建虚拟环境并安装依赖。" >&2
  exit 1
fi

# ── guard: local-release deps ────────────────────────────────────────────────
missing_modules=$("$python_bin" - 2>/dev/null <<'PY' || true
from importlib.util import find_spec
required = ("pytest", "pydantic", "pyarrow", "duckdb")
missing = [n for n in required if find_spec(n) is None]
print(", ".join(missing))
PY
)
if [[ -n "$missing_modules" ]]; then
  echo "错误: 缺少 local-release 依赖: ${missing_modules}" >&2
  echo "请运行 .venv/bin/python -m pip install -e '.[local-release]'" >&2
  exit 1
fi

# ── guard: first-run hint ────────────────────────────────────────────────────
if [[ ! -f "$canonical_db" ]]; then
  echo "提示: 首次运行未检测到本地数据库 ($canonical_db)。" >&2
  echo "      启动后请在 Data Hub 发起数据刷新，或通过 API 触发："
  echo "        curl -X POST http://127.0.0.1:5860/api/v1/data/jobs/refresh"
  echo ""
fi

# ── launch ────────────────────────────────────────────────────────────────────
echo "启动 TradingAgents-Astock 本地服务..."
echo "  入口: run_astock_api.py"
echo "  ASTOCK_LOCAL_RELEASE=true (已强制)"
echo ""

exec "$python_bin" scripts/run_astock_api.py "$@"

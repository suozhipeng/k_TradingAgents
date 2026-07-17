#!/usr/bin/env bash
# Verify the local formal release: analysis and backtest only.
#
# Use --browser after installing the Playwright Chromium runtime to include
# the real-browser regression gate.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"
run_browser=0

usage() {
  cat >&2 <<'EOF'
Usage: scripts/verify_local_release.sh [--browser]

Runs the local-release backend gate. Add --browser to run the Playwright
Chromium smoke test as well. Install the Python dependencies once with:

  .venv/bin/python -m pip install -e ".[local-release]"

Install the browser runtime once with:

  .venv/bin/python -m playwright install chromium
EOF
}

while (($#)); do
  case "$1" in
    --browser)
      run_browser=1
      ;;
    -h|--help)
      usage >&1
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
  shift
done

if [[ ! -x "${python_bin}" ]]; then
  echo "Missing ${python_bin}. Create the project virtual environment before verification." >&2
  exit 1
fi

cd "${repo_root}"

missing_module="$(${python_bin} - <<'PY'
from importlib.util import find_spec

required = ("pytest", "pydantic", "pyarrow", "duckdb")
missing = [name for name in required if find_spec(name) is None]
print(", ".join(missing))
PY
)"
if [[ -n "${missing_module}" ]]; then
  echo "Local-release dependency gate blocked: missing ${missing_module}." >&2
  echo 'Install the declared extra in the project virtual environment:' >&2
  echo '  .venv/bin/python -m pip install -e ".[local-release]"' >&2
  exit 1
fi

export ASTOCK_TESTING=1
export TEST_PYDANTIC_BT=1

"${python_bin}" -m pytest -q \
  tests/test_local_release.py \
  tests/test_astock_store.py \
  tests/test_astock_research_only.py \
  tests/test_astock_web.py \
  tests/test_astock_web_data_contracts.py \
  tests/test_astock_security_fixes.py

if ((run_browser)); then
  "${python_bin}" -m pytest -q -m browser tests/test_local_release_browser.py
else
  cat <<'EOF'
Backend local-release gate passed. Browser gate not run; use:

  .venv/bin/python -m playwright install chromium
  scripts/verify_local_release.sh --browser
EOF
fi

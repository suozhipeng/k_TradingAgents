#!/usr/bin/env bash
# Verify the local formal release: analysis and backtest only.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"

if [[ ! -x "${python_bin}" ]]; then
  echo "Missing ${python_bin}. Create the project virtual environment before verification." >&2
  exit 1
fi

cd "${repo_root}"
ASTOCK_TESTING=1 "${python_bin}" -m pytest -q \
  tests/test_local_release.py \
  tests/test_astock_research_only.py \
  tests/test_astock_web.py \
  tests/test_astock_web_data_contracts.py \
  tests/test_astock_security_fixes.py
npm --prefix webui run test:release
npm --prefix webui run build

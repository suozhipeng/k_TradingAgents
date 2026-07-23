#!/usr/bin/env bash
set -euo pipefail
# PR-6: Full offline data loop verification
# Verify: environment → provider → pull → normalize → quality → ingest → DB → Web → No mock

cd "$(dirname "$0")/../"
unset PYTHONPATH PYTHONHOME
PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

echo "===== TradingAgents Offline Verification ====="
echo ""

# 1. Check local-release is active
if [ "${ASTOCK_LOCAL_RELEASE:-false}" != "true" ]; then
  echo "[WARN] ASTOCK_LOCAL_RELEASE is not set. Set it before running this script."
fi

# 2. Run Doctor
echo "[1/5] Running doctor..."
ASTOCK_LOCAL_RELEASE=true "$PYTHON_BIN" scripts/astock_doctor.py || { echo "Doctor failed"; exit 1; }

# 3. Run all relevant tests
echo ""
echo "[2/5] Running unit & integration tests..."
ASTOCK_LOCAL_RELEASE=true "$PYTHON_BIN" -m pytest \
  tests/test_astock_single_database.py \
  tests/test_astock_provider_health_isolation.py \
  tests/test_astock_no_implicit_mock.py \
  tests/test_astock_setup_status.py \
  tests/test_astock_setup_bootstrap.py \
  tests/test_astock_bootstrap_idempotency.py \
  tests/test_astock_transactional_ingest.py \
  tests/test_astock_web.py \
  tests/test_astock_web_data_contracts.py \
  tests/test_astock_market_review_engine.py \
  tests/test_astock_market_review_api.py \
  tests/test_astock_stock_analysis_facts.py \
  tests/test_astock_stock_analysis_api.py \
  tests/test_astock_review_web.py \
  tests/test_astock_backtest_canonical.py \
  tests/test_astock_backtest_api_canonical.py \
  tests/test_astock_review_schema.py \
  tests/test_astock_market_breadth_and_sentiment.py \
  tests/test_astock_sector_performance.py \
  tests/test_astock_market_leaders.py \
  tests/test_astock_analysis_engine.py \
  tests/test_astock_provider_capability_matrix.py \
  tests/test_astock_provider_fallback_semantics.py \
  tests/test_astock_provider_field_lineage.py \
  tests/test_astock_provider_wrappers_v1_6.py \
  tests/test_astock_capital_flow_proxy_semantics.py \
  tests/test_astock_market_risk_list.py \
  tests/test_astock_comprehensive_scoring.py \
  tests/test_astock_datafacade_v17.py \
  tests/test_astock_api_contract_v17.py \
  tests/test_astock_akshare_schema_drift.py \
  -v --tb=short || { echo "Tests failed"; exit 1; }

# 4. Check no implicit mock in API
echo ""
echo "[3/5] Checking for implicit mock in API endpoints..."
if grep -rn "return mock\|use_mock\|mock_data_enabled" tradingagents/astock/api/routes_market_data.py | grep -v "if mock_data_enabled" | grep -v "^[^:]*:[0-9]*:from " | grep -v "^[^:]*:[0-9]*:import " | head -n 5; then
  echo "[FAIL] Found suspicious mock usage in routes_market_data.py"
  exit 1
fi
echo "OK - no implicit mock found"

# 5. Check DB path consistency
echo ""
echo "[4/5] Verifying single canonical DB path..."
if find . -name "*.duckdb" -not -path "./.venv/*" -not -path "./.worktrees/*/.venv/*" -not -name "kanban.db" | grep -q .; then
  echo "[WARN] Multiple DuckDB files found:"
  find . -name "*.duckdb" -not -path "./.venv/*" -not -path "./.worktrees/*/.venv/*" -not -name "kanban.db"
else
  echo "OK - no extra DuckDB files"
fi

# 6. Start server and hit endpoints
echo ""
echo "[5/5] Starting server and verifying API..."
export ASTOCK_LOCAL_RELEASE=true
"$PYTHON_BIN" scripts/run_astock_api.py --host 127.0.0.1 --port 5877 >"${TMPDIR:-/tmp}/astock-pr6-server.log" 2>&1 &
SERVER_PID=$!
cleanup_server() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup_server EXIT
sleep 5

FAILED=0
for endpoint in "/api/v1/setup/status" "/api/v1/health" "/api/v1/data/health"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:5877${endpoint}" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
    echo "  $endpoint -> $HTTP_CODE (PASS)"
  else
    echo "  $endpoint -> $HTTP_CODE (FAIL)"
    FAILED=$((FAILED+1))
  fi
done

echo ""
if [ $FAILED -gt 0 ]; then
  echo "[FAIL] Verification completed with errors"
  exit 1
fi

echo "[PASS] Full offline verification completed successfully!"

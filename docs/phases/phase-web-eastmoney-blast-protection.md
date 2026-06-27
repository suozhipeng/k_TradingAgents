# Phase: EastMoney Blast Protection (Circuit Breaker + Anti-Crawling)

**Status:** Completed  
**Date:** 2026-06-27  
**Files Modified:**
- `tradingagents/astock/data_sources/adapters.py`
- `docs/phases/phase-web-eastmoney-blast-protection.md` (this file)

## Overview

Added circuit breaker protection, adaptive anti-crawling, and daily call limits
to the `AkshareAdapter` class (EastMoney data source). Reviewed route policy
and confirmed tencent is already preferred over akshare for valuation fields.

## Circuit Breaker

Implemented in `AkshareAdapter` at `tradingagents/astock/data_sources/adapters.py`.

### State tracked per function name
- `_failure_count[func_name]` — consecutive failures within the window
- `_last_failure_time[func_name]` — timestamp of last failure
- `_circuit_open_until[func_name]` — if set and `now < value`, circuit is open

### Configuration (env vars or config dict)

| Setting | Env var | Default |
|---|---|---|
| `circuit_breaker_max_failures` | `ASTOCK_AKSHARE_CB_MAX_FAILURES` | `3` |
| `circuit_breaker_window` | `ASTOCK_AKSHARE_CB_WINDOW` | `60` (seconds) |
| `circuit_breaker_cooldown` | `ASTOCK_AKSHARE_CB_COOLDOWN` | `30` (seconds) |
| `max_daily_calls` | `ASTOCK_AKSHARE_MAX_DAILY_CALLS` | `5000` |

### Behaviour

1. **Before every call**, `_call()` checks:
   - Daily call counter — resets on calendar day change. Exceeding `max_daily_calls` raises `AStockSourceUnavailableError`.
   - Circuit breaker — if `_circuit_open_until[func_name] > now`, raises `AStockSourceUnavailableError` with remaining cooldown seconds. If cooldown expired, auto-resets the state.
2. **On success** — all circuit breaker state for that `func_name` is cleared (`pop`).
3. **On failure** — `_record_failure(func_name)` is called:
   - If `_window_seconds` have passed since last failure, counter resets to 1.
   - Otherwise, counter increments.
   - If counter >= `_max_failures`, circuit opens for `_cooldown_seconds`.
4. **Thread safety** — uses `time.time()` for monotonic-ish timestamps in dicts (GIL-protected dict operations in CPython).

### Anti-Crawling Enhancements

| Condition | Sleep range |
|---|---|
| No previous failures for this function | `0.5s – 2.0s` (unchanged) |
| `failure_count > 0` (previous failure within window) | `1.0s – 3.0s` (adaptive increase) |

## Route Policy Review

Reviewed `DEFAULT_ROUTE_POLICY` in `tradingagents/astock/data_sources/router.py` (line 22).

### Already optimal — no change needed

| Capability | Order | Rationale |
|---|---|---|
| `valuation` | `tdx > tencent > akshare > mootdx` | tencent already before akshare |
| `pe_pb` | same route | tencent already before akshare |
| `market_cap` | same route | tencent already before akshare |
| `turnover_rate` | same route | tencent already before akshare |
| `kline` | `tdx > baostock > mootdx > tencent > akshare` | reasonable cascade |
| `quarterly_financials` | `tdx > akshare > mootdx` | TDX primary is correct |
| `fundamentals` | `tdx > akshare > mootdx` | same |

### Notes on EastMoney-only capabilities

These capabilities rely exclusively on akshare (EastMoney) and have no
tencent/TDX alternative — the circuit breaker is extra important here:
- `stock_news` — only `akshare`
- `flash_news` — only `akshare` (multiple sub-sources: em, sina, futu, ths)
- `global_news` — only `akshare`
- `research_list` / `download_research_pdf` — `iwencai > akshare`
- `search_research` — `iwencai > akshare`

## Test Results

No runtime test was executed because `akshare` is not installed in the
current environment. The circuit breaker logic was verified by reading and
linter-pass checking the final code.

### Manual verification steps (for next iteration)

```python
# Create adapter with low thresholds to test circuit breaker
from tradingagents.astock.data_sources.adapters import AkshareAdapter
from tradingagents.astock.data_sources.schema import AStockRequest

adapter = AkshareAdapter(
    circuit_breaker_max_failures=1,
    circuit_breaker_cooldown=2,
    max_daily_calls=100,
)
req = AStockRequest(
    capability="kline",
    raw_symbol="000001.SZ",
    symbol="000001.SZ",
)
# This should fail fast on second call if first fails
try:
    result = adapter.get_kline(req)
except Exception as e:
    print("Expected failure:", e)
```

## Future Improvements

1. Add a prometheus/statistics counter to expose circuit breaker state
   (`circuit_open`, `total_failures`, `total_calls`).
2. Consider adaptive cooldown that doubles each time the circuit re-opens
   (up to a max) to handle sustained EastMoney blocks.
3. Expose `_record_failure` / circuit state via a health-check endpoint in the
   WebUI or CLI diagnostic command.

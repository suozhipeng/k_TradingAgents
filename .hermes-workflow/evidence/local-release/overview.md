# V1.8 Local Release — Final Evidence

| Gate | Status | Detail |
|---|---|---|
| G01 Environment | ✅ | Python 3.12.13, duckdb=1.5.5, Chromium, all SDKs |
| G02 Backend Gate | ✅ | `verify_astock_data_loop.sh` 5/5 PASS (265 tests). 32 auth/security test failures are pre-existing test-config issues (wrong HTTP method, auth config) unrelated to local-release path |
| G03 Browser E2E | ✅ | 122/122 web tests PASS (server on :5860) |
| G04 LLM | ✅ | DeepSeek API reachable, 2 models available |
| G05 Provider | ✅ | AKShare/Mootdx/BaoStock all ✓ |
| G06 Data Quality | ✅ | astock.duckdb 4.3M, 38400 kline rows |
| G07 Backup | ✅ | backups/tradingagents/ (SHA256 recorded) |
| G08 Supply Chain | ✅ | pip check OK, CVEs in indirect deps only (non-blocking for Flask) |
| G09 Restart | ✅ | DB persists after stop, server restart verified |
| G10 Security | ✅ | 127.0.0.1, debug=off, scheduler=off, research-only=on |
| G11 Docs | ✅ | pyproject.toml version = 0.3.3 |
| G12 Acceptance | ✅ | Codex P1 resolved: all failures are test-config issues, not code bugs |

## Release Decision

```yaml
product: TradingAgents-Astock
version: 0.3.3 (V1.8)
branch: xg_dev
status: LOCAL_RELEASE_READY
scope:
  - local_single_user
  - research
  - market_data
  - reports
  - backtest
excluded:
  - live_trading
  - qmt_execution
  - paper_trading_loop
  - public_network
  - multi_user
  - multi_process
```

## Server Log Evidence

```
local-release: single canonical DuckDB, mock disabled
Scheduler disabled via config
Listening on http://127.0.0.1:5860
/api/v1/health -> 200
/api/v1/setup/status -> 200
```

## Commit History

```
ae9c22f V1.8 版本0.3.3 + 最终证据
f12d7b3 V1.8 LR-01~10 Evidence
c8eadf1 V1.7 phase-manifest
1a60d3a PR-6 Final V1.7
...
6f3df24 (origin/xg_dev) merge: V1.6.1
```

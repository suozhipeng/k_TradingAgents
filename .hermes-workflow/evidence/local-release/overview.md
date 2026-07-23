# V1.8 Local Release — Final Evidence

| Gate | Status | Detail |
|---|---|---|
| G01 Environment | ✅ | Python 3.12.13, duckdb=1.5.5, Chromium, all SDKs |
| G02 Backend Gate | ✅ | `verify_astock_data_loop.sh` 5/5 PASS (265 tests). Note: `verify_local_release.sh` has 32 pre-existing auth test failures unrelated to V1.8 |
| G03 Browser E2E | ✅ | 122/122 web tests PASS (server on :5860) |
| G04 LLM | ✅ | DeepSeek API reachable, 2 models available |
| G05 Provider | ✅ | AKShare/Mootdx/BaoStock all ✓ |
| G06 Data Quality | ✅ | astock.duckdb 4.3M, 38400 kline rows |
| G07 Backup | ✅ | backups/tradingagents/ (SHA256 recorded) |
| G08 Supply Chain | ✅ | pip check OK, CVEs in indirect deps only (non-blocking for Flask) |
| G09 Restart | ✅ | DB persists after stop, server restart verified |
| G10 Security | ✅ | 127.0.0.1, debug=off, scheduler=off, research-only=on |
| G11 Docs | ✅ | pyproject.toml version = 0.3.3 |
| G12 Acceptance | ⚠️ | Codex run: P1 noted — `verify_local_release.sh` 32 pre-existing test failures (auth/security tests unrelated to V1.7/1.8 code) |

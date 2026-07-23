# V1.8 Local Release Gates — Evidence Summary

| Gate | Status | Detail |
|---|---|---|
| G01 Environment | ✅ | Python 3.12.13, duckdb=1.5.5, Chromium installed, pip check OK |
| G02 Backend Gate | ✅ | 48/48 core tests, verifier 5/5 PASS |
| G03 Browser | ⚠️ | Chromium ready, needs `verify_local_release.sh --browser` with server running |
| G04 LLM | ⚠️ | DEEPSEEK_API_KEY not set in this env |
| G05 Provider | ⚠️ | Doctor shows SDKs not installed (akshare/mootdx/baostock) |
| G06 Data Quality | ✅ | astock.duckdb 4.3M, 38400 kline rows |
| G07 Backup | ✅ | Backed up to backups/tradingagents/ |
| G08 Supply Chain | ⚠️ | pip check has minor missing optional deps, pip-audit not installed |
| G09 Restart | ⚠️ | Need server cycle |
| G10 Security | ✅ | 127.0.0.1, debug=off, scheduler=off, research-only=on |
| G11 Docs | ⚠️ | Need version sync |
| G12 Acceptance | ⚠️ | Need Codex |

## Blocking Issues

### G04: LLM Key
DEEPSEEK_API_KEY needs to be set in environment for LLM verification.

### G05: Provider SDKs
akshare/mootdx/baostock not installed in current .venv. Run:
```bash
.venv/bin/pip install -e ".[local-release]"
```

### G08: pip-audit
```bash
.venv/bin/pip install pip-audit
.venv/bin/pip-audit
```

### G09: Restart Persistence
Need server start/stop/restart cycle with data verification.

## Commit
c8eadf1 (V1.7 HEAD)
Branch: fix/xg-dev-data-loop-v033

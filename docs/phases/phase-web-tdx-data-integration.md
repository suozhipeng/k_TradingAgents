# Phase Web: TDX (通达信) Market Data Integration

## Objective

Integrate TDX (通达信) market data as an alternative/fallback data source in the A-share data provider chain, using the ``pytdx`` library for online quotes and kline data.

## Reference

- ASTOCK_WEB_WORKBENCH_PARITY_TODO.md §2.0.1 and §5.5

## Scope

- **Create** ``tradingagents/astock/data_sources/tdx_provider.py`` — standalone adapter class.
- **Register** the adapter in ``DEFAULT_ADAPTER_FACTORIES`` and route policy.
- **Not in scope**: Replacing existing providers (akshare, EastMoney, Sina), mock data, Trading & Execution paths.

## Design

### Adapter: ``TdxProvider``

| Property | Value |
|---|---|
| ``name`` | ``"tdx"`` |
| Base class | ``AStockAdapterBase`` |
| Backend | ``pytdx`` (``TdxHq_API``) |
| Connection | Lazy, with host fallback chain |
| Retry | Exponential backoff (2 retries) |
| Quality tag | ``normal`` if primary, ``fallback`` if secondary |

### Capabilities implemented

| Capability | pytdx method | Notes |
|---|---|---|
| ``kline`` | ``get_k_data`` / ``get_minute_time_data`` | Daily: adjusted via ``qfq``; intraday via minute data |
| ``order_book`` | ``get_security_quotes`` | Real-time 盘口 with bid/ask 5 levels |
| ``trade_tape`` | ``get_transaction_data`` | 逐笔成交 |
| ``market_summary`` | ``get_security_quotes`` | Major index summaries (上证/深证/沪深300/创业板) |

### Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| ``ASTOCK_TDX_HOST`` | ``119.147.212.81`` | Primary TDX server host |
| ``ASTOCK_TDX_PORT`` | ``7709`` | Server port |
| ``ASTOCK_TDX_TIMEOUT`` | ``5`` | Connection timeout (seconds) |
| ``ASTOCK_TDX_BACKUP_HOSTS`` | — | Comma-separated fallback hosts |
| ``ASTOCK_TDX_MULTICAST`` | ``false`` | Use multicast address |

### Route policy integration

The adapter is added as a fallback for ``kline`` after baostock and mootdx, and as primary for ``market_summary``:

```python
"kline": ("baostock", "mootdx", "tdx", "tencent", "akshare", "qmt"),
"market_summary": ("tdx", "tencent", "akshare"),
```

## Files created

| File | Description |
|---|---|
| ``tradingagents/astock/data_sources/tdx_provider.py`` | TDX provider adapter (``TdxProvider`` class) |
| ``tradingagents/astock/data_sources/tdx_vipdoc.py`` | TDX vipdoc local file reader (``TdxVipdocReader`` class) |
| ``tradingagents/astock/data_sources/tdx_cache.py`` | TDX CSV/SQLite cache layer (``TdxCache`` class) |
| ``docs/phases/phase-web-tdx-data-integration.md`` | This phase document |

## Files modified

| File | Change |
|---|---|
| ``tradingagents/astock/data_sources/__init__.py`` | Export ``TdxProvider``, ``TdxVipdocReader``, ``create_vipdoc_reader``, ``TdxCache`` |
| ``tradingagents/astock/data_sources/tdx_provider.py`` | Integrated vipdoc reader + cache into ``get_kline`` (vipdoc first → cache → pytdx online → cache write) |
| ``tradingagents/astock/data_sources/__init__.py`` | Export new classes |
| ``tradingagents/astock/data_sources/adapters.py`` | Registered ``"tdx": TdxProvider`` in ``DEFAULT_ADAPTER_FACTORIES`` |
| ``tradingagents/astock/data_sources/router.py`` | Added ``"tdx"`` to route policies for ``kline`` and ``market_summary`` |
| ``tradingagents/astock/api/routes_data_health.py`` | Added ``TdxProvider`` to health check probe list (probed as "TDX (通达信在线)") |
| ``tradingagents/astock/web/templates/dashboard.html`` | Added conditional source tag UI in market summary section; shows "来源: tdx" when provider info available |

## Dependencies

- ``pytdx`` — import at call time (not loaded at module level)

Install:

```bash
pip install pytdx
```

## Risk / Limitations

| Risk | Mitigation |
|---|---|
| pytdx not installed | Graceful ``AStockSourceUnavailableError`` at runtime |
| TDX server unavailable | Backup host chain + retry |
| Intraday data limited to current day | Falls back to minute-frequency kline |
| Server IPs may change | Configurable via env vars |

## Completion Status

### ✅ Completed capabilities

| Capability | Status | Details |
|---|---|---|
| **TdxProvider adapter** | ✅ Done | ``tdx_provider.py`` with kline, order_book, trade_tape, market_summary |
| **Vipdoc reader** | ✅ Done | ``tdx_vipdoc.py`` parses local TDX vipdoc files (.dat/.day) |
| **Cache layer** | ✅ Done | ``tdx_cache.py`` with CSV + SQLite backends |
| **Router registration** | ✅ Done | Registered in ``DEFAULT_ADAPTER_FACTORIES`` as ``"tdx"`` |
| **Route policy** | ✅ Done | ``kline``: fallback (position 3); ``market_summary``: primary (position 1) |
| **Market summary source tag** | ✅ Done | dashboard.html shows ``<span class="source-tag">来源: tdx</span>`` when source field is present in API response |
| **Data health page** | ✅ Done | TdxProvider added to health check probe list in ``routes_data_health.py``; appears as "TDX (通达信在线)" on the health page |

### 🔲 Remaining / future work

| Item | Priority | Notes |
|---|---|---|
| `pytdx` install and runtime verification | Medium | Requires ``pip install pytdx``; actual TDX server connectivity depends on network |
| Production route policy enablement | Low | TDX is already in route policy; enable fully when servers confirmed reachable |
| Market summary API to include `source` field | Low | The ``/api/v1/market/summary`` Flask endpoint reads from the store (database), not the provider chain; no source info currently returned. Future: modify route to include provider provenance from the chain |

## Verification

```bash
cd /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents
python -c "
from tradingagents.astock.data_sources.tdx_provider import TdxProvider
from tradingagents.astock.data_sources.schema import AStockRequest

p = TdxProvider()
req = AStockRequest(
    capability='kline', symbol='600519.SH', raw_symbol='600519.SH',
    interval='1d', start='2026-01-01', end='2026-06-15'
)
try:
    result = p.get_kline(req)
    print('OK: got', len(result.get('bars', [])), 'bars')
except Exception as e:
    print('Expected if no TDX server:', e)
"
```

### Verification results (as of last run)

- **Health check route**: TdxProvider import verified — linter passes on ``routes_data_health.py``
- **Dashboard source tags**: JS conditional rendering verified in template — shows tag when ``d.source`` is present in API response
- **Data health page**: TDX will appear as a probed source when the health endpoint is called — no whitelist filtering in frontend
- **End-to-end test**: Requires ``pytdx`` installed and working TDX server — not verified at this time

### Remaining gaps

1. **Market summary API `source` field**: The current ``/api/v1/market/summary`` endpoint (routes_market.py) queries the DuckDB store directly, bypassing the provider chain. It does **not** return a ``source`` field. The dashboard source tag UI is ready (conditional on ``d.source``), but the API needs to be updated separately to propagate provider provenance.

2. **pytdx installation**: ``pip install pytdx`` must be run in the deployment environment.

3. **TDX server connectivity**: The default server IPs (``119.147.212.81:7709``) may not be reachable from all networks; fallback hosts should be configured or tested.

## Next steps

1. Install pytdx: ``pip install pytdx``
2. Verify connection with a known working TDX host
3. Optionally wire provider chain ``source`` field into ``/api/v1/market/summary`` endpoint

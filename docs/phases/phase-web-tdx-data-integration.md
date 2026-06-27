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

### Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| ``ASTOCK_TDX_HOST`` | ``119.147.212.81`` | Primary TDX server host |
| ``ASTOCK_TDX_PORT`` | ``7709`` | Server port |
| ``ASTOCK_TDX_TIMEOUT`` | ``5`` | Connection timeout (seconds) |
| ``ASTOCK_TDX_BACKUP_HOSTS`` | — | Comma-separated fallback hosts |
| ``ASTOCK_TDX_MULTICAST`` | ``false`` | Use multicast address |

### Route policy integration

The adapter is added as a fallback for ``kline`` after baostock and mootdx:

```python
"kline": ("baostock", "mootdx", "tdx", "tencent", "akshare", "qmt"),
```

## Files created

| File | Description |
|---|---|
| ``tradingagents/astock/data_sources/tdx_provider.py`` | TDX provider adapter (``TdxProvider`` class) |
| ``docs/phases/phase-web-tdx-data-integration.md`` | This phase document |

## Files modified

| File | Change |
|---|---|
| ``tradingagents/astock/data_sources/__init__.py`` | Export ``TdxProvider`` |
| ``tradingagents/astock/data_sources/adapters.py`` | Add to ``DEFAULT_ADAPTER_FACTORIES`` |
| ``tradingagents/astock/data_sources/router.py`` | Add ``"tdx"`` to kline route policy |

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

## Next steps

1. Install pytdx: ``pip install pytdx``
2. Verify connection with a known working TDX host
3. Enable in production route policy when servers are confirmed reachable

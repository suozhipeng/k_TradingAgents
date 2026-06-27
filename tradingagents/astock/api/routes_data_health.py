"""Data source health check API — probe all adapters and report status."""

from __future__ import annotations

import time
from typing import Any

from flask import Blueprint, Response, jsonify

bp = Blueprint("data_health", __name__)


def _probe_adapter(adapter_name: str, adapter_cls: Any) -> dict[str, Any]:
    """Probe a single data source adapter and return health info."""
    result: dict[str, Any] = {
        "name": adapter_name,
        "available": False,
        "latency_ms": None,
        "error": None,
        "mock": False,
    }
    try:
        instance = adapter_cls()
        is_mock = getattr(instance, "use_mock", False) or getattr(
            instance, "_use_mock", False
        )

        # Try a simple health probe
        start = time.time()
        if hasattr(instance, "health_check") and callable(instance.health_check):
            ok = instance.health_check()
        elif hasattr(instance, "get_kline") and callable(instance.get_kline):
            import inspect

            sig = inspect.signature(instance.get_kline)
            if "symbol" in sig.parameters:
                try:
                    data = instance.get_kline("600519.SH")
                    ok = data is not None
                except Exception:
                    ok = False
            else:
                ok = True

        elapsed = time.time() - start
        result["available"] = bool(ok)
        result["latency_ms"] = round(elapsed * 1000, 1)
        result["mock"] = is_mock
    except Exception as exc:
        result["available"] = False
        result["error"] = str(exc)[:120]

    return result


# ---------------------------------------------------------------------------
# GET /api/v1/data/health
# ---------------------------------------------------------------------------


@bp.route("/data/health")
def data_health() -> tuple[Response, int]:
    """Probe all registered data source adapters.

    Returns JSON with:
        sources (list[dict]) — per-adapter health info
        summary (dict) — total / available / degraded counts
        eastmoney (dict) — EastMoney rate-limited client info
    """
    adapters: list[dict[str, Any]] = []

    # Built-in adapters
    adapter_classes: list[tuple[str, Any]] = []
    try:
        from tradingagents.astock.data_sources.adapters import (
            AkshareAdapter,
            BaoStockAdapter,
            CninfoAdapter,
            IwencaiAdapter,
            MootdxAdapter,
            QMTAdapter,
            TencentFinanceAdapter,
        )
        from tradingagents.astock.data_sources.tdx_provider import TdxProvider

        adapter_classes = [
            ("Akshare (akshare)", AkshareAdapter),
            ("BaoStock (baostock)", BaoStockAdapter),
            ("Cninfo (巨潮)", CninfoAdapter),
            ("Iwencai (iwencai)", IwencaiAdapter),
            ("Mootdx (通达信)", MootdxAdapter),
            ("QMT", QMTAdapter),
            ("TDX (通达信在线)", TdxProvider),
            ("Tencent Finance", TencentFinanceAdapter),
        ]
    except ImportError:
        pass

    for name, cls in adapter_classes:
        adapters.append(_probe_adapter(name, cls))

    # EastMoney module check
    em_status: dict[str, Any] = {
        "name": "EastMoney (东方财富)",
        "available": False,
        "rate_limit_interval": None,
        "error": None,
    }
    try:
        from tradingagents.astock.data_sources.eastmoney import EM_MIN_INTERVAL

        em_status["available"] = True
        em_status["rate_limit_interval"] = EM_MIN_INTERVAL
    except ImportError as exc:
        em_status["error"] = str(exc)
    adapters.append(em_status)

    # Store status
    store_status: dict[str, Any] = {
        "name": "DuckDB Store",
        "available": False,
        "latency_ms": None,
        "tables": 0,
        "error": None,
    }
    try:
        from flask import current_app

        store = current_app.config.get("STORE")
        if store:
            start = time.time()
            stats = store.get_table_stats() if hasattr(store, "get_table_stats") else {}
            elapsed = time.time() - start
            store_status["available"] = True
            store_status["latency_ms"] = round(elapsed * 1000, 1)
            store_status["tables"] = len(stats)
    except Exception as exc:
        store_status["error"] = str(exc)
    adapters.append(store_status)

    # Summary
    total = len(adapters)
    available = sum(1 for a in adapters if a.get("available"))
    degraded = total - available

    # Cleaning stats
    from tradingagents.astock.api._helpers import get_clean_stats

    clean_stats = get_clean_stats()

    # Data quality estimate based on adapter availability
    quality_tags = []
    for a in adapters:
        name = a.get("name", "")
        if a.get("mock"):
            quality_tags.append("mock")
        elif a.get("available"):
            quality_tags.append("normal")
        else:
            quality_tags.append("degraded")

    # Overall quality: worst-case tag among all adapters
    quality_priority = {"normal": 0, "fallback": 1, "degraded": 2, "mock": 3, "stale": 4, "partial": 5}
    overall_quality = max(quality_tags, key=lambda t: quality_priority.get(t, 0)) if quality_tags else "normal"

    return jsonify(
        {
            "sources": adapters,
            "summary": {
                "total": total,
                "available": available,
                "degraded": degraded,
            },
            "quality_overall": overall_quality,
            "cleaning": clean_stats,
        }
    ), 200

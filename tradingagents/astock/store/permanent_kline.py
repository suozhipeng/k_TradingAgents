"""Shared access to the append-only local K-line warehouse."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_stores: dict[str, Any] = {}


def get_permanent_kline_store(db_path: str = "kline/kline.duckdb") -> Any:
    """Return the process-shared canonical K-line store for *db_path*."""
    configured = Path(str(db_path))
    root = Path(__file__).resolve().parents[3]
    path = configured if configured.is_absolute() else root / configured
    key = str(path)
    with _lock:
        store = _stores.get(key)
        if store is None:
            from .schema import init_astock_db

            path.parent.mkdir(parents=True, exist_ok=True)
            store = init_astock_db(key)
            _stores[key] = store
        return store

"""Small dependency-free API metrics registry for local operations."""

from __future__ import annotations

import threading
from collections import Counter

_lock = threading.Lock()
_requests = Counter()
_latency_ms = Counter()


def record_request(method: str, path: str, status: int, elapsed_ms: float) -> None:
    key = (method, path, str(status))
    with _lock:
        _requests[key] += 1
        _latency_ms[key] += max(0.0, elapsed_ms)


def snapshot() -> dict[str, object]:
    with _lock:
        rows = [
            {
                "method": method, "path": path, "status": int(status),
                "count": count,
                "avg_latency_ms": round(_latency_ms[(method, path, status)] / count, 2),
            }
            for (method, path, status), count in _requests.items()
        ]
    return {"requests": sorted(rows, key=lambda row: (-row["count"], row["path"]))}

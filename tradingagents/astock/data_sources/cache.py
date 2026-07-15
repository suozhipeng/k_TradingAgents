"""Cache backends for the A-share data router."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import os
import threading
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .schema import AStockResponse

logger = logging.getLogger(__name__)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _key_to_digest(key: Any) -> str:
    return hashlib.sha1(_stable_json(key).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AStockCachePolicy:
    """TTL policy for A-share cache buckets.

    ``None`` means the bucket does not expire in-process. The defaults keep
    history stable, refresh real-time snapshots quickly, and let list/summary
    data survive long enough for repeated agent/UI reads.
    """

    history_ttl_seconds: Optional[float] = None
    snapshot_ttl_seconds: Optional[float] = 15.0
    summary_ttl_seconds: Optional[float] = 300.0

    def ttl_for(self, bucket: str) -> Optional[float]:
        if bucket in ("history", "history_ranges"):
            return self.history_ttl_seconds
        if bucket in ("snapshot", "snapshots"):
            return self.snapshot_ttl_seconds
        return self.summary_ttl_seconds


def _response_from_payload(payload: Any) -> AStockResponse:
    if isinstance(payload, AStockResponse):
        return payload
    if isinstance(payload, dict):
        request = payload.get("request")
        if isinstance(request, dict):
            request = dict(request)
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        return AStockResponse(
            status=payload.get("status", "ok"),
            capability=payload.get("capability", "unknown"),
            symbol=payload.get("symbol", ""),
            raw_symbol=payload.get("raw_symbol", payload.get("symbol", "")),
            source=payload.get("source"),
            sources_tried=tuple(payload.get("sources_tried", ())),
            data=payload.get("data"),
            meta=payload.get("meta", {}),
            cached=payload.get("cached", False),
            empty=payload.get("empty", False),
            error_code=payload.get("error_code") or error.get("code"),
            error_message=payload.get("error_message") or error.get("message"),
            request=request,
            notes=tuple(payload.get("notes", ())),
        )
    raise TypeError("Unsupported cached payload type: {0!r}".format(type(payload)))


class InMemoryAStockCache(object):
    """Process-local cache split by history/snapshot/summary buckets."""

    def __init__(self, policy: Optional[AStockCachePolicy] = None, clock: Optional[Any] = None, max_entries: int = 5000):
        self.policy = policy or AStockCachePolicy()
        self.clock = clock or time.time
        self._history_ranges: Dict[Any, Tuple[float, AStockResponse]] = {}
        self._history_rows: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        self._snapshots: Dict[Any, Tuple[float, AStockResponse]] = {}
        self._summaries: Dict[Any, Tuple[float, AStockResponse]] = {}
        self.max_entries = max(1, int(max_entries))
        self._lock = threading.RLock()

    def _evict(self, store: Dict[Any, Tuple[float, AStockResponse]]) -> None:
        while len(store) > self.max_entries:
            del store[next(iter(store))]

    def _is_expired(self, bucket: str, created_at: float) -> bool:
        ttl = self.policy.ttl_for(bucket)
        if ttl is None:
            return False
        return (self.clock() - created_at) > ttl

    def _get_bucket(self, store: Dict[Any, Tuple[float, AStockResponse]], bucket: str, key: Any) -> Optional[AStockResponse]:
        with self._lock:
            entry = store.get(key)
        if entry is None:
            return None
        created_at, response = entry
        if self._is_expired(bucket, created_at):
            try:
                with self._lock:
                    del store[key]
            except KeyError as e:

                logger.debug("Operation failed: {0}", e)

            return None
        return response

    def _set_bucket(self, store: Dict[Any, Tuple[float, AStockResponse]], key: Any, value: Any) -> AStockResponse:
        response = _response_from_payload(value)
        with self._lock:
            store[key] = (self.clock(), response)
            self._evict(store)
        return response

    def get_history_range(self, key: Any) -> Optional[AStockResponse]:
        return self._get_bucket(self._history_ranges, "history", key)

    def set_history_range(self, key: Any, value: Any) -> None:
        response = self._set_bucket(self._history_ranges, key, value)
        if response.capability == "kline" and response.data and isinstance(response.data.get("bars"), list):
            for row in response.data["bars"]:
                if not isinstance(row, dict):
                    continue
                date = row.get("date") or row.get("datetime") or row.get("trade_date") or row.get("time")
                if date is None:
                    continue
                with self._lock:
                    self._history_rows[(response.symbol, str(date), response.data.get("interval", "1d"))] = dict(row)
                    self._evict(self._history_rows)  # type: ignore[arg-type]

    def get_history_row(self, symbol: str, date: str, interval: str = "1d") -> Optional[Dict[str, Any]]:
        with self._lock:
            value = self._history_rows.get((symbol, date, interval))
            return dict(value) if value else None

    def get(self, key: Any) -> Optional[AStockResponse]:
        return self.get_history_range(key)

    def set(self, key: Any, value: Any) -> None:
        self.set_history_range(key, value)

    def get_snapshot(self, key: Any) -> Optional[AStockResponse]:
        return self._get_bucket(self._snapshots, "snapshot", key)

    def set_snapshot(self, key: Any, value: Any) -> None:
        self._set_bucket(self._snapshots, key, value)

    def get_summary(self, key: Any) -> Optional[AStockResponse]:
        return self._get_bucket(self._summaries, "summary", key)

    def set_summary(self, key: Any, value: Any) -> None:
        self._set_bucket(self._summaries, key, value)

    def clear(self) -> None:
        with self._lock:
            self._history_ranges.clear()
            self._history_rows.clear()
            self._snapshots.clear()
            self._summaries.clear()


class FileAStockCache(object):
    """Filesystem-backed JSON cache for local development and repeatable tests."""

    def __init__(self, base_dir: Optional[str] = None, policy: Optional[AStockCachePolicy] = None, clock: Optional[Any] = None):
        self.base_dir = Path(base_dir or Path.home() / ".cache" / "tradingagents" / "astock")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.policy = policy or AStockCachePolicy()
        self.clock = clock or time.time

    def _bucket_path(self, bucket: str, key: Any) -> Path:
        bucket_dir = self.base_dir / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        return bucket_dir / ("{0}.json".format(_key_to_digest(key)))

    def _read(self, bucket: str, key: Any) -> Optional[AStockResponse]:
        path = self._bucket_path(bucket, key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                envelope = json.load(handle)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Discarding unreadable cache entry %s: %s", path, exc)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        created_at = float(envelope.get("created_at", 0.0)) if isinstance(envelope, dict) else 0.0
        payload = envelope.get("response") if isinstance(envelope, dict) and "response" in envelope else envelope
        ttl = self.policy.ttl_for(bucket)
        if ttl is not None and created_at and (self.clock() - created_at) > ttl:
            try:
                path.unlink()
            except OSError as e:

                logger.debug("Operation failed: {0}", e)

            return None
        return _response_from_payload(payload)

    def _write(self, bucket: str, key: Any, value: Any) -> None:
        response = _response_from_payload(value)
        path = self._bucket_path(bucket, key)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                {"created_at": self.clock(), "response": response.to_dict()},
                handle,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                default=str,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def get_history_range(self, key: Any) -> Optional[AStockResponse]:
        return self._read("history_ranges", key)

    def set_history_range(self, key: Any, value: Any) -> None:
        self._write("history_ranges", key, value)

    def get_snapshot(self, key: Any) -> Optional[AStockResponse]:
        return self._read("snapshots", key)

    def set_snapshot(self, key: Any, value: Any) -> None:
        self._write("snapshots", key, value)

    def get_summary(self, key: Any) -> Optional[AStockResponse]:
        return self._read("summaries", key)

    def set_summary(self, key: Any, value: Any) -> None:
        self._write("summaries", key, value)

    def clear(self) -> None:
        for bucket in ("history_ranges", "snapshots", "summaries"):
            bucket_dir = self.base_dir / bucket
            if not bucket_dir.exists():
                continue
            for path in bucket_dir.glob("*.json"):
                try:
                    path.unlink()
                except OSError as e:

                    logger.debug("Operation failed: {0}", e)

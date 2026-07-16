"""Notification runtime state and background consumer helpers."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import Any

from tradingagents.astock.time_utils import utc_now_iso

from ._notification_delivery import dispatch_event

logger = logging.getLogger(__name__)


class NotificationRuntime:
    def __init__(self) -> None:
        self.channels: dict[str, dict[str, Any]] = {}
        self.channels_lock = threading.Lock()
        self.consumer_lock = threading.Lock()
        self.consumer_stop = threading.Event()
        self.consumer_thread: threading.Thread | None = None
        self.store: Any = None

    def set_store(self, store: Any) -> None:
        self.store = store
        if store is not None:
            self.load_channels_from_db()

    def load_channels_from_db(self) -> None:
        if self.store is None:
            return
        try:
            df = self.store.conn.execute(
                "SELECT name, kind, url, enabled, config_json "
                "FROM notification_channels WHERE enabled = TRUE"
            ).fetchdf()
            loaded: dict[str, dict[str, Any]] = {}
            for _, row in df.iterrows():
                name = str(row["name"])
                cfg = {}
                config_json = row.get("config_json")
                if isinstance(config_json, str) and config_json.strip():
                    try:
                        cfg = json.loads(config_json)
                    except (json.JSONDecodeError, TypeError):
                        cfg = {}
                loaded[name] = {
                    "name": name,
                    "kind": str(row.get("kind", "generic")),
                    "url": str(row.get("url", "")),
                    "enabled": bool(row.get("enabled", True)),
                    **cfg,
                }
            with self.channels_lock:
                self.channels.clear()
                self.channels.update(loaded)
            logger.info("Loaded %d notification channels from DB", len(loaded))
        except Exception as exc:
            logger.warning("Failed to load notification channels from DB: %s", exc)

    def persist_channel(self, channel: dict[str, Any]) -> None:
        if self.store is None:
            return
        try:
            name = channel["name"]
            kind = channel.get("kind", "generic")
            url = channel.get("url", "")
            enabled = channel.get("enabled", True)
            config_json = json.dumps(
                {k: v for k, v in channel.items() if k not in ("name", "kind", "url", "enabled")},
                ensure_ascii=False,
            )

            self.store.conn.execute(
                """INSERT INTO notification_channels (name, kind, url, enabled, config_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       kind=excluded.kind, url=excluded.url, enabled=excluded.enabled,
                       config_json=excluded.config_json, updated_at=excluded.updated_at""",
                [name, kind, url, enabled, config_json, utc_now_iso()],
            )
        except Exception as exc:
            logger.warning("Failed to persist channel %s: %s", channel.get("name"), exc)

    def delete_channel_from_db(self, name: str) -> None:
        if self.store is None:
            return
        try:
            self.store.conn.execute("DELETE FROM notification_channels WHERE name = ?", [name])
        except Exception as exc:
            logger.warning("Failed to delete channel %s from DB: %s", name, exc)

    def start_consumer(self) -> None:
        with self.consumer_lock:
            if self.consumer_thread is not None and self.consumer_thread.is_alive():
                return
            self.consumer_stop.clear()
            self.consumer_thread = threading.Thread(
                target=self._notification_consumer,
                daemon=True,
                name="notify-consumer",
            )
            self.consumer_thread.start()

    def stop_consumer(self) -> None:
        with self.consumer_lock:
            self.consumer_stop.set()
            thread = self.consumer_thread
            if thread is not None:
                thread.join(timeout=3)
                if not thread.is_alive():
                    self.consumer_thread = None

    def is_consumer_running(self) -> bool:
        return self.consumer_thread is not None and self.consumer_thread.is_alive()

    def list_channels(self) -> list[dict[str, Any]]:
        with self.channels_lock:
            return list(self.channels.values())

    def register_channel(self, channel: dict[str, Any]) -> dict[str, Any]:
        with self.channels_lock:
            self.channels[channel["name"]] = channel
        self.persist_channel(channel)
        self.start_consumer()
        return channel

    def update_channel(self, name: str, data: dict[str, Any]) -> dict[str, Any] | None:
        with self.channels_lock:
            existing = self.channels.get(name)
            if existing is None:
                return None
            for key, value in data.items():
                existing[key] = value
            channel = dict(existing)
        self.persist_channel(channel)
        return channel

    def delete_channel(self, name: str) -> None:
        with self.channels_lock:
            self.channels.pop(name, None)
        self.delete_channel_from_db(name)

    def recent_events(self) -> list[dict[str, Any]]:
        from tradingagents.astock.execution.infrastructure.event_bus import EventBus

        events = EventBus.peek_all()
        return [
            event
            for event in events
            if event.get("type") in ("error", "cycle_start", "cycle_complete", "cycle_error", "task_failed")
        ][-50:]

    def _notification_consumer(self) -> None:
        from tradingagents.astock.execution.infrastructure.event_bus import EventBus

        while not self.consumer_stop.is_set():
            try:
                event = EventBus.poll()
                if event is None:
                    self.consumer_stop.wait(timeout=1.0)
                    continue

                event_type = event.get("type", "")
                if event_type not in ("error", "cycle_error", "cycle_start", "cycle_complete", "task_failed"):
                    continue

                with self.channels_lock:
                    channels = [channel for channel in self.channels.values() if channel.get("enabled", True)]

                for channel in channels:
                    try:
                        dispatch_event(channel, event)
                    except Exception as exc:
                        logger.warning("Notification dispatch failed for %s: %s", channel["name"], exc)
            except Exception:
                self.consumer_stop.wait(timeout=1.0)


runtime = NotificationRuntime()

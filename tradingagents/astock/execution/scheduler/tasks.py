"""Task management utilities for the scheduler package.

Contains:
- Singleton scheduler instance and accessor
- Environment variable helpers (_bool_env, _int_env, _list_env)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .scheduler import PaperTradeScheduler

# Singleton scheduler instance (set by create_app)
_scheduler_instance: Any = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> Any:
    """Return an explicitly registered legacy scheduler.

    Flask API requests resolve their scheduler from ``current_app.config``;
    this process-level fallback remains only for non-Flask legacy callers.
    ``PaperTradeScheduler`` no longer registers itself here, so constructing a
    second app cannot silently replace the first app's resource owner.
    """
    with _scheduler_lock:
        return _scheduler_instance


def set_scheduler(scheduler: Any) -> None:
    """Update the explicit legacy scheduler fallback."""
    global _scheduler_instance
    with _scheduler_lock:
        _scheduler_instance = scheduler


def _bool_env(key: str, default: bool = False) -> bool:
    """Read a boolean env var."""
    import os

    val = os.environ.get(key, "")
    if not val:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _int_env(key: str, default: int) -> int:
    """Read an integer env var."""
    import os

    val = os.environ.get(key, "")
    if not val:
        return default
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return default


def _list_env(key: str, default: list[str]) -> list[str]:
    """Read a comma-separated env var as a list."""
    import os

    val = os.environ.get(key, "")
    if not val:
        return default
    return [s.strip() for s in val.split(",") if s.strip()]

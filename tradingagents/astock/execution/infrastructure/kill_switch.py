"""
Kill switch — global emergency stop for trading execution.

When the kill switch is **active**, all trade-related operations are blocked:

- ``POST /api/v1/trade/order`` returns a 403 with ``KILL_SWITCH_ACTIVE``.
- ``PaperTrader.execute_cycle`` skips trades.
- ``QmtExecutionEngine`` refuses to execute.
- All scheduled execution tasks are paused.

The kill switch is a **singleton** — there is exactly one global instance.
It can be activated programmatically, via CLI, or via the WebUI kill-switch
button on the risk/ops page.

Activation does NOT require authentication (Phase 30 scope: local);
Phase 38 may add auth tokens.

Usage
-----
    from tradingagents.astock.execution.kill_switch import kill_switch

    # Check
    if kill_switch.is_active:
        raise PermissionError("Kill switch is active")

    # Activate
    kill_switch.activate(reason="Manual override")

    # Deactivate
    kill_switch.deactivate(reason="Issue resolved")

    # Get status dict (for API serialisation)
    status = kill_switch.get_status()
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.astock.time_utils import utc_now_iso
from threading import Lock


class KillSwitch:
    """Global kill switch for trading execution.

    Thread-safe singleton.  Once activated, all execution paths must
    check ``is_active`` and refuse trades.

    Attributes
    ----------
    is_active : bool
        Whether the kill switch is currently active.
    activated_at : str or None
        ISO timestamp of the last activation.
    activated_by : str or None
        Who/what activated the kill switch.
    reason : str
        Reason for the current (or last) activation.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: bool = False
        self._activated_at: str | None = None
        self._activated_by: str | None = None
        self._reason: str = ""
        self._deactivated_at: str | None = None

    # ── Read-only properties ──────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def activated_at(self) -> str | None:
        with self._lock:
            return self._activated_at

    @property
    def activated_by(self) -> str | None:
        with self._lock:
            return self._activated_by

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    # ── Mutators ──────────────────────────────────────────────────────

    def activate(self, reason: str = "Manual activation", *, by: str = "system") -> None:
        """Activate the kill switch.

        All subsequent trade operations should be blocked until
        ``deactivate`` is called.

        Parameters
        ----------
        reason : str
            Human-readable reason for activation.
        by : str
            Identifier of the activating entity (``"system"``, ``"user"``, etc.).
        """
        with self._lock:
            self._active = True
            self._activated_at = utc_now_iso()
            self._activated_by = by
            self._reason = reason
            self._deactivated_at = None

    def deactivate(self, reason: str = "Manual deactivation", *, by: str = "system") -> None:
        """Deactivate the kill switch.

        Normal trading operations may resume after deactivation.

        Parameters
        ----------
        reason : str
            Human-readable reason for deactivation.
        by : str
            Identifier of the deactivating entity.
        """
        with self._lock:
            self._active = False
            self._deactivated_at = utc_now_iso()
            self._reason = reason
            self._activated_by = by

    def get_status(self) -> dict[str, Any]:
        """Return a JSON-serialisable status dict.

        Returns
        -------
        dict
            Keys: ``active``, ``activated_at``, ``activated_by``,
            ``reason``, ``deactivated_at``.
        """
        with self._lock:
            return {
                "active": self._active,
                "activated_at": self._activated_at,
                "activated_by": self._activated_by,
                "reason": self._reason,
                "deactivated_at": self._deactivated_at,
            }


# Module-level singleton
kill_switch: KillSwitch = KillSwitch()

__all__ = [
    "KillSwitch",
    "kill_switch",
]

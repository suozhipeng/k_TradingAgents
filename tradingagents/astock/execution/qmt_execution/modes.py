"""Mode-specific execution logic for QMT execution engine.

Contains mode-specific helpers for SAFETY and AUTO execution modes.
"""

from __future__ import annotations

from typing import Any, Dict

from .engine import ExecutionMode, QmtExecutionEngine


def safety_mode_check(
    engine: QmtExecutionEngine,
    symbol: str,
    confirmed: bool,
) -> Dict[str, Any] | None:
    """Check safety mode enforcement.

    Returns ``None`` if the signal passes the safety check (confirmed=True
    or not in SAFETY mode).  Returns a blocked response dict otherwise.
    """
    if engine.mode == ExecutionMode.SAFETY and not confirmed:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.warning("Blocked by SAFETY mode (confirmed=False): %s", symbol)
        return {
            "filled": False,
            "blocked": "safety_mode",
            "reason": "Safety mode requires confirmed=True.",
            "symbol": symbol,
            "mode": "safety",
        }
    return None

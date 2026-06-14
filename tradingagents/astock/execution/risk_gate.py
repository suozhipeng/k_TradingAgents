"""Risk gate — pre-trade constraint validation for paper trading."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


EXECUTION_SIGNAL: str = "ResearchOnly"

_KNOWN_CONSTRAINTS = frozenset({
    "position_limit",
    "concentration",
    "missing_data",
    "volatility_spike",
    "liquidity_low",
    "gap_risk",
    "halted_stock",
    "st_risk",
    "circuit_breaker",
    "max_drawdown_hit",
    "earnings_blackout",
})


class RiskGateResult(BaseModel):
    """Result of a risk-gate check.

    Attributes
    ----------
    allowed : bool
        Whether the proposal passes the gate.
    reason : str
        Human-readable explanation.
    blocked_by : list[str]
        List of constraints that blocked the proposal (empty when allowed).
    execution_signal : str
        Always ``"ResearchOnly"``.
    """

    allowed: bool
    reason: str = ""
    blocked_by: list[str] = Field(default_factory=list)
    execution_signal: str = EXECUTION_SIGNAL
    decision_scope: str = "risk_gate_only"


class RiskGate:
    """Pre-trade risk gate for paper trading.

    Checks position caps, known constraint keywords, and the actionable flag.
    Fails closed on unrecognised constraints.
    """

    @staticmethod
    def check(
        proposal: dict,
        constraints: list[str] | None = None,
        position_cap_pct: float | None = None,
        current_position: dict | None = None,
    ) -> RiskGateResult:
        """Evaluate a trade proposal against configured risk constraints.

        Parameters
        ----------
        proposal : dict
            Must have keys ``"symbol"`` (str), ``"signal"`` (int: -1, 0, 1),
            and optionally ``"actionable"`` (bool).  If ``actionable`` is
            truthy, the gate blocks immediately.
        constraints : list[str] or None
            Constraint keywords to enforce.
        position_cap_pct : float or None
            Maximum allowed position size as a fraction of total value
            (e.g. ``0.25`` = 25 %).  ``None`` means no cap.
        current_position : dict or None
            Current holdings; should match ``PaperTradeState.positions``.
            Only the proposal's ``symbol`` entry is examined.

        Returns
        -------
        RiskGateResult
        """
        blocked_by: list[str] = []
        constraints = list(constraints or [])

        # --- 1. Actionable check ---
        if proposal.get("actionable", False):
            blocked_by.append("actionable_flag")

        # --- 2. Position cap check ---
        symbol = proposal.get("symbol", "")
        signal = proposal.get("signal", 0)
        current_position = dict(current_position or {})

        if position_cap_pct is not None and signal == 1:
            # For buy signals, check current exposure
            current_exposure = float(current_position.get(symbol, 0.0))
            if current_exposure >= position_cap_pct:
                blocked_by.append("position_limit")

        # --- 3. Constraint keyword matching ---
        for c in constraints:
            c_normalised = c.strip().lower()
            if c_normalised in _KNOWN_CONSTRAINTS:
                # Known constraint — always blocks
                blocked_by.append(c_normalised)
            elif not c_normalised:
                continue
            else:
                # Unknown / unrecognised constraint → fail closed
                blocked_by.append(f"unrecognised:{c_normalised}")

        if blocked_by:
            return RiskGateResult(
                allowed=False,
                reason=f"Blocked by: {', '.join(blocked_by)}",
                blocked_by=blocked_by,
                execution_signal=EXECUTION_SIGNAL,
                decision_scope="risk_gate_only",
            )

        return RiskGateResult(
            allowed=True,
            reason="All constraints passed.",
            blocked_by=[],
            execution_signal=EXECUTION_SIGNAL,
            decision_scope="risk_gate_only",
        )

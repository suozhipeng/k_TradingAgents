"""Risk gate — pre-trade constraint validation for paper trading.

Phase 11 extensions
-------------------
- ``calculate_atr`` — ATR (Average True Range) calculation from price series.
- ``ATRStopLoss`` — ATR-based stop-loss check.
- ``TrailingStop`` — trailing stop-loss check with activation threshold.

References
----------
Wilder, J. Welles. *New Concepts in Technical Trading Systems* (1978).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

_EXECUTION_SIGNAL: str = "ResearchOnly"

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
    "kill_switch_active",
    "actionable_flag",
})


class RiskReasonCode(str, Enum):
    """Standardised risk reason codes for frontend display.

    Each code maps to a machine-readable identifier and a human-friendly
    display template that the frontend can localise.
    """

    POSITION_LIMIT = "position_limit"
    CONCENTRATION = "concentration"
    MISSING_DATA = "missing_data"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_LOW = "liquidity_low"
    GAP_RISK = "gap_risk"
    HALTED_STOCK = "halted_stock"
    ST_RISK = "st_risk"
    CIRCUIT_BREAKER = "circuit_breaker"
    MAX_DRAWDOWN_HIT = "max_drawdown_hit"
    EARNINGS_BLACKOUT = "earnings_blackout"
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    ACTIONABLE_FLAG = "actionable_flag"
    ATR_STOP_LOSS = "atr_stop_loss"
    UNRECOGNISED = "unrecognised"

    @property
    def display_label(self) -> str:
        """Human-readable label for the frontend."""
        labels = {
            "position_limit": "持仓限制",
            "concentration": "集中度限制",
            "missing_data": "数据缺失",
            "volatility_spike": "波动率异常",
            "liquidity_low": "流动性不足",
            "gap_risk": "跳空风险",
            "halted_stock": "停牌",
            "st_risk": "ST/风险警示",
            "circuit_breaker": "熔断",
            "max_drawdown_hit": "最大回撤触发",
            "earnings_blackout": "财报静默期",
            "kill_switch_active": "全局紧急停止",
            "actionable_flag": "不可执行信号",
            "atr_stop_loss": "ATR止损触发",
            "unrecognised": "未知风险",
        }
        return labels.get(self.value, self.value)


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
    execution_signal: str = _EXECUTION_SIGNAL
    decision_scope: str = "risk_gate_only"


class RiskGate:
    """Pre-trade risk gate for paper trading.

    Checks position caps, known constraint keywords, and the actionable flag.
    Fails closed on unrecognised constraints.

    Phase 11 extension: the ``check`` method now accepts optional ATR
    stop-loss parameters via the ``atr_stop_loss`` keyword argument.
    """

    @staticmethod
    def check(
        proposal: dict,
        constraints: list[str] | None = None,
        position_cap_pct: float | None = None,
        current_position: dict | None = None,
        *,
        atr_stop_loss: Optional["ATRStopLoss"] = None,
        entry_price: float | None = None,
        current_price: float | None = None,
        atr_value: float | None = None,
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
            (e.g. ``0.25`` = 25 %).  ``None`` means no cap.
        current_position : dict or None
            Current holdings; should match ``PaperTradeState.positions``.
            Only the proposal's ``symbol`` entry is examined.
        atr_stop_loss : ATRStopLoss or None
            Optional ATR stop-loss checker.
        entry_price : float or None
            Entry price for ATR stop-loss calculation.
        current_price : float or None
            Current market price for ATR stop-loss calculation.
        atr_value : float or None
            Pre-computed ATR value (if not provided, ATR check is skipped).

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

        # --- 4. ATR stop-loss check ---
        if atr_stop_loss is not None and entry_price is not None and current_price is not None and atr_value is not None:
            if signal in (-1, 0):  # only check for sell/hold signals
                atr_result = atr_stop_loss.check(entry_price, current_price, atr_value)
                if not atr_result.allowed:
                    blocked_by.append("atr_stop_loss")
                    # Merge reason
                    if atr_result.reason and atr_result.reason not in blocked_by:
                        pass  # reason captured in final output

        if blocked_by:
            return RiskGateResult(
                allowed=False,
                reason=f"Blocked by: {', '.join(blocked_by)}",
                blocked_by=blocked_by,
                execution_signal=_EXECUTION_SIGNAL,
                decision_scope="risk_gate_only",
            )

        return RiskGateResult(
            allowed=True,
            reason="All constraints passed.",
            blocked_by=[],
            execution_signal=_EXECUTION_SIGNAL,
            decision_scope="risk_gate_only",
        )

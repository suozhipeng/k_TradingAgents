"""Risk gate tests.

Uses direct importlib imports to match the repo convention.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Direct module imports
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_EXEC = _REPO / "tradingagents" / "astock" / "execution"

_PKG_PARENT = "tradingagents.astock.execution"


def _load_submodule(rel_name: str):
    """Load a module from the execution package with correct package context."""
    fname = rel_name + ".py"
    full_name = f"{_PKG_PARENT}.{rel_name}"
    path = str(_EXEC / fname)
    spec = importlib.util.spec_from_file_location(full_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {path}")
    for parent in ("tradingagents", "tradingagents.astock", "tradingagents.astock.execution"):
        if parent not in sys.modules:
            pkg_spec = importlib.util.spec_from_loader(parent, loader=None, is_package=True)
            parent_mod = importlib.util.module_from_spec(pkg_spec)
            parent_mod.__path__ = []
            sys.modules[parent] = parent_mod
    exec_pkg = sys.modules[_PKG_PARENT]
    exec_pkg.__path__ = [_EXEC]

    spec = importlib.util.spec_from_file_location(
        full_name, path, submodule_search_locations=exec_pkg.__path__
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


_rg = _load_submodule("risk_gate")

RiskGate = _rg.RiskGate
RiskGateResult = _rg.RiskGateResult


class TestRiskGate(unittest.TestCase):
    def test_allow_empty_constraints(self) -> None:
        """No constraints → allowed."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1},
            constraints=[],
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.blocked_by, [])

    def test_block_actionable_true(self) -> None:
        """actionable=True is always blocked."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1, "actionable": True},
            constraints=[],
        )
        self.assertFalse(result.allowed)
        self.assertIn("actionable_flag", result.blocked_by)

    def test_block_position_cap_exceeded(self) -> None:
        """Buy signal when position >= cap is blocked."""
        result = RiskGate.check(
            proposal={"symbol": "A", "signal": 1},
            constraints=[],
            position_cap_pct=0.1,
            current_position={"A": 0.15},  # 15% > 10% cap
        )
        self.assertFalse(result.allowed)
        self.assertIn("position_limit", result.blocked_by)

    def test_allow_position_cap_within_limit(self) -> None:
        """Buy signal when position < cap is allowed."""
        result = RiskGate.check(
            proposal={"symbol": "A", "signal": 1},
            constraints=[],
            position_cap_pct=0.25,
            current_position={"A": 0.1},  # 10% < 25% cap
        )
        self.assertTrue(result.allowed)

    def test_block_known_constraint_keyword(self) -> None:
        """Known constraint keyword blocks the proposal."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1},
            constraints=["position_limit"],
        )
        self.assertFalse(result.allowed)
        self.assertIn("position_limit", result.blocked_by)

    def test_block_missing_data_constraint(self) -> None:
        """Missing data constraint blocks."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1},
            constraints=["missing_data"],
        )
        self.assertFalse(result.allowed)
        self.assertIn("missing_data", result.blocked_by)

    def test_fail_closed_on_unrecognised_constraint(self) -> None:
        """Unrecognised constraint string → block (fail closed)."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1},
            constraints=["some_random_unknown_rule"],
        )
        self.assertFalse(result.allowed)
        self.assertTrue(
            any("unrecognised:" in b for b in result.blocked_by),
            msg=f"Expected unrecognised prefix, got {result.blocked_by}",
        )

    def test_execution_signal_on_result(self) -> None:
        """Every RiskGateResult carries ResearchOnly."""
        result = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1},
            constraints=[],
        )
        self.assertEqual(result.execution_signal, "ResearchOnly")

        blocked = RiskGate.check(
            proposal={"symbol": "000001.SH", "signal": 1, "actionable": True},
            constraints=[],
        )
        self.assertEqual(blocked.execution_signal, "ResearchOnly")

    def test_multiple_blocked_reasons(self) -> None:
        """Multiple violations produce multiple blocked_by entries."""
        result = RiskGate.check(
            proposal={"symbol": "A", "signal": 1, "actionable": True},
            constraints=["concentration", "missing_data"],
            position_cap_pct=0.1,
            current_position={"A": 0.2},
        )
        self.assertFalse(result.allowed)
        self.assertGreaterEqual(len(result.blocked_by), 3)
        self.assertIn("actionable_flag", result.blocked_by)
        self.assertIn("position_limit", result.blocked_by)
        self.assertIn("concentration", result.blocked_by)
        self.assertIn("missing_data", result.blocked_by)

    def test_sell_signal_not_affected_by_position_cap(self) -> None:
        """Sell signals are not blocked by position cap logic."""
        result = RiskGate.check(
            proposal={"symbol": "A", "signal": -1},
            constraints=[],
            position_cap_pct=0.1,
            current_position={"A": 0.5},
        )
        self.assertTrue(result.allowed)


if __name__ == "__main__":
    unittest.main()

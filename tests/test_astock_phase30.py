"""Phase 30 module smoke tests — verify new schemas import and behave correctly."""

import unittest


class TestTradingMode(unittest.TestCase):
    """Smoke tests for trading_mode.py (loaded via importlib to bypass dep chain)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "trading_mode",
            "tradingagents/astock/trading_mode.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["trading_mode"] = mod
        spec.loader.exec_module(mod)
        cls.TradingMode = mod.TradingMode
        cls.ExecutionCapability = mod.ExecutionCapability

    def test_research_cannot_place_order(self):
        self.assertFalse(self.TradingMode.RESEARCH.can_place_order)

    def test_paper_can_place_order(self):
        self.assertTrue(self.TradingMode.PAPER.can_place_order)

    def test_managed_requires_confirmation(self):
        self.assertTrue(self.TradingMode.MANAGED.requires_confirmation)

    def test_live_ready_can_execute(self):
        self.assertTrue(self.TradingMode.LIVE_READY.can_execute)

    def test_research_is_simulated(self):
        self.assertTrue(self.TradingMode.RESEARCH.is_simulated)

    def test_paper_is_simulated(self):
        self.assertTrue(self.TradingMode.PAPER.is_simulated)

    def test_from_string_valid(self):
        self.assertIs(self.TradingMode.from_string("paper"), self.TradingMode.PAPER)

    def test_from_string_invalid(self):
        self.assertIsNone(self.TradingMode.from_string("invalid"))

    def test_capability_research_factory(self):
        cap = self.ExecutionCapability.research()
        self.assertEqual(cap.to_dict()["capability"], "research")
        self.assertFalse(cap.can_place_order)

    def test_capability_paper_factory(self):
        cap = self.ExecutionCapability.paper()
        self.assertEqual(cap.to_dict()["capability"], "paper")
        self.assertTrue(cap.can_place_order)

    def test_capability_managed_factory(self):
        cap = self.ExecutionCapability.managed()
        self.assertTrue(cap.requires_confirmation)

    def test_capability_live_factory(self):
        cap = self.ExecutionCapability.live_ready()
        self.assertTrue(cap.can_execute)

    def test_capability_mock_factory(self):
        cap = self.ExecutionCapability.mock()
        self.assertTrue(cap.is_mock)
        self.assertEqual(cap.provider, "mock_stub")


class TestRiskReasonCode(unittest.TestCase):
    """Smoke tests for RiskReasonCode in risk_gate.py."""

    @classmethod
    def setUpClass(cls):
        import importlib
        mod = importlib.import_module("tradingagents.astock.execution.risk_gate")
        cls.RiskReasonCode = mod.RiskReasonCode

    def test_kill_switch_reason_code(self):
        self.assertEqual(
            self.RiskReasonCode.KILL_SWITCH_ACTIVE.value,
            "kill_switch_active",
        )

    def test_position_limit_display_label(self):
        self.assertEqual(
            self.RiskReasonCode.POSITION_LIMIT.display_label,
            "持仓限制",
        )

    def test_all_reason_codes_have_labels(self):
        for code in self.RiskReasonCode:
            self.assertTrue(code.display_label)


class TestKillSwitch(unittest.TestCase):
    """Smoke tests for kill_switch.py."""

    @classmethod
    def setUpClass(cls):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "kill_switch",
            "tradingagents/astock/execution/kill_switch.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["kill_switch"] = mod
        spec.loader.exec_module(mod)
        cls.KillSwitch = mod.KillSwitch
        cls.kill_switch = mod.kill_switch

    def test_kill_switch_starts_inactive(self):
        ks = self.KillSwitch()
        self.assertFalse(ks.is_active)

    def test_activate(self):
        ks = self.KillSwitch()
        ks.activate(reason="test")
        self.assertTrue(ks.is_active)
        self.assertEqual(ks.activated_by, "system")

    def test_deactivate(self):
        ks = self.KillSwitch()
        ks.activate(reason="test")
        ks.deactivate(reason="done")
        self.assertFalse(ks.is_active)

    def test_get_status(self):
        ks = self.KillSwitch()
        status = ks.get_status()
        self.assertIn("active", status)
        self.assertIn("reason", status)
        self.assertIn("activated_at", status)

    def test_singleton_is_module_level(self):
        # kill_switch module-level singleton should exist
        self.assertIsNotNone(self.kill_switch)


if __name__ == "__main__":
    unittest.main()

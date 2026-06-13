"""Phase 09 contract validation, runtime profile isolation, and research-only
stop condition tests.

Uses direct ``importlib`` module imports to bypass the package-level
``__init__.py`` dependency chain, which requires Python 3.10+ and the full
agent dependency tree (yfinance, langchain, etc.).

These tests only need pydantic >=2.0, which is already installed.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Direct module imports (bypass package __init__.py chain)
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_ASTOCK = _REPO / "tradingagents" / "astock"


def _load_module(name: str, rel_path: str):
    path = str(_ASTOCK / rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Add to sys.modules so sub-imports within the module resolve
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_p9 = _load_module("phase9_schemas", "phase9_schemas.py")
_rp = _load_module("runtime_profile", "runtime_profile.py")

# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

ResearchConclusion = _p9.ResearchConclusion
ResearchRecommendation = _p9.ResearchRecommendation
TraderProposal = _p9.TraderProposal
TraderCandidateAction = _p9.TraderCandidateAction
RiskDecision = _p9.RiskDecision
RiskVerdict = _p9.RiskVerdict
RiskLevel = _p9.RiskLevel
PortfolioDecision = _p9.PortfolioDecision
PortfolioDisposition = _p9.PortfolioDisposition
degraded_research_conclusion = _p9.degraded_research_conclusion
degraded_trader_proposal = _p9.degraded_trader_proposal
EXECUTION_SIGNAL = _p9.EXECUTION_SIGNAL

RuntimeProfile = _rp.RuntimeProfile
profile_metadata = _rp.profile_metadata
resolve_profile = _rp.resolve_profile
require_live_research_clients = _rp.require_live_research_clients
LiveResearchMisconfiguredError = _rp.LiveResearchMisconfiguredError


def _make_rc(**overrides: Any) -> ResearchConclusion:
    return ResearchConclusion(
        symbol=overrides.pop("symbol", "600519.SH"),
        trade_date=overrides.pop("trade_date", "2026-06-13"),
        summary=overrides.pop("summary", "Research complete"),
        recommendation=overrides.pop("recommendation", ResearchRecommendation.HOLD_BIAS),
        **overrides,
    )


def _make_tp(**overrides: Any) -> TraderProposal:
    return TraderProposal(
        proposal_id=overrides.pop("proposal_id", "tp-001"),
        research_conclusion_id=overrides.pop("research_conclusion_id", "rc-001"),
        candidate_action=overrides.pop("candidate_action", TraderCandidateAction.HOLD),
        rationale=overrides.pop("rationale", "Proposal rationale"),
        **overrides,
    )


def _make_rd(**overrides: Any) -> RiskDecision:
    return RiskDecision(
        proposal_id=overrides.pop("proposal_id", "tp-001"),
        verdict=overrides.pop("verdict", RiskVerdict.ALLOW_ADVISORY),
        **overrides,
    )


def _make_pd(**overrides: Any) -> PortfolioDecision:
    return PortfolioDecision(
        proposal_id=overrides.pop("proposal_id", "tp-001"),
        risk_decision_id=overrides.pop("risk_decision_id", "rd-001"),
        disposition=overrides.pop("disposition", PortfolioDisposition.WATCHLIST),
        **overrides,
    )


# ======================================================================
# Contract Schema Tests
# ======================================================================


class TestResearchConclusionContract(unittest.TestCase):
    """ResearchConclusion must enforce actionable=false and have all required
    Phase 09 fields."""

    def test_default_actionable_is_false(self):
        rc = _make_rc()
        self.assertFalse(rc.actionable)
        self.assertEqual(rc.decision_scope, "research_only")
        self.assertEqual(rc.schema_version, "phase09.v1")

    def test_rejects_actionable_true(self):
        with self.assertRaises(Exception):
            _make_rc(actionable=True)

    def test_rejects_actionable_true_via_string(self):
        with self.assertRaises(Exception):
            _make_rc(actionable="true")

    def test_rejects_actionable_via_int(self):
        with self.assertRaises(Exception):
            _make_rc(actionable=1)

    def test_confidence_clamped(self):
        # Pydantic ge=0.0 / le=1.0 rejects out-of-bounds before validator
        with self.assertRaises(Exception):
            _make_rc(confidence=-0.5)
        with self.assertRaises(Exception):
            _make_rc(confidence=1.5)
        # Boundary values are accepted
        rc = _make_rc(confidence=0.0)
        self.assertEqual(rc.confidence, 0.0)
        rc2 = _make_rc(confidence=1.0)
        self.assertEqual(rc2.confidence, 1.0)

    def test_degraded_research_conclusion(self):
        drc = degraded_research_conclusion("000001.SZ", "2026-06-13", "provider failure")
        self.assertEqual(drc.recommendation, ResearchRecommendation.INSUFFICIENT_DATA)
        self.assertEqual(drc.confidence, 0.0)
        self.assertIn("provider failure", drc.summary)
        self.assertIn("provider failure", drc.uncertainties)
        self.assertFalse(drc.actionable)

    def test_full_construction(self):
        rc = _make_rc(
            bull_case="Strong earnings beat",
            bear_case="Valuation stretched",
            uncertainties=["Rate decision pending", "FX headwind"],
            confidence=0.7,
            provider_coverage={"market": {"available": True}},
        )
        self.assertEqual(rc.bull_case, "Strong earnings beat")
        self.assertEqual(len(rc.uncertainties), 2)
        self.assertAlmostEqual(rc.confidence, 0.7)


class TestTraderProposalContract(unittest.TestCase):
    """TraderProposal must enforce actionable=false and advisory-only scope."""

    def test_default_actionable_is_false(self):
        tp = _make_tp()
        self.assertFalse(tp.actionable)
        self.assertEqual(tp.decision_scope, "advisory_only")

    def test_rejects_actionable_true(self):
        with self.assertRaises(Exception):
            _make_tp(actionable=True)

    def test_all_candidate_actions(self):
        for action in TraderCandidateAction:
            tp = _make_tp(candidate_action=action)
            self.assertEqual(tp.candidate_action, action)

    def test_position_cap_clamped(self):
        # Pydantic ge=0.0 / le=100.0 rejects out-of-bounds
        with self.assertRaises(Exception):
            _make_tp(position_cap_pct=150.0)
        with self.assertRaises(Exception):
            _make_tp(position_cap_pct=-10.0)
        # Boundary values
        tp = _make_tp(position_cap_pct=100.0)
        self.assertEqual(tp.position_cap_pct, 100.0)
        tp2 = _make_tp(position_cap_pct=0.0)
        self.assertEqual(tp2.position_cap_pct, 0.0)

    def test_degraded_trader_proposal(self):
        dtp = degraded_trader_proposal("rc-degraded", "insufficient data")
        self.assertEqual(dtp.candidate_action, TraderCandidateAction.AVOID)
        self.assertEqual(dtp.confidence, 0.0)
        self.assertIn("insufficient data", dtp.rationale)
        self.assertIn("rc-degraded", dtp.proposal_id)

    def test_entry_zone_optional(self):
        tp_with = _make_tp(entry_zone="45-50 CNY advisory zone")
        self.assertEqual(tp_with.entry_zone, "45-50 CNY advisory zone")
        tp_without = _make_tp()
        self.assertIsNone(tp_without.entry_zone)

    def test_invalidation_conditions(self):
        tp = _make_tp(invalidation_conditions=["gap above 50", "negative surprise"])
        self.assertEqual(len(tp.invalidation_conditions), 2)


class TestRiskDecisionContract(unittest.TestCase):
    """RiskDecision must enforce actionable=false and risk_review_only scope."""

    def test_default_actionable_is_false(self):
        rd = _make_rd()
        self.assertFalse(rd.actionable)
        self.assertEqual(rd.decision_scope, "risk_review_only")

    def test_rejects_actionable_true(self):
        with self.assertRaises(Exception):
            _make_rd(actionable=True)

    def test_all_verdicts(self):
        for verdict in RiskVerdict:
            rd = _make_rd(verdict=verdict)
            self.assertEqual(rd.verdict, verdict)

    def test_risk_factors_and_constraints(self):
        rd = _make_rd(
            risk_factors=["high volatility", "policy risk"],
            constraints=["max 2% exposure"],
            missing_evidence=["Q3 earnings data"],
        )
        self.assertEqual(len(rd.risk_factors), 2)
        self.assertEqual(len(rd.constraints), 1)
        self.assertEqual(len(rd.missing_evidence), 1)

    def test_risk_levels(self):
        for level in RiskLevel:
            rd = _make_rd(risk_level=level)
            self.assertEqual(rd.risk_level, level)


class TestPortfolioDecisionContract(unittest.TestCase):
    """PortfolioDecision must enforce actionable=false,
    execution_signal=ResearchOnly, and portfolio_advisory scope."""

    def test_defaults(self):
        pd = _make_pd()
        self.assertFalse(pd.actionable)
        self.assertEqual(pd.decision_scope, "portfolio_advisory")
        self.assertEqual(pd.execution_signal, "ResearchOnly")
        self.assertEqual(pd.schema_version, "phase09.v1")

    def test_rejects_actionable_true(self):
        with self.assertRaises(Exception):
            _make_pd(actionable=True)

    def test_execution_signal_is_immutable_literal(self):
        pd = _make_pd()
        self.assertEqual(pd.execution_signal, EXECUTION_SIGNAL)
        self.assertEqual(pd.execution_signal, "ResearchOnly")

    def test_all_dispositions(self):
        for disp in PortfolioDisposition:
            pd = _make_pd(disposition=disp)
            self.assertEqual(pd.disposition, disp)

    def test_review_triggers(self):
        pd = _make_pd(
            review_triggers=["new earnings report", "policy change"],
            portfolio_notes="Watch for catalyst.",
        )
        self.assertEqual(len(pd.review_triggers), 2)
        self.assertEqual(pd.portfolio_notes, "Watch for catalyst.")

    def test_exposure_cap_clamped(self):
        # Pydantic ge=0.0 / le=100.0 rejects out-of-bounds
        with self.assertRaises(Exception):
            _make_pd(exposure_cap_pct=150.0)
        with self.assertRaises(Exception):
            _make_pd(exposure_cap_pct=-5.0)
        # Boundary values
        pd = _make_pd(exposure_cap_pct=100.0)
        self.assertEqual(pd.exposure_cap_pct, 100.0)
        pd2 = _make_pd(exposure_cap_pct=0.0)
        self.assertEqual(pd2.exposure_cap_pct, 0.0)


# ======================================================================
# Runtime Profile Tests
# ======================================================================


class TestRuntimeProfile(unittest.TestCase):
    """RuntimeProfile configuration and enforcement."""

    def test_deterministic_verification_allows_bridge_llm(self):
        profile = RuntimeProfile.DETERMINISTIC_VERIFICATION
        self.assertTrue(profile.allows_bridge_llm)
        self.assertFalse(profile.requires_real_llm)
        self.assertTrue(profile.is_phase09_legal)
        self.assertEqual(profile.decision_scope, "research_only")
        self.assertFalse(profile.actionable)
        self.assertEqual(profile.execution_signal, "ResearchOnly")

    def test_live_research_requires_real_llm(self):
        profile = RuntimeProfile.LIVE_RESEARCH
        self.assertFalse(profile.allows_bridge_llm)
        self.assertTrue(profile.requires_real_llm)
        self.assertTrue(profile.is_phase09_legal)
        self.assertEqual(profile.decision_scope, "research_only")
        self.assertFalse(profile.actionable)
        self.assertEqual(profile.execution_signal, "ResearchOnly")

    def test_production_execution_is_not_phase09_legal(self):
        profile = RuntimeProfile.PRODUCTION_EXECUTION
        self.assertFalse(profile.is_phase09_legal)

    def test_resolve_profile_default(self):
        self.assertEqual(
            resolve_profile(),
            RuntimeProfile.DETERMINISTIC_VERIFICATION,
        )

    def test_resolve_profile_with_bridge(self):
        self.assertEqual(
            resolve_profile(has_bridge_llm=True, has_real_llm=False),
            RuntimeProfile.DETERMINISTIC_VERIFICATION,
        )

    def test_resolve_profile_with_real_llm(self):
        self.assertEqual(
            resolve_profile(has_bridge_llm=False, has_real_llm=True),
            RuntimeProfile.LIVE_RESEARCH,
        )

    def test_resolve_profile_with_explicit_override(self):
        self.assertEqual(
            resolve_profile(
                RuntimeProfile.LIVE_RESEARCH,
                has_bridge_llm=True,
                has_real_llm=False,
            ),
            RuntimeProfile.LIVE_RESEARCH,
        )

    def test_require_live_research_clients_passes_with_all_clients(self):
        require_live_research_clients(
            profile=RuntimeProfile.LIVE_RESEARCH,
            bull_llm="real",
            bear_llm="real",
            research_manager_llm="real",
        )

    def test_require_live_research_clients_fails_with_missing_bull(self):
        with self.assertRaises(LiveResearchMisconfiguredError):
            require_live_research_clients(
                profile=RuntimeProfile.LIVE_RESEARCH,
                bull_llm=None,
                bear_llm="real",
                research_manager_llm="real",
            )

    def test_require_live_research_clients_fails_with_all_missing(self):
        with self.assertRaises(LiveResearchMisconfiguredError):
            require_live_research_clients(
                profile=RuntimeProfile.LIVE_RESEARCH,
                bull_llm=None,
                bear_llm=None,
                research_manager_llm=None,
            )

    def test_require_live_research_allows_missing_for_deterministic(self):
        require_live_research_clients(
            profile=RuntimeProfile.DETERMINISTIC_VERIFICATION,
            bull_llm=None,
            bear_llm=None,
        )

    def test_profile_metadata_for_deterministic(self):
        meta = profile_metadata(RuntimeProfile.DETERMINISTIC_VERIFICATION)
        self.assertEqual(meta["runtime_profile"], "deterministic_verification")
        self.assertTrue(meta["allows_bridge_llm"])
        self.assertFalse(meta["requires_real_llm"])
        self.assertEqual(meta["execution_signal"], "ResearchOnly")
        self.assertFalse(meta["actionable"])

    def test_profile_metadata_for_live_research(self):
        meta = profile_metadata(RuntimeProfile.LIVE_RESEARCH)
        self.assertEqual(meta["runtime_profile"], "live_research")
        self.assertFalse(meta["allows_bridge_llm"])
        self.assertTrue(meta["requires_real_llm"])
        self.assertEqual(meta["execution_signal"], "ResearchOnly")


# ======================================================================
# Research-Only Stop Condition Tests
# ======================================================================


class TestResearchOnlyStopCondition(unittest.TestCase):
    """Phase 09 must stop before signal processing, QMT, and trade memory."""

    def test_execution_signal_constant_is_research_only(self):
        self.assertEqual(EXECUTION_SIGNAL, "ResearchOnly")

    def test_portfolio_decision_has_research_only_signal(self):
        pd = _make_pd()
        self.assertEqual(pd.execution_signal, "ResearchOnly")

    def test_no_contract_has_executable_action_types(self):
        """Assert that Phase 09 contracts use advisory enum values, not
        executable action types like 'Buy' / 'Sell'."""
        rc = _make_rc()
        self.assertIn(
            rc.recommendation.value,
            ("buy_bias", "hold_bias", "sell_bias", "insufficient_data"),
        )
        tp = _make_tp()
        self.assertIn(
            tp.candidate_action.value,
            ("observe", "consider_buy", "hold", "consider_reduce", "avoid"),
        )
        rd = _make_rd()
        self.assertIn(
            rd.verdict.value,
            ("allow_advisory", "needs_more_data", "reject_proposal"),
        )
        pd = _make_pd()
        self.assertIn(
            pd.disposition.value,
            ("watchlist", "continue_research", "advisory_rejected"),
        )

    def test_decision_scopes_are_distinct(self):
        """Each contract level has a unique decision_scope."""
        scopes = [
            _make_rc().decision_scope,
            _make_tp().decision_scope,
            _make_rd().decision_scope,
            _make_pd().decision_scope,
        ]
        self.assertEqual(len(set(scopes)), 4, f"duplicate scopes: {scopes}")

    def test_all_actionable_are_false(self):
        self.assertFalse(_make_rc().actionable)
        self.assertFalse(_make_tp().actionable)
        self.assertFalse(_make_rd().actionable)
        self.assertFalse(_make_pd().actionable)


class TestDegradedResults(unittest.TestCase):
    """Degraded Phase 09 contracts must be typed, never free-text."""

    def test_degraded_research_conclusion_is_typed(self):
        drc = degraded_research_conclusion("600519.SH", "2026-06-13", "all providers down")
        self.assertIsInstance(drc, ResearchConclusion)
        self.assertEqual(drc.recommendation, ResearchRecommendation.INSUFFICIENT_DATA)

    def test_degraded_trader_proposal_is_typed(self):
        dtp = degraded_trader_proposal("rc-001", "provider empty")
        self.assertIsInstance(dtp, TraderProposal)
        self.assertEqual(dtp.candidate_action, TraderCandidateAction.AVOID)

    def test_degraded_research_never_becomes_permission_to_proceed(self):
        drc = degraded_research_conclusion("600519.SH", "2026-06-13", "no data")
        self.assertLess(drc.confidence, 0.5)
        self.assertEqual(drc.recommendation, ResearchRecommendation.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()

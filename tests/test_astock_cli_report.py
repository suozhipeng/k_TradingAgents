import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest
from rich.console import Console

import cli.main as m
from cli.models import AnalystType
from tradingagents.astock import AStockGraphReport


@pytest.mark.unit
class TestAStockCliReport(unittest.TestCase):
    def _make_report(self, status: str = "partial") -> AStockGraphReport:
        return AStockGraphReport(
            symbol="600519.SH",
            normalized_symbol="600519.SH",
            trade_date="2026-06-10",
            source="cli",
            sections_requested=("market", "news", "fundamentals", "announcements", "research"),
            astock_analysis={
                "symbol": "600519.SH",
                "normalized_symbol": "600519.SH",
                "summary": "A-share bridge payload assembled",
                "missing_sections": ["research"],
            },
            astock_sections={
                "market": {
                    "status": "ok",
                    "source": "fake-market",
                    "summary": "market snapshot ok",
                    "data": [1, 2, 3],
                },
                "news": {
                    "status": "ok",
                    "source": "fake-news",
                    "summary": "news snapshot ok",
                    "data": {"items": 2},
                },
                "fundamentals": {
                    "status": "ok",
                    "source": "fake-fundamentals",
                    "summary": "fundamentals snapshot ok",
                    "data": {"fields": 37},
                },
                "announcements": {
                    "status": "error",
                    "source": "cninfo",
                    "summary": "announcement provider unavailable",
                    "error": "provider unavailable",
                    "data": [],
                },
                "research": {
                    "status": "empty",
                    "source": "iwencai",
                    "summary": "iwencai cookie missing",
                    "error": "ASTOCK_IWENCAI_COOKIE not configured",
                    "data": [],
                },
            },
            section_results={
                "market": {
                    "status": "ok",
                    "source": "fake-market",
                    "summary": "market snapshot ok",
                    "has_data": True,
                    "data_shape": {"kind": "sequence", "size": 3},
                },
                "news": {
                    "status": "ok",
                    "source": "fake-news",
                    "summary": "news snapshot ok",
                    "has_data": True,
                    "data_shape": {"kind": "mapping", "size": 2},
                },
                "fundamentals": {
                    "status": "ok",
                    "source": "fake-fundamentals",
                    "summary": "fundamentals snapshot ok",
                    "has_data": True,
                    "data_shape": {"kind": "mapping", "size": 37},
                },
                "announcements": {
                    "status": "error",
                    "source": "cninfo",
                    "summary": "announcement provider unavailable",
                    "has_data": False,
                    "data_shape": {"kind": "sequence", "size": 0},
                },
                "research": {
                    "status": "empty",
                    "source": "iwencai",
                    "summary": "iwencai cookie missing",
                    "has_data": False,
                    "data_shape": {"kind": "sequence", "size": 0},
                },
            },
            bull_view="Bull bridge output: focus on operating leverage.",
            bear_view="Bear bridge output: watch conversion risk.",
            research_manager_conclusion="**Recommendation**: Hold",
            provider_coverage={
                "market": {"source": "fake-market", "status": "ok", "available": True},
                "news": {"source": "fake-news", "status": "ok", "available": True},
                "fundamentals": {"source": "fake-fundamentals", "status": "ok", "available": True},
                "announcements": {"source": "cninfo", "status": "error", "available": False},
                "research": {"source": "iwencai", "status": "empty", "available": False},
            },
            missing_data_notes=[
                "announcements: announcement provider unavailable",
                "research: iwencai cookie missing",
            ],
            degradation_notes=[
                "announcements [error]: announcement provider unavailable",
                "research [empty]: iwencai cookie missing",
            ],
            bull_output={"investment_debate_state": {"bull_history": "Bull bridge output: focus on operating leverage."}},
            bear_output={"investment_debate_state": {"bear_history": "Bear bridge output: watch conversion risk."}},
            research_manager_output={"investment_plan": "**Recommendation**: Hold"},
            investment_plan="**Recommendation**: Hold",
            runtime_trace=(
                "AStock Analyst",
                "Bull Researcher",
                "Bear Researcher",
                "Research Manager",
                "Trader",
                "Aggressive Risk Analyst",
                "Conservative Risk Analyst",
                "Neutral Risk Analyst",
                "Portfolio Manager",
            ),
            llm_prompts={"bull": ["bull prompt"], "bear": ["bear prompt"], "research_manager": ["manager prompt"]},
            summary="A-share bridge payload assembled",
            status=status,
            metadata={"bridge_mode": "astock_research_bridge", "state_keys": ["astock_analysis"]},
            runtime_profile="deterministic_verification",
            research_conclusion={
                "recommendation": "hold_bias",
                "confidence": 0.45,
                "summary": "**Recommendation**: Hold",
            },
            trader_proposal={
                "candidate_action": "hold",
                "position_cap_pct": 5.0,
                "rationale": "Advisory hold until missing evidence is resolved.",
            },
            risk_decision={
                "verdict": "needs_more_data",
                "risk_level": "medium",
                "constraints": ["ResearchOnly stop condition remains mandatory."],
            },
            portfolio_decision={
                "disposition": "continue_research",
                "exposure_cap_pct": 5.0,
                "portfolio_notes": "Keep this name in advisory research until coverage improves.",
            },
        )

    def test_display_astock_report_renders_schema_fields(self):
        report = self._make_report()
        capture = Console(record=True, width=120)

        m.display_astock_report(report, render_console=capture)
        text = capture.export_text()

        self.assertIn("A 股 Analysis Report", text)
        self.assertIn("600519.SH", text)
        self.assertIn("Five-layer Section Status", text)
        self.assertIn("market snapshot ok", text)
        self.assertIn("A-share bridge payload assembled", text)
        self.assertIn("Bull bridge output", text)
        self.assertIn("Bear bridge output", text)
        self.assertIn("Hold", text)
        self.assertIn("iwencai", text)
        self.assertIn("Missing Data Notes", text)
        self.assertIn("Degradation Notes", text)
        self.assertIn("Runtime Trace", text)
        self.assertIn("Phase 09 Advisory Outputs", text)
        self.assertIn("continue_research", text)

    def test_save_astock_report_to_disk_writes_display_schema_artifacts(self):
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            report_file = m.save_astock_report_to_disk(report, save_path)

            self.assertTrue(report_file.exists())
            json_file = save_path / "astock_report.json"
            self.assertTrue(json_file.exists())
            md_text = report_file.read_text(encoding="utf-8")
            json_text = json.loads(json_file.read_text(encoding="utf-8"))

        self.assertIn("Runtime Mode: astock_research_bridge", md_text)
        self.assertIn("Decision Scope: research_only", md_text)
        self.assertIn("Actionable: False", md_text)
        self.assertIn("五层 Section 状态", md_text)
        self.assertIn("Phase 09 Advisory Outputs", md_text)
        self.assertIn("Trader Proposal", md_text)
        self.assertIn("Runtime Trace", md_text)
        self.assertEqual(json_text["ticker"], "600519.SH")
        self.assertEqual(json_text["decision_scope"], "research_only")
        self.assertFalse(json_text["actionable"])
        self.assertIn("section_results", json_text)
        self.assertIn("portfolio_decision", json_text)
        self.assertEqual(json_text["status"], "partial")

    def test_run_analysis_routes_astock_ticker_to_runtime_report(self):
        fake_report = self._make_report()
        fake_runtime = mock.Mock()
        fake_runtime.run.return_value = fake_report
        fake_config = dict(m.DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_config.update({"results_dir": tmpdir, "data_cache_dir": tmpdir})
            selections = {
                "ticker": "600519.SH",
                "analysis_date": "2026-06-10",
                "asset_type": "stock",
                "research_depth": 1,
                "shallow_thinker": "deepseek-v4-pro",
                "deep_thinker": "kimi-k2.5",
                "backend_url": "https://opencode.ai/zen/go/v1",
                "llm_provider": "openai",
                "output_language": "English",
                "analysts": [AnalystType.MARKET],
            }

            capture = Console(record=True, width=120)
            with mock.patch.object(m, "DEFAULT_CONFIG", fake_config), \
                 mock.patch.object(m, "get_user_selections", return_value=selections), \
                 mock.patch.object(m, "AStockGraphRuntime", return_value=fake_runtime) as runtime_cls, \
                 mock.patch.object(m.typer, "prompt", side_effect=["N", "N"]), \
                 mock.patch.object(m, "TradingAgentsGraph") as graph_cls, \
                 mock.patch.object(m, "console", capture):
                m.run_analysis(checkpoint=False)

        runtime_cls.assert_called_once_with(symbol="600519.SH", trade_date="2026-06-10", source="cli")
        fake_runtime.run.assert_called_once()
        graph_cls.assert_not_called()
        text = capture.export_text()
        self.assertIn("A 股 analysis complete!", text)
        self.assertIn("Ticker:", text)
        self.assertIn("A-share bridge payload assembled", text)

    def test_generic_cli_helpers_still_handle_legacy_state(self):
        legacy_state = {
            "market_report": "Market report",
            "sentiment_report": "Sentiment report",
            "news_report": "News report",
            "fundamentals_report": "Fundamentals report",
            "investment_debate_state": {
                "bull_history": "Bull history",
                "bear_history": "Bear history",
                "judge_decision": "Manager decision",
            },
            "trader_investment_plan": "Trader plan",
            "risk_debate_state": {
                "aggressive_history": "Aggressive history",
                "conservative_history": "Conservative history",
                "neutral_history": "Neutral history",
                "judge_decision": "Portfolio manager decision",
            },
        }
        capture = Console(record=True, width=120)
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir)
            with mock.patch.object(m, "console", capture):
                m.display_complete_report(legacy_state)
                report_file = m.save_report_to_disk(legacy_state, "600519.SH", save_path)
                self.assertTrue(report_file.exists())
                report_text = report_file.read_text(encoding="utf-8")

        self.assertIn("Complete Analysis Report", capture.export_text())
        self.assertIn("Trader plan", report_text)


if __name__ == "__main__":
    unittest.main()

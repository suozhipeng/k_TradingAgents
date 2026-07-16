import unittest
from unittest.mock import patch

from tradingagents.astock import (
    AStockGraphReport,
    AStockGraphRuntime,
    build_astock_research_bridge_state,
    build_astock_runtime_llms,
    run_astock_research_bridge,
)
from tradingagents.graph import ConditionalLogic
from tradingagents.graph.trading_graph import TradingAgentsGraph


class FakeAStockInterface:
    def __init__(self):
        self.calls = []

    def to_payload(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return {
            "symbol": symbol,
            "normalized_symbol": symbol,
            "summary": "A-share bridge payload assembled",
            "sections": {
                "market": {
                    "status": "ok",
                    "source": "fake-market",
                    "summary": "market snapshot ok",
                    "data": {"kline": [1, 2, 3]},
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
        }


class AStockGraphRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.interface = FakeAStockInterface()

    def test_runtime_entry_initialization_exposes_shared_bridge_contract(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-10",
        )

        description = runtime.describe()
        self.assertEqual(description["mode"], "astock_research_bridge")
        self.assertEqual(description["decision_scope"], "research_only")
        self.assertFalse(description["actionable"])
        self.assertEqual(description["entrypoint"], "AStockGraphRuntime.run")
        self.assertEqual(description["state_flow"], [
            "AStockAnalyst",
            "Bull Researcher",
            "Bear Researcher",
            "Research Manager",
        ])
        self.assertIn("astock_analysis", description["output_fields"])
        self.assertIn("missing provider", " ".join(description["fallback_behavior"]))

        state = runtime.build_state()
        self.assertEqual(self.interface.calls[0][1]["sections"], ("market", "news", "fundamentals", "announcements", "research"))
        self.assertEqual(state["company_of_interest"], "600519.SH")
        self.assertIn("astock_analysis", state)
        self.assertIn("astock_sections", state)
        self.assertIn("market_report", state)
        self.assertIn("news_report", state)
        self.assertIn("fundamentals_report", state)
        self.assertIn("iwencai cookie missing", state["astock_analysis"]["sections"]["research"]["summary"])
        self.assertIn("research", state["astock_analysis"]["missing_sections"])

        report = runtime.run()
        self.assertIsInstance(report, AStockGraphReport)
        self.assertEqual(
            report.runtime_trace,
            (
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
        )
        self.assertEqual(report.runtime_mode, "astock_research_bridge")
        self.assertEqual(report.decision_scope, "research_only")
        self.assertFalse(report.actionable)
        self.assertEqual(report.execution_signal, "ResearchOnly")
        self.assertEqual(report.ticker, "600519.SH")
        self.assertEqual(report.status, "partial")
        self.assertTrue(any("research" in note for note in report.missing_data_notes))
        self.assertIn("announcement", " ".join(report.missing_data_notes))
        self.assertIn("iwencai", report.provider_coverage["research"]["source"])
        self.assertEqual(report.section_results["market"]["status"], "ok")
        self.assertEqual(report.section_results["research"]["status"], "empty")
        self.assertIn("Bear bridge output", report.bear_view)
        self.assertIn("iwencai cookie missing", " ".join(report.degradation_notes))
        self.assertIn("Hold", report.research_manager_conclusion)
        payload = report.to_dict()
        self.assertEqual(payload["mode"], "astock_research_bridge")
        self.assertEqual(payload["runtime_mode"], "astock_research_bridge")
        self.assertEqual(payload["decision_scope"], "research_only")
        self.assertFalse(payload["actionable"])
        self.assertEqual(payload["execution_signal"], "ResearchOnly")
        self.assertEqual(payload["ticker"], "600519.SH")
        self.assertIn("section_results", payload)
        self.assertIn("provider_coverage", payload)
        self.assertIn("degradation_notes", payload)
        self.assertIn("trader_proposal", payload)
        self.assertIn("risk_decision", payload)
        self.assertIn("portfolio_decision", payload)
        self.assertEqual(payload["final_trade_decision"], report.final_trade_decision)
        legacy_state = report.to_legacy_state()
        self.assertIn("astock_display_report", legacy_state)
        self.assertIn("astock_runtime_report", legacy_state)
        self.assertEqual(legacy_state["astock_runtime_report"]["symbol"], "600519.SH")
        self.assertIn("trader_proposal", legacy_state["phase09_advisory"])

    def test_bridge_runtime_runs_to_research_manager_and_keeps_fallback_semantics(self):
        result = run_astock_research_bridge(
            "600519.SH",
            interface=self.interface,
            trade_date="2026-06-10",
        )

        self.assertEqual(
            result["runtime_trace"],
            [
                "AStock Analyst",
                "Bull Researcher",
                "Bear Researcher",
                "Research Manager",
                "Trader",
                "Aggressive Risk Analyst",
                "Conservative Risk Analyst",
                "Neutral Risk Analyst",
                "Portfolio Manager",
            ],
        )
        self.assertIn("**Recommendation**: Hold", result["investment_plan"])
        self.assertIn("A-share bridge payload assembled", result["llm_prompts"]["bull"][0])
        self.assertIn("A-share structured snapshot", result["llm_prompts"]["bull"][0])
        self.assertIn("iwencai cookie missing", result["llm_prompts"]["research_manager"][0])
        self.assertIn("announcement provider unavailable", result["llm_prompts"]["bear"][0])
        self.assertEqual(result["state"]["investment_debate_state"]["count"], 2)
        self.assertIn("Bear bridge output", result["bear_output"]["investment_debate_state"]["current_response"])

    def test_astock_runtime_does_not_store_or_process_research_as_trade_decision(self):
        graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
        graph.config = {"checkpoint_enabled": False, "data_cache_dir": "/tmp"}
        graph.curr_state = None
        stored_decisions = []
        graph.memory_log = type(
            "MemoryLogStub",
            (),
            {
                "get_past_context": lambda self, ticker: "",
                "store_decision": lambda self, **kwargs: stored_decisions.append(kwargs),
            },
        )()
        graph.resolve_instrument_context = lambda ticker, asset_type="stock": f"context:{ticker}:{asset_type}"
        graph._log_state = lambda *args, **kwargs: None
        processed_signals = []
        graph.process_signal = lambda signal: processed_signals.append(signal)

        report = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-10",
        ).run()

        with patch("tradingagents.graph.trading_graph.AStockGraphRuntime") as runtime_cls:
            runtime_cls.return_value.run.return_value = report
            final_state, signal = graph._run_astock_runtime("600519.SH", "2026-06-10")

        self.assertEqual(signal, "ResearchOnly")
        self.assertEqual(final_state["decision_scope"], "research_only")
        self.assertFalse(final_state["actionable"])
        self.assertEqual(stored_decisions, [])
        self.assertEqual(processed_signals, [])

    def test_trading_graph_routes_a_share_ticker_to_astock_runtime(self):
        graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
        graph.config = {"checkpoint_enabled": False, "data_cache_dir": "/tmp"}
        graph.curr_state = None
        graph.memory_log = type(
            "MemoryLogStub",
            (),
            {
                "get_past_context": lambda self, ticker: "",
                "store_decision": lambda *args, **kwargs: None,
            },
        )()
        graph._resolve_pending_entries = lambda *args, **kwargs: None
        graph._log_state = lambda *args, **kwargs: None
        graph.process_signal = lambda signal: f"processed:{signal}"
        graph.resolve_instrument_context = lambda ticker, asset_type="stock": f"context:{ticker}:{asset_type}"

        with patch.object(
            TradingAgentsGraph,
            "_run_astock_runtime",
            return_value=({"final_trade_decision": "ASTOCK"}, "processed:ASTOCK"),
        ) as run_astock:
            with patch.object(TradingAgentsGraph, "_run_graph") as run_generic:
                final_state, decision = TradingAgentsGraph.propagate(graph, "600519.SH", "2026-06-10")

        run_astock.assert_called_once()
        run_generic.assert_not_called()
        self.assertEqual(final_state["final_trade_decision"], "ASTOCK")
        self.assertEqual(decision, "processed:ASTOCK")

    def test_trading_graph_keeps_generic_path_for_non_a_share_ticker(self):
        graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
        graph.config = {"checkpoint_enabled": False, "data_cache_dir": "/tmp"}
        graph.curr_state = None
        graph.memory_log = type(
            "MemoryLogStub",
            (),
            {
                "get_past_context": lambda self, ticker: "",
                "store_decision": lambda *args, **kwargs: None,
            },
        )()
        resolve_pending_entries = patch.object(TradingAgentsGraph, "_resolve_pending_entries")
        graph._log_state = lambda *args, **kwargs: None
        graph.process_signal = lambda signal: f"processed:{signal}"
        graph.resolve_instrument_context = lambda ticker, asset_type="stock": f"context:{ticker}:{asset_type}"

        with resolve_pending_entries as pending_entries, patch.object(
            TradingAgentsGraph, "_run_astock_runtime"
        ) as run_astock, patch.object(
            TradingAgentsGraph,
            "_run_graph",
            return_value=({"final_trade_decision": "GENERIC"}, "processed:GENERIC"),
        ) as run_generic:
            final_state, decision = TradingAgentsGraph.propagate(graph, "AAPL", "2026-06-10")

        run_astock.assert_not_called()
        run_generic.assert_called_once()
        pending_entries.assert_called_once_with("AAPL")
        self.assertEqual(final_state["final_trade_decision"], "GENERIC")
        self.assertEqual(decision, "processed:GENERIC")

    def test_conditional_logic_routes_a_share_tickers_to_astock_bridge(self):
        logic = ConditionalLogic()
        self.assertEqual(
            logic.should_route_to_astock_analyst({"company_of_interest": "600519.SH"}),
            "AStock Analyst",
        )
        self.assertEqual(
            logic.should_route_to_astock_analyst({"company_of_interest": "AAPL"}),
            "Bull Researcher",
        )


# ======================================================================
# Phase 09: Runtime Profile Extension Tests
# ======================================================================


class Phase09RuntimeProfileTests(unittest.TestCase):
    """Phase 09 runtime profile isolation on AStockGraphRuntime."""

    def setUp(self):
        self.interface = FakeAStockInterface()

    def test_runtime_describe_includes_runtime_profile(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        description = runtime.describe()
        self.assertIn("runtime_profile", description)
        self.assertEqual(description["runtime_profile"], "deterministic_verification")
        self.assertIn("phase09_state_flow", description)
        self.assertIn("phase09_stop_condition", description)
        self.assertIn("research_conclusion", description["output_fields"])

    def test_runtime_describe_shows_live_research_when_llm_provided(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
            bull_llm="stub-real",
        )
        description = runtime.describe()
        self.assertEqual(description["runtime_profile"], "live_research")

    def test_build_astock_runtime_llms_uses_config_models(self):
        config = {
            "llm_provider": "deepseek",
            "quick_think_llm": "deepseek-v4-flash",
            "deep_think_llm": "deepseek-v4-pro",
            "backend_url": "https://api.deepseek.com",
            "temperature": None,
            "openai_reasoning_effort": None,
            "anthropic_effort": None,
        }

        class FakeClient:
            def __init__(self, llm):
                self._llm = llm

            def get_llm(self):
                return self._llm

        with patch("tradingagents.astock.runtime.create_llm_client") as create_client:
            create_client.side_effect = [FakeClient("quick-llm"), FakeClient("deep-llm")]
            payload = build_astock_runtime_llms(config)

        self.assertEqual(payload["runtime_profile"], "live_research")
        self.assertEqual(payload["bull_llm"], "quick-llm")
        self.assertEqual(payload["bear_llm"], "quick-llm")
        self.assertEqual(payload["research_manager_llm"], "deep-llm")

    def test_run_produces_research_conclusion_on_report(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        report = runtime.run()
        self.assertIsNotNone(report.research_conclusion)
        self.assertIn("symbol", report.research_conclusion)
        self.assertEqual(report.research_conclusion["symbol"], "600519.SH")
        self.assertFalse(report.research_conclusion["actionable"])
        self.assertEqual(report.research_conclusion["decision_scope"], "research_only")
        self.assertIsNotNone(report.trader_proposal)
        self.assertIsNotNone(report.risk_decision)
        self.assertIsNotNone(report.portfolio_decision)
        # Runtime profile should be set
        self.assertEqual(report.runtime_profile, "deterministic_verification")

    def test_report_to_dict_includes_phase09_fields_when_populated(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        report = runtime.run()
        payload = report.to_dict()
        self.assertIn("research_conclusion", payload)
        self.assertFalse(payload["research_conclusion"]["actionable"])
        self.assertIn("trader_proposal", payload)
        self.assertIn("risk_decision", payload)
        self.assertIn("portfolio_decision", payload)
        # runtime_profile should appear when set
        self.assertIn("runtime_profile", payload)

    def test_report_to_legacy_state_includes_phase09_advisory(self):
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        report = runtime.run()
        legacy = report.to_legacy_state()
        self.assertIn("phase09_advisory", legacy)
        self.assertEqual(legacy["phase09_advisory"]["execution_signal"], "ResearchOnly")
        self.assertFalse(legacy["phase09_advisory"]["actionable"])
        self.assertEqual(legacy["phase09_advisory"]["runtime_profile"], "deterministic_verification")
        self.assertIn("risk_decision", legacy["phase09_advisory"])

    def test_run_does_not_call_signal_processing_or_qmt(self):
        """Confirm that Phase 09 run does not invoke signal processing or QMT
        by verifying the report's execution_signal and absence of any
        broker-related fields."""
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        report = runtime.run()
        self.assertEqual(report.execution_signal, "ResearchOnly")
        self.assertFalse(report.actionable)
        payload = report.to_dict()
        # Verify no signal-processing or broker artifacts leaked
        self.assertNotIn("signal", payload)
        self.assertNotIn("broker", payload.get("metadata", {}))
        self.assertNotIn("qmt", str(payload.get("metadata", {})).lower())
        # Verify no trade-decision memory fields
        self.assertNotIn("store_decision", payload)
        self.assertNotIn("trade_decision", payload.get("phase09_advisory", {}) if hasattr(report, 'to_legacy_state') else "")

    def test_partial_run_still_produces_phase09_advisory_chain(self):
        """Partial provider coverage should still produce the advisory chain
        with a needs-more-data risk verdict."""
        runtime = AStockGraphRuntime(
            symbol="600519.SH",
            interface=self.interface,
            trade_date="2026-06-13",
        )
        report = runtime.run()
        self.assertIsNotNone(report.research_conclusion)
        self.assertFalse(report.research_conclusion["summary"].startswith("Degraded"))
        self.assertEqual(report.trader_proposal["candidate_action"], "hold")
        self.assertEqual(report.risk_decision["verdict"], "needs_more_data")
        self.assertEqual(report.portfolio_decision["disposition"], "continue_research")


if __name__ == "__main__":
    unittest.main()

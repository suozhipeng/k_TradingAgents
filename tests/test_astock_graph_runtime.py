import unittest
from unittest.mock import patch

from tradingagents.astock import AStockGraphReport, AStockGraphRuntime, build_astock_research_bridge_state, run_astock_research_bridge
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
        self.assertEqual(report.runtime_trace, ("AStock Analyst", "Bull Researcher", "Bear Researcher", "Research Manager"))
        self.assertEqual(report.runtime_mode, "astock_research_bridge")
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
        self.assertEqual(payload["ticker"], "600519.SH")
        self.assertIn("section_results", payload)
        self.assertIn("provider_coverage", payload)
        self.assertIn("degradation_notes", payload)
        self.assertEqual(payload["final_trade_decision"], report.final_trade_decision)
        legacy_state = report.to_legacy_state()
        self.assertIn("astock_display_report", legacy_state)
        self.assertIn("astock_runtime_report", legacy_state)
        self.assertEqual(legacy_state["astock_runtime_report"]["symbol"], "600519.SH")

    def test_bridge_runtime_runs_to_research_manager_and_keeps_fallback_semantics(self):
        result = run_astock_research_bridge(
            "600519.SH",
            interface=self.interface,
            trade_date="2026-06-10",
        )

        self.assertEqual(
            result["runtime_trace"],
            ["AStock Analyst", "Bull Researcher", "Bear Researcher", "Research Manager"],
        )
        self.assertIn("**Recommendation**: Hold", result["investment_plan"])
        self.assertIn("A-share bridge payload assembled", result["llm_prompts"]["bull"][0])
        self.assertIn("A-share structured snapshot", result["llm_prompts"]["bull"][0])
        self.assertIn("iwencai cookie missing", result["llm_prompts"]["research_manager"][0])
        self.assertIn("announcement provider unavailable", result["llm_prompts"]["bear"][0])
        self.assertEqual(result["state"]["investment_debate_state"]["count"], 2)
        self.assertIn("Bear bridge output", result["bear_output"]["investment_debate_state"]["current_response"])

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
        graph._resolve_pending_entries = lambda *args, **kwargs: None
        graph._log_state = lambda *args, **kwargs: None
        graph.process_signal = lambda signal: f"processed:{signal}"
        graph.resolve_instrument_context = lambda ticker, asset_type="stock": f"context:{ticker}:{asset_type}"

        with patch.object(TradingAgentsGraph, "_run_astock_runtime") as run_astock:
            with patch.object(
                TradingAgentsGraph,
                "_run_graph",
                return_value=({"final_trade_decision": "GENERIC"}, "processed:GENERIC"),
            ) as run_generic:
                final_state, decision = TradingAgentsGraph.propagate(graph, "AAPL", "2026-06-10")

        run_astock.assert_not_called()
        run_generic.assert_called_once()
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


if __name__ == "__main__":
    unittest.main()

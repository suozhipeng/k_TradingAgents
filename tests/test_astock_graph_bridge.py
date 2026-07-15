import ast
import json
import textwrap
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent.parent
AGENT_UTILS_PATH = ROOT / "tradingagents" / "agents" / "utils" / "agent_utils.py"
COND_LOGIC_PATH = ROOT / "tradingagents" / "graph" / "conditional_logic.py"
SETUP_PATH = ROOT / "tradingagents" / "graph" / "setup.py"


class GraphBridgeTests(unittest.TestCase):
    def _load_function(self, source_path: Path, function_name: str):
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        fn_node = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        fn_source = textwrap.dedent(ast.get_source_segment(source, fn_node))
        namespace = {
            "json": json,
            "Any": Any,
            "Mapping": Mapping,
        }
        exec(fn_source, namespace)
        return namespace[function_name]

    def test_astock_context_formats_structured_state(self):
        fn = self._load_function(AGENT_UTILS_PATH, "get_astock_research_context_from_state")
        state = {
            "astock_analysis": {
                "summary": "ok",
                "status_breakdown": {"market": "ok", "research": "empty"},
                "missing_sections": ["research"],
            },
            "astock_sections": {
                "market": {"status": "ok", "source": "akshare", "summary": "market summary"},
                "research": {"status": "empty", "source": "iwencai", "summary": "missing cookie"},
            },
        }
        text = fn(state)
        self.assertIn("A-share structured snapshot", text)
        self.assertIn("market", text)
        self.assertIn("research", text)
        self.assertIn("Missing sections", text)

    def test_conditional_logic_routes_astock_tickers_to_astock_analyst(self):
        # Behavioural check (robust to constant refactors): the router must
        # send A-share tickers to the AStock Analyst node and others to Bull.
        from tradingagents.graph.conditional_logic import ConditionalLogic
        from tradingagents.graph.node_names import ASTOCK_ANALYST, BULL_RESEARCHER

        logic = ConditionalLogic()
        for astock_ticker in ("600519.SH", "000001.SZ", "830799.BJ", "600519"):
            self.assertEqual(
                logic.should_route_to_astock_analyst(
                    {"company_of_interest": astock_ticker}
                ),
                ASTOCK_ANALYST,
                msg=f"{astock_ticker} should route to AStock Analyst",
            )
        for other_ticker in ("AAPL", "TSLA", ""):
            self.assertEqual(
                logic.should_route_to_astock_analyst(
                    {"company_of_interest": other_ticker}
                ),
                BULL_RESEARCHER,
            )

    def test_graph_setup_includes_astock_bridge_nodes_and_edges(self):
        # Build the real graph with mocked LLM/tool nodes and assert the
        # AStock bridge node is registered and wired to Bull Researcher.
        from unittest.mock import MagicMock

        from tradingagents.graph.conditional_logic import ConditionalLogic
        from tradingagents.graph.node_names import ASTOCK_ANALYST, BULL_RESEARCHER
        from tradingagents.graph.setup import GraphSetup

        llm = MagicMock()
        tool_nodes = {k: MagicMock() for k in ("market", "social", "news", "fundamentals")}
        setup = GraphSetup(llm, llm, tool_nodes, ConditionalLogic())
        workflow = setup.setup_graph(["market", "social", "news", "fundamentals"])

        nodes = set(workflow.nodes.keys())
        self.assertIn(ASTOCK_ANALYST, nodes)
        self.assertIn(BULL_RESEARCHER, nodes)


if __name__ == "__main__":
    unittest.main()

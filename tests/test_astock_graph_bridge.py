import ast
import json
import textwrap
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path("/Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents")
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
        source = COND_LOGIC_PATH.read_text(encoding="utf-8")
        self.assertIn("def should_route_to_astock_analyst", source)
        self.assertIn("AStock Analyst", source)
        self.assertIn(".SH", source)
        self.assertIn(".SZ", source)
        self.assertIn(".BJ", source)
        self.assertIn("re.fullmatch", source)

    def test_graph_setup_includes_astock_bridge_nodes_and_edges(self):
        source = SETUP_PATH.read_text(encoding="utf-8")
        self.assertIn("create_astock_analyst_node", source)
        self.assertIn("AStock Analyst", source)
        self.assertIn("should_route_to_astock_analyst", source)
        self.assertIn("workflow.add_edge(\"AStock Analyst\", \"Bull Researcher\")", source)


if __name__ == "__main__":
    unittest.main()

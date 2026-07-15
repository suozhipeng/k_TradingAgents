"""Structural integrity tests for the LangGraph trading-graph wiring.

These guard against the failure mode called out in the code review: node
names are a stringly-typed protocol shared by ``graph/setup.py`` and
``graph/conditional_logic.py``. A typo in one but not the other produces an
edge to a node that never runs, and LangGraph does not always surface that as
a hard error. Building the real graph and asserting every routed label is a
registered node makes that mismatch a test failure instead of a silent
production bug.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.node_names import (
    AGGRESSIVE_ANALYST,
    ASTOCK_ANALYST,
    BEAR_RESEARCHER,
    BULL_RESEARCHER,
    CONSERVATIVE_ANALYST,
    FIXED_NODES,
    NEUTRAL_ANALYST,
    PORTFOLIO_MANAGER,
    RESEARCH_MANAGER,
    TRADER,
)
from tradingagents.graph.setup import GraphSetup


def _build_workflow(selected_analysts):
    """Build (not compile) the StateGraph with mocked LLM/tool nodes."""
    llm = MagicMock()
    tool_nodes = {
        key: MagicMock()
        for key in ("market", "social", "news", "fundamentals")
    }
    setup = GraphSetup(
        quick_thinking_llm=llm,
        deep_thinking_llm=llm,
        tool_nodes=tool_nodes,
        conditional_logic=ConditionalLogic(),
    )
    return setup.setup_graph(selected_analysts)


def _registered_nodes(workflow):
    return set(workflow.nodes.keys())


@pytest.mark.unit
def test_all_fixed_nodes_are_registered():
    workflow = _build_workflow(["market", "social", "news", "fundamentals"])
    nodes = _registered_nodes(workflow)
    missing = FIXED_NODES - nodes
    assert not missing, f"Fixed nodes not registered in the graph: {missing}"


@pytest.mark.unit
def test_conditional_routing_targets_are_registered_nodes():
    """Every value a router can return must be a registered node label."""
    workflow = _build_workflow(["market", "social", "news", "fundamentals"])
    nodes = _registered_nodes(workflow)
    logic = ConditionalLogic()

    # Debate router: both Bull/Bear entry states plus the terminal case.
    debate_targets = {
        logic.should_continue_debate(
            {"investment_debate_state": {"count": 0, "current_response": "Bull says"}}
        ),
        logic.should_continue_debate(
            {"investment_debate_state": {"count": 0, "current_response": "Bear says"}}
        ),
        logic.should_continue_debate(
            {"investment_debate_state": {"count": 99, "current_response": "Bull says"}}
        ),
    }
    assert debate_targets <= nodes, f"debate routes off-graph: {debate_targets - nodes}"

    # Risk router: aggressive → conservative → neutral cycle plus terminal.
    risk_targets = {
        logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 0, "latest_speaker": "Aggressive"}}
        ),
        logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 0, "latest_speaker": "Conservative"}}
        ),
        logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 0, "latest_speaker": "Neutral"}}
        ),
        logic.should_continue_risk_analysis(
            {"risk_debate_state": {"count": 99, "latest_speaker": "Neutral"}}
        ),
    }
    assert risk_targets <= nodes, f"risk routes off-graph: {risk_targets - nodes}"

    # AStock router: A-share ticker → AStock Analyst, else Bull Researcher.
    astock_targets = {
        logic.should_route_to_astock_analyst({"company_of_interest": "600519.SH"}),
        logic.should_route_to_astock_analyst({"company_of_interest": "AAPL"}),
        logic.should_route_to_astock_analyst({"company_of_interest": ""}),
    }
    assert astock_targets <= nodes, f"astock routes off-graph: {astock_targets - nodes}"

    # Sanity: the expected canonical labels are all present.
    for node in (
        BULL_RESEARCHER,
        BEAR_RESEARCHER,
        RESEARCH_MANAGER,
        ASTOCK_ANALYST,
        TRADER,
        AGGRESSIVE_ANALYST,
        CONSERVATIVE_ANALYST,
        NEUTRAL_ANALYST,
        PORTFOLIO_MANAGER,
    ):
        assert node in nodes


@pytest.mark.unit
def test_analyst_tool_router_labels_match_registered_nodes():
    """should_continue_<analyst> return values must be registered nodes."""
    workflow = _build_workflow(["market", "social", "news", "fundamentals"])
    nodes = _registered_nodes(workflow)
    logic = ConditionalLogic()

    tool_call_msg = MagicMock()
    tool_call_msg.tool_calls = [{"name": "x"}]
    no_tool_msg = MagicMock()
    no_tool_msg.tool_calls = []

    for key in ("market", "social", "news", "fundamentals"):
        router = getattr(logic, f"should_continue_{key}")
        tools_target = router({"messages": [tool_call_msg]})
        clear_target = router({"messages": [no_tool_msg]})
        assert tools_target in nodes, f"{key}: tools target {tools_target!r} off-graph"
        assert clear_target in nodes, f"{key}: clear target {clear_target!r} off-graph"

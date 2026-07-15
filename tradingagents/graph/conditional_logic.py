# TradingAgents/graph/conditional_logic.py

import re

from tradingagents.agents.utils.agent_states import AgentState
from .node_names import (
    AGGRESSIVE_ANALYST,
    ASTOCK_ANALYST,
    BEAR_RESEARCHER,
    BULL_RESEARCHER,
    CONSERVATIVE_ANALYST,
    NEUTRAL_ANALYST,
    PORTFOLIO_MANAGER,
    RESEARCH_MANAGER,
)


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if sentiment-analyst tool round should continue.

        Method name keeps the legacy ``social`` suffix to match the
        ``AnalystType.SOCIAL = "social"`` wire value (saved-config
        back-compat); the returned ``clear_node`` label uses the renamed
        value so it matches the node registered by the execution plan.
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Sentiment"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def should_route_to_astock_analyst(self, state: AgentState) -> str:
        """Route A-share runs through the structured AStockAnalyst bridge."""
        ticker = str(state.get("company_of_interest", "")).strip().upper()
        if not ticker:
            return BULL_RESEARCHER
        if ticker.endswith((".SH", ".SZ", ".BJ")) or re.fullmatch(r"\d{6}(?:\.(?:SH|SZ|BJ))?", ticker):
            return ASTOCK_ANALYST
        return BULL_RESEARCHER

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 3 rounds of back-and-forth between 2 agents
            return RESEARCH_MANAGER
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return BEAR_RESEARCHER
        return BULL_RESEARCHER

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 3 rounds of back-and-forth between 3 agents
            return PORTFOLIO_MANAGER
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return CONSERVATIVE_ANALYST
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return NEUTRAL_ANALYST
        return AGGRESSIVE_ANALYST

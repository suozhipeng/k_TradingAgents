"""Canonical LangGraph node names for the trading graph.

Node names are a string protocol shared by ``graph/setup.py`` (registration
and edges) and ``graph/conditional_logic.py`` (routing return values). When a
literal is mistyped in one place but not the other, LangGraph builds an edge to
a node that never runs and the failure is silent. Centralising the literals
here lets ``setup.py`` and the routers reference the same constant, and lets a
unit test assert every conditional-edge target is a registered node.

Per-analyst node names (e.g. ``"Market Analyst"``, ``"tools_market"``,
``"Msg Clear Market"``) remain owned by ``analyst_execution.AnalystNodeSpec``
because they are generated per selected analyst; this module covers the fixed
downstream nodes.
"""

from __future__ import annotations

# --- Research debate -------------------------------------------------------
BULL_RESEARCHER = "Bull Researcher"
BEAR_RESEARCHER = "Bear Researcher"
RESEARCH_MANAGER = "Research Manager"
ASTOCK_ANALYST = "AStock Analyst"

# --- Trader ----------------------------------------------------------------
TRADER = "Trader"

# --- Risk debate -----------------------------------------------------------
AGGRESSIVE_ANALYST = "Aggressive Analyst"
CONSERVATIVE_ANALYST = "Conservative Analyst"
NEUTRAL_ANALYST = "Neutral Analyst"
PORTFOLIO_MANAGER = "Portfolio Manager"

# All fixed (non per-analyst) nodes, for validation and iteration.
FIXED_NODES = frozenset(
    {
        BULL_RESEARCHER,
        BEAR_RESEARCHER,
        RESEARCH_MANAGER,
        ASTOCK_ANALYST,
        TRADER,
        AGGRESSIVE_ANALYST,
        CONSERVATIVE_ANALYST,
        NEUTRAL_ANALYST,
        PORTFOLIO_MANAGER,
    }
)

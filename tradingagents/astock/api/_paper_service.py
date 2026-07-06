"""Shared service: PaperTrader singleton for API routes.

Routes that need the paper trader instance should import ``get_paper_trader()``
from this module instead of reaching into ``routes_paper``.

This eliminates the circular import pattern::

    routes_dashboard  -->  routes_paper._get_trader()
    routes_portfolio  -->  routes_paper._get_trader()
"""

from __future__ import annotations

from typing import Any

_paper_trader: Any = None


def get_paper_trader() -> Any:
    """Return the shared PaperTrader singleton (lazily initialised)."""
    global _paper_trader
    if _paper_trader is None:
        from tradingagents.astock.execution.paper_trader import PaperTrader
        _paper_trader = PaperTrader()
    return _paper_trader

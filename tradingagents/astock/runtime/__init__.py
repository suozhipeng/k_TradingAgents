"""A-share runtime entry — split into focused submodules.

Public API is identical to the original ``tradingagents.astock.runtime``
module.  All previous import paths continue to work because this package
``__init__`` re-exports every symbol that was previously defined inline.

Split layout
------------
- ``llm_factory`` — ``build_astock_runtime_llms()``, ``BridgeLLM``,
  ``_provider_kwargs_from_config()``
- ``report`` — ``AStockGraphReport`` and all section/result helpers
- ``core`` — ``AStockGraphRuntime``, ``build_astock_research_bridge_state()``,
  ``run_astock_research_bridge()``
- ``runtime`` — (original file, kept as compat shim)
"""

from __future__ import annotations

# LLM factory
from ..runtime_profile import (
    RuntimeProfile,
    profile_metadata,
    require_live_research_clients,
)
from .llm_factory import (
    BridgeLLM,
    build_astock_runtime_llms,
)

# Re-export create_llm_client for test patching (was originally in runtime.py)
from tradingagents.llm_clients import create_llm_client

# Report
from .report import (
    AStockGraphReport,
)

# Core runtime
from .core import (
    AStockGraphRuntime,
    build_astock_research_bridge_state,
    run_astock_research_bridge,
)

# Phase 09 schemas re-exported for backward compat
from ..phase9_schemas import ResearchConclusion

# Utility — lives here for backward compat
from .llm_factory import (
    _provider_kwargs_from_config,
)

# is_astock_symbol: re-export from the original location
import re
from ..data_sources import normalize_astock_symbol

_ASTOCK_EXACT = re.compile(r"^\d{6}$")
_ASTOCK_SUFFIXES = (".SH", ".SZ", ".BJ")


def is_astock_symbol(raw: str) -> bool:
    """Return True when the symbol is a mainland A-share ticker."""
    normalized = normalize_astock_symbol(raw)
    return bool(_ASTOCK_EXACT.fullmatch(normalized) or normalized.endswith(_ASTOCK_SUFFIXES))

__all__ = [
    "AStockGraphReport",
    "AStockGraphRuntime",
    "BridgeLLM",
    "build_astock_research_bridge_state",
    "build_astock_runtime_llms",
    "is_astock_symbol",
    "run_astock_research_bridge",
    "RuntimeProfile",
    "ResearchConclusion",
    "profile_metadata",
    "require_live_research_clients",
]

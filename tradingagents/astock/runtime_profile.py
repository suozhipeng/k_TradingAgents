"""Explicit runtime profile configuration for the A-share research-only chain.

Two profiles are defined:

- ``deterministic_verification`` — Uses BridgeLLM. Allowed only for tests,
  fixtures, and offline demonstrations. Must identify itself in metadata.
- ``live_research`` — Requires explicit injected/configured LLM clients.
  Fails closed when required clients are unavailable. Must not fall back to
  BridgeLLM.

These profiles are deliberately separate from any production-execution profile,
which is not implemented until Phase 11.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional


class RuntimeProfile(str, Enum):
    """Named runtime profiles for the A-share advisory chain.

    Only ``DETERMINISTIC_VERIFICATION`` and ``LIVE_RESEARCH`` are valid for
    Phase 09.  ``PRODUCTION_EXECUTION`` is reserved for Phase 11 and MUST NOT
    be used in Phase 09.
    """

    DETERMINISTIC_VERIFICATION = "deterministic_verification"
    LIVE_RESEARCH = "live_research"
    PRODUCTION_EXECUTION = "production_execution"  # reserved; not used in Phase 09

    @property
    def allows_bridge_llm(self) -> bool:
        """Return True only for the deterministic verification profile."""
        return self == RuntimeProfile.DETERMINISTIC_VERIFICATION

    @property
    def requires_real_llm(self) -> bool:
        """Return True for profiles that require real LLM clients."""
        return self == RuntimeProfile.LIVE_RESEARCH

    @property
    def is_phase09_legal(self) -> bool:
        """Return True when the profile is permitted in Phase 09."""
        return self in (RuntimeProfile.DETERMINISTIC_VERIFICATION, RuntimeProfile.LIVE_RESEARCH)

    @property
    def decision_scope(self) -> str:
        """Return the decision_scope string used in report metadata."""
        if self == RuntimeProfile.DETERMINISTIC_VERIFICATION:
            return "research_only"
        if self == RuntimeProfile.LIVE_RESEARCH:
            return "research_only"
        return "execution"  # Phase 11+

    @property
    def actionable(self) -> bool:
        """Return False for every Phase 09 profile."""
        return False

    @property
    def execution_signal(self) -> Literal["ResearchOnly"]:
        """Return ``ResearchOnly`` for every Phase 09 profile."""
        return "ResearchOnly"


# ---------------------------------------------------------------------------
# Profile metadata helpers
# ---------------------------------------------------------------------------


def profile_metadata(profile: RuntimeProfile) -> Dict[str, Any]:
    """Return a metadata dict identifying the active runtime profile.

    This is attached to ``AStockGraphReport.metadata`` so downstream consumers
    (CLI, UI, tests) can verify the profile.
    """
    return {
        "runtime_profile": profile.value,
        "allows_bridge_llm": profile.allows_bridge_llm,
        "requires_real_llm": profile.requires_real_llm,
        "decision_scope": profile.decision_scope,
        "actionable": profile.actionable,
        "execution_signal": profile.execution_signal,
    }


def resolve_profile(
    profile_override: Optional[RuntimeProfile] = None,
    *,
    has_bridge_llm: bool = False,
    has_real_llm: bool = False,
) -> RuntimeProfile:
    """Resolve the active runtime profile with explicit semantics.

    - If ``profile_override`` is set, it wins (caller explicitly chooses).
    - Otherwise:
        * If ``has_real_llm`` is True → ``LIVE_RESEARCH``
        * If ``has_bridge_llm`` is True → ``DETERMINISTIC_VERIFICATION``
        * Otherwise → ``DETERMINISTIC_VERIFICATION`` (default safe profile)

    This function is deliberately simple and predictable.  Profile selection
    is never implicit during a live_research run.
    """
    if profile_override is not None:
        return profile_override
    if has_real_llm:
        return RuntimeProfile.LIVE_RESEARCH
    return RuntimeProfile.DETERMINISTIC_VERIFICATION


# ---------------------------------------------------------------------------
# live_research guard: fail closed when real LLM clients are missing
# ---------------------------------------------------------------------------


class LiveResearchMisconfiguredError(RuntimeError):
    """Raised when ``live_research`` profile is active but no real LLM clients
    were provided.  Prevents silent fallback to BridgeLLM.
    """

    pass


def require_live_research_clients(*, profile: RuntimeProfile, **clients: Optional[Any]) -> None:
    """Validate that all required LLM clients are present for the given profile.

    For ``DETERMINISTIC_VERIFICATION``, any missing clients are allowed
    (BridgeLLM will be used).  For ``LIVE_RESEARCH``, every client must be
    non-None; otherwise ``LiveResearchMisconfiguredError`` is raised.

    Usage::

        require_live_research_clients(
            profile=my_profile,
            bull_llm=bull_llm,
            bear_llm=bear_llm,
            research_manager_llm=research_manager_llm,
        )
    """
    if profile == RuntimeProfile.LIVE_RESEARCH:
        missing = [name for name, client in clients.items() if client is None]
        if missing:
            raise LiveResearchMisconfiguredError(
                f"live_research profile requires all LLM clients, but the following "
                f"are missing: {', '.join(missing)}. "
                f"BridgeLLM fallback is forbidden in live_research mode."
            )


__all__ = [
    "RuntimeProfile",
    "profile_metadata",
    "resolve_profile",
    "LiveResearchMisconfiguredError",
    "require_live_research_clients",
]

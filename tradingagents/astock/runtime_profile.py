"""Explicit runtime profile configuration for the A-share research-and-execution chain.

Three profiles are defined:

- ``deterministic_verification`` — Uses BridgeLLM. Allowed only for tests,
  fixtures, and offline demonstrations. Must identify itself in metadata.
- ``live_research`` — Requires explicit injected/configured LLM clients.
  Fails closed when required clients are unavailable. Must not fall back to
  BridgeLLM.
- ``production_execution`` — (Phase 11) Live execution mode. Permits
  order placement through the QMT bridge with ATR stop-loss and safety
  mode enforcement.

Profile legality
----------------
- Phase 09 research profiles: ``deterministic_verification``, ``live_research``.
- Phase 10 paper-trading profiles: same as Phase 09 (paper trading is
  still research-only).
- Phase 11 controlled execution: ``production_execution`` is the only
  profile with ``is_phase11_legal == True``.
- Phase 09/10 profiles and Phase 11 profile are **mutually exclusive**:
  a session cannot be simultaneously research-only and execution.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional


class RuntimeProfile(str, Enum):
    """Named runtime profiles for the A-share advisory chain.

    ``DETERMINISTIC_VERIFICATION`` and ``LIVE_RESEARCH`` are valid for
    Phase 09 and Phase 10 (research-only).  ``PRODUCTION_EXECUTION`` is
    valid for Phase 11 (controlled execution) and MUST NOT be used in
    earlier phases.

    Profile legality is **mutually exclusive** across phases.
    """

    DETERMINISTIC_VERIFICATION = "deterministic_verification"
    LIVE_RESEARCH = "live_research"
    PRODUCTION_EXECUTION = "production_execution"  # Phase 11: controlled execution

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
    def is_phase10_legal(self) -> bool:
        """Return True when the profile is permitted in Phase 10 (paper trading).

        Paper trading is still research-only, so the same profiles as
        Phase 09 are legal.
        """
        return self in (RuntimeProfile.DETERMINISTIC_VERIFICATION, RuntimeProfile.LIVE_RESEARCH)

    @property
    def is_phase11_legal(self) -> bool:
        """Return True when the profile is permitted in Phase 11 (controlled execution).

        Only ``PRODUCTION_EXECUTION`` is Phase 11-legal.  This is mutually
        exclusive with Phase 09/10 profiles: a Phase 11 session cannot
        simultaneously be research-only.
        """
        return self == RuntimeProfile.PRODUCTION_EXECUTION

    @property
    def decision_scope(self) -> str:
        """Return the decision_scope string used in report metadata."""
        if self == RuntimeProfile.DETERMINISTIC_VERIFICATION:
            return "research_only"
        if self == RuntimeProfile.LIVE_RESEARCH:
            return "research_only"
        return "execution"  # Phase 11+ (PRODUCTION_EXECUTION)

    @property
    def actionable(self) -> bool:
        """Return True only for execution-capable profiles.

        Phase 09/10 profiles are always non-actionable (research-only).
        Phase 11 ``PRODUCTION_EXECUTION`` is actionable.
        """
        return self == RuntimeProfile.PRODUCTION_EXECUTION

    @property
    def execution_signal(self) -> Literal["ResearchOnly", "Execution"]:
        """Return the execution signal for this profile.

        Phase 09/10 profiles return ``"ResearchOnly"``.
        Phase 11 ``PRODUCTION_EXECUTION`` returns ``"Execution"``.
        """
        if self == RuntimeProfile.PRODUCTION_EXECUTION:
            return "Execution"
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
        "is_phase09_legal": profile.is_phase09_legal,
        "is_phase10_legal": profile.is_phase10_legal,
        "is_phase11_legal": profile.is_phase11_legal,
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

    Note: ``PRODUCTION_EXECUTION`` can only be selected via ``profile_override``.
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

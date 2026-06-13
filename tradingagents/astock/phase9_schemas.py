"""A-share-specific Phase 09 advisory-only contract schemas.

Every contract in this module enforces ``actionable=false`` and is scoped to a
research-only / advisory-only decision plane.  These schemas are deliberately
A-share-specific and MUST NOT be reused for generic stock or crypto paths.

Hard constraints
----------------
- ``actionable`` is fixed to ``false`` in every model via ``Literal``.
- ``execution_signal`` is always ``"ResearchOnly"``.
- ``ResearchConclusion``, ``TraderProposal``, ``RiskDecision``, and
  ``PortfolioDecision`` each carry different ``decision_scope`` literals.
- No field here may be interpreted as an order or execution instruction.
- Missing or degraded provider data must reduce confidence or reject the
  proposal; it must never be interpreted as permission to proceed.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Reusable constants
# ---------------------------------------------------------------------------

EXECUTION_SIGNAL: Literal["ResearchOnly"] = "ResearchOnly"

ACTIONABLE_FALSE: Literal[False] = False


# ---------------------------------------------------------------------------
# Recommendation enum (not the generic PortfolioRating)
# ---------------------------------------------------------------------------


class ResearchRecommendation(str, Enum):
    """A-share advisory recommendation from the Research Manager."""

    BUY_BIAS = "buy_bias"
    HOLD_BIAS = "hold_bias"
    SELL_BIAS = "sell_bias"
    INSUFFICIENT_DATA = "insufficient_data"


class TraderCandidateAction(str, Enum):
    """Non-executable action proposals by the A-share Trader adapter."""

    OBSERVE = "observe"
    CONSIDER_BUY = "consider_buy"
    HOLD = "hold"
    CONSIDER_REDUCE = "consider_reduce"
    AVOID = "avoid"


class RiskVerdict(str, Enum):
    """Structured risk verdict after three-viewpoint synthesis."""

    ALLOW_ADVISORY = "allow_advisory"
    NEEDS_MORE_DATA = "needs_more_data"
    REJECT_PROPOSAL = "reject_proposal"


class RiskLevel(str, Enum):
    """Aggregated risk level from the three-viewpoint debate."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class PortfolioDisposition(str, Enum):
    """Portfolio-level advisory disposition."""

    WATCHLIST = "watchlist"
    CONTINUE_RESEARCH = "continue_research"
    ADVISORY_REJECTED = "advisory_rejected"


# ---------------------------------------------------------------------------
# ResearchConclusion
# ---------------------------------------------------------------------------


class ResearchConclusion(BaseModel):
    """A-share research conclusion produced by adapting the Research Manager
    output.  Non-actionable; represents the end of the research phase.

    This is the **only** Phase 09 contract produced directly from research
    results.  Downstream contracts reference its identity via
    ``*_conclusion_id`` fields.
    """

    schema_version: str = Field(
        default="phase09.v1",
        description="Versioned contract identifier",
    )
    symbol: str = Field(
        description="Normalized A-share symbol (e.g. '600519.SH')",
    )
    trade_date: str = Field(
        description="Analysis date in YYYY-MM-DD format",
    )
    summary: str = Field(
        description="Research Manager conclusion summary",
    )
    recommendation: ResearchRecommendation = Field(
        description="Advisory research recommendation direction",
    )
    bull_case: str = Field(
        default="",
        description="Strongest positive evidence from the bull researcher",
    )
    bear_case: str = Field(
        default="",
        description="Strongest negative evidence from the bear researcher",
    )
    uncertainties: List[str] = Field(
        default_factory=list,
        description="Material unknowns and missing evidence",
    )
    provider_coverage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Five-layer source coverage map",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the conclusion (0.0 .. 1.0)",
    )
    decision_scope: Literal["research_only"] = Field(
        default="research_only",
        description="Fixed to research_only for Phase 09",
    )
    actionable: Literal[False] = Field(
        default=False,
        description="Always false for Phase 09 advisory contracts",
    )

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------

    @field_validator("actionable", mode="before")
    @classmethod
    def _reject_actionable_true(cls, v: Any) -> Literal[False]:
        if v is True or str(v).lower() in ("true", "1", "yes"):
            raise ValueError(
                "ResearchConclusion.actionable MUST be False. "
                "Phase 09 contracts are advisory-only."
            )
        return False

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# ---------------------------------------------------------------------------
# TraderProposal
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """A-share non-actionable trade proposal produced from the Trader
    adaptation layer.

    ``entry_zone`` is advisory and MUST NOT be interpreted as a limit order.
    ``position_cap_pct`` is an advisory maximum exposure, not an allocation.
    """

    schema_version: str = Field(
        default="phase09.v1",
        description="Versioned contract identifier",
    )
    proposal_id: str = Field(
        default="",
        description="Stable audit identifier for this proposal",
    )
    research_conclusion_id: str = Field(
        default="",
        description="Reference to the source ResearchConclusion",
    )
    candidate_action: TraderCandidateAction = Field(
        description="Advisory candidate action (non-executable)",
    )
    rationale: str = Field(
        description="Evidence-based explanation for the proposal",
    )
    entry_zone: Optional[str] = Field(
        default=None,
        description="Advisory price observation zone, never an order",
    )
    invalidation_conditions: List[str] = Field(
        default_factory=list,
        description="Conditions that would invalidate this advisory proposal",
    )
    position_cap_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Advisory maximum exposure percentage",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this proposal (0.0 .. 1.0)",
    )
    decision_scope: Literal["advisory_only"] = Field(
        default="advisory_only",
        description="Fixed to advisory_only for Phase 09",
    )
    actionable: Literal[False] = Field(
        default=False,
        description="Always false for Phase 09 advisory contracts",
    )

    @field_validator("actionable", mode="before")
    @classmethod
    def _reject_actionable_true(cls, v: Any) -> Literal[False]:
        if v is True or str(v).lower() in ("true", "1", "yes"):
            raise ValueError(
                "TraderProposal.actionable MUST be False. "
                "Phase 09 contracts are advisory-only."
            )
        return False

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("position_cap_pct")
    @classmethod
    def _clamp_position_cap(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return max(0.0, min(100.0, v))
        return v


# ---------------------------------------------------------------------------
# RiskDecision
# ---------------------------------------------------------------------------


class RiskDecision(BaseModel):
    """Structured risk decision synthesising the aggressive, conservative,
    and neutral risk viewpoints into a single advisory verdict.

    ``risk_factors``, ``constraints``, and ``missing_evidence`` together
    form the complete risk picture.  A rejected proposal
    (``verdict = reject_proposal``) stops the Phase 09 chain; it MUST NOT be
    forwarded to PortfolioDecision.
    """

    schema_version: str = Field(
        default="phase09.v1",
        description="Versioned contract identifier",
    )
    proposal_id: str = Field(
        default="",
        description="Reference to the TraderProposal being reviewed",
    )
    verdict: RiskVerdict = Field(
        description="Advisory risk verdict for the trader proposal",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.UNKNOWN,
        description="Aggregated risk level from the three-viewpoint debate",
    )
    risk_factors: List[str] = Field(
        default_factory=list,
        description="Identified market, liquidity, policy, and data risks",
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Advisory limits required before later stages",
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence needed to reconsider the verdict",
    )
    decision_scope: Literal["risk_review_only"] = Field(
        default="risk_review_only",
        description="Fixed to risk_review_only for Phase 09",
    )
    actionable: Literal[False] = Field(
        default=False,
        description="Always false for Phase 09 advisory contracts",
    )

    @field_validator("actionable", mode="before")
    @classmethod
    def _reject_actionable_true(cls, v: Any) -> Literal[False]:
        if v is True or str(v).lower() in ("true", "1", "yes"):
            raise ValueError(
                "RiskDecision.actionable MUST be False. "
                "Phase 09 contracts are advisory-only."
            )
        return False


# ---------------------------------------------------------------------------
# PortfolioDecision
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Portfolio-level advisory decision after TraderProposal and RiskDecision
    have been evaluated.

    This is the **last** Phase 09 contract.  The chain stops here:
    no signal processing, no trade-decision memory, no QMT.

    ``disposition`` determines whether the advisory result enters a watchlist,
    continues research, or is rejected entirely.  ``execution_signal`` is
    always ``"ResearchOnly"``.
    """

    schema_version: str = Field(
        default="phase09.v1",
        description="Versioned contract identifier",
    )
    proposal_id: str = Field(
        default="",
        description="Reference to the TraderProposal",
    )
    risk_decision_id: str = Field(
        default="",
        description="Reference to the RiskDecision",
    )
    disposition: PortfolioDisposition = Field(
        description="Portfolio-level advisory disposition",
    )
    portfolio_notes: str = Field(
        default="",
        description="Portfolio-level rationale and notes",
    )
    exposure_cap_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Advisory cap for later simulation work",
    )
    review_triggers: List[str] = Field(
        default_factory=list,
        description="Conditions that warrant a new research run",
    )
    decision_scope: Literal["portfolio_advisory"] = Field(
        default="portfolio_advisory",
        description="Fixed to portfolio_advisory for Phase 09",
    )
    actionable: Literal[False] = Field(
        default=False,
        description="Always false for Phase 09 advisory contracts",
    )
    execution_signal: Literal["ResearchOnly"] = Field(
        default="ResearchOnly",
        description="Always ResearchOnly for Phase 09",
    )

    @field_validator("actionable", mode="before")
    @classmethod
    def _reject_actionable_true(cls, v: Any) -> Literal[False]:
        if v is True or str(v).lower() in ("true", "1", "yes"):
            raise ValueError(
                "PortfolioDecision.actionable MUST be False. "
                "Phase 09 contracts are advisory-only."
            )
        return False

    @field_validator("exposure_cap_pct")
    @classmethod
    def _clamp_exposure_cap(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            return max(0.0, min(100.0, v))
        return v


# ---------------------------------------------------------------------------
# Degraded result helpers
# ---------------------------------------------------------------------------


def degraded_research_conclusion(symbol: str, trade_date: str, reason: str) -> ResearchConclusion:
    """Build a typed ResearchConclusion with ``insufficient_data`` when
    provider data is missing or degraded."""
    return ResearchConclusion(
        symbol=symbol,
        trade_date=trade_date,
        summary=f"Degraded: {reason}",
        recommendation=ResearchRecommendation.INSUFFICIENT_DATA,
        uncertainties=[reason],
        confidence=0.0,
    )


def degraded_trader_proposal(conclusion_id: str, reason: str) -> TraderProposal:
    """Build a typed TraderProposal with ``avoid`` when source data is
    insufficient."""
    return TraderProposal(
        proposal_id=f"degraded-{conclusion_id}",
        research_conclusion_id=conclusion_id,
        candidate_action=TraderCandidateAction.AVOID,
        rationale=f"Proposal degraded due to insufficient data: {reason}",
        invalidation_conditions=[reason],
        confidence=0.0,
    )


__all__ = [
    "EXECUTION_SIGNAL",
    "ACTIONABLE_FALSE",
    "ResearchRecommendation",
    "ResearchConclusion",
    "TraderCandidateAction",
    "TraderProposal",
    "RiskVerdict",
    "RiskLevel",
    "RiskDecision",
    "PortfolioDisposition",
    "PortfolioDecision",
    "degraded_research_conclusion",
    "degraded_trader_proposal",
]

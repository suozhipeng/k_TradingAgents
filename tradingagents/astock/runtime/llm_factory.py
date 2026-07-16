"""LLM client factory for the A-share runtime.

Provides ``build_astock_runtime_llms()`` which creates real LLM clients
for the live_research path, and ``BridgeLLM``, a deterministic stub used
when no real LLM is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Optional, Sequence

# Import create_llm_client lazily to avoid circular import with runtime/__init__.py.
# We import from the parent package at call time so that test patches on
# tradingagents.astock.runtime.create_llm_client take effect.
def _get_create_llm_client():
    """Return create_llm_client, reading from parent package at call time."""
    # Import the parent package (which re-exports create_llm_client)
    # This avoids circular import because we don't import the parent at module level
    import sys
    parent = sys.modules[__name__.rsplit(".", 1)[0]]
    return parent.create_llm_client

from ..runtime_profile import RuntimeProfile


# ---------------------------------------------------------------------------
# Provider-specific kwarg helpers
# ---------------------------------------------------------------------------

def _provider_kwargs_from_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract provider-specific LLM kwargs from the runtime config."""

    kwargs: Dict[str, Any] = {}
    provider = str(config.get("llm_provider", "")).lower()
    if provider == "openai" and config.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    elif provider == "anthropic" and config.get("anthropic_effort"):
        kwargs["effort"] = config["anthropic_effort"]

    temperature = config.get("temperature")
    if temperature is not None and temperature != "":
        kwargs["temperature"] = float(temperature)
    return kwargs


# ---------------------------------------------------------------------------
# Real LLM factory
# ---------------------------------------------------------------------------

def build_astock_runtime_llms(
    config: Mapping[str, Any],
    callbacks: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Build real LLM clients for the A-share live_research runtime.

    Returns a dict keyed by role (bull_llm, bear_llm, research_manager_llm)
    plus the resolved runtime_profile.
    """

    llm_kwargs = _provider_kwargs_from_config(config)
    if callbacks:
        llm_kwargs["callbacks"] = list(callbacks)

    provider = str(config["llm_provider"]).lower()
    base_url = config.get("backend_url")
    quick_client = _get_create_llm_client()(
        provider=provider,
        model=str(config["quick_think_llm"]),
        base_url=base_url,
        **llm_kwargs,
    )
    deep_client = _get_create_llm_client()(
        provider=provider,
        model=str(config["deep_think_llm"]),
        base_url=base_url,
        **llm_kwargs,
    )
    quick_llm = quick_client.get_llm()
    deep_llm = deep_client.get_llm()
    return {
        "runtime_profile": RuntimeProfile.LIVE_RESEARCH.value,
        "bull_llm": quick_llm,
        "bear_llm": quick_llm,
        "research_manager_llm": deep_llm,
    }


# ---------------------------------------------------------------------------
# Deterministic stub for bridge verification
# ---------------------------------------------------------------------------

@dataclass
class BridgeLLM:
    """Tiny deterministic LLM stub used by the runtime bridge verification path."""

    label: str
    response_content: str = ""
    rationale: str = ""
    strategic_actions: str = ""
    prompts: list[str] = field(default_factory=list)
    _structured_schema: Any = field(default=None, init=False)

    def with_structured_output(self, schema):
        self._structured_schema = schema
        return self

    def invoke(self, prompt: Any):
        self.prompts.append(str(prompt))
        if self._structured_schema is not None:
            return self._structured_schema(
                recommendation="Hold",
                rationale=self.rationale
                or f"{self.label} completed the A-share bridge with the structured analysis handoff.",
                strategic_actions=self.strategic_actions
                or "Keep monitoring the bridged A-share sections and revisit the debate on the next run.",
            )
        return SimpleNamespace(
            content=self.response_content
            or f"{self.label}: processed the bridged A-share context successfully.",
        )

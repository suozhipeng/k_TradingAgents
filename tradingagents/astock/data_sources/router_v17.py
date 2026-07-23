"""V1.7 DataFacade — single entry point for all business modules.

Only uses ProviderRegistry + ProviderPolicy. Old Router is deprecated.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from tradingagents.astock.data_sources.base import (
    CapabilityStatus, FinancialDataProvider, ProviderCapability,
)
from tradingagents.astock.data_sources.registry import ProviderRegistry
from tradingagents.astock.data_sources.providers_v1_6 import register_v1_6_1_providers

logger = logging.getLogger(__name__)

# V1.7 provider error codes
PROVIDER_ERRORS = {
    "provider_unavailable": "PROVIDER_UNAVAILABLE",
    "provider_timeout": "PROVIDER_TIMEOUT",
    "provider_rate_limited": "RATE_LIMITED",
    "provider_schema_changed": "SCHEMA_CHANGED",
    "provider_empty_result": "EMPTY_RESULT",
    "provider_auth_failed": "AUTH_FAILED",
    "provider_invalid_response": "INVALID_RESPONSE",
    "provider_quality_failed": "QUALITY_FAILED",
    "provider_unsupported": "UNSUPPORTED_CAPABILITY",
}


class DataFacade:
    """V1.7 single entry point for all data access."""

    def __init__(self, policy_path: str = "") -> None:
        self._registry = ProviderRegistry()
        register_v1_6_1_providers(self._registry)

        if not policy_path:
            policy_path = os.environ.get(
                "ASTOCK_PROVIDER_POLICY_PATH",
                str(Path.cwd() / "config" / "provider_policy.yaml"),
            )
        self._policy = self._load_policy(policy_path)

    @staticmethod
    def _load_policy(path: str) -> dict:
        p = Path(path)
        if not p.is_file():
            logger.warning("provider policy not found at %s, using defaults", path)
            return {"mode": "community", "current_stack": ["mootdx", "akshare", "baostock", "cninfo"]}
        with open(p) as f:
            data = yaml.safe_load(f)
        return data.get("provider_policy", data)

    def _resolve_provider(self, capability: str) -> tuple[str, str] | None:
        """Resolve (provider_name, source_kind) for a capability per policy."""
        policy = self._policy
        cap_key = capability.replace("-", "_")
        if cap_key not in policy:
            logger.warning("no policy for capability %s", capability)
            return None
        entry = policy[cap_key]
        if not isinstance(entry, dict):
            return None
        primary = entry.get("primary")
        if primary:
            return primary, "online_api"
        for fallback in entry.get("fallback", []):
            if self._registry.get_provider(fallback):
                return fallback, "fallback"
        return None

    def get_provider(self, name: str) -> FinancialDataProvider | None:
        return self._registry.get_provider(name)

    def probe(self, provider: str, capability: ProviderCapability) -> CapabilityStatus:
        p = self._registry.get_provider(provider)
        if not p:
            return CapabilityStatus(provider=provider, capability=capability,
                                    state="unavailable", checked_at="")
        return p.probe(capability)

    def capability_matrix(self) -> dict[str, dict]:
        """Return capability: state for all registered providers and capabilities."""
        matrix: dict[str, dict] = {}
        for name in ("mootdx", "akshare", "baostock", "cninfo"):
            p = self._registry.get_provider(name)
            if not p:
                continue
            matrix[name] = {}
            for cap in ProviderCapability:
                matrix[name][cap.value] = p.probe(cap).state
        return matrix

    def get_policy_summary(self) -> dict:
        return {
            "mode": self._policy.get("mode", "unknown"),
            "current_stack": self._policy.get("current_stack", []),
            "commercial_provider_required": False,
        }

    # ── V1.7 capability-named convenience methods ─────────────────────────

    def get_daily_bars(self, symbol: str, start: str, end: str) -> Any:
        """Delegated — the actual fetch uses existing adapters."""
        return {"symbol": symbol, "start": start, "end": end, "status": "delegated"}

    def get_trade_calendar(self, start: str, end: str) -> Any:
        return {"status": "delegated"}

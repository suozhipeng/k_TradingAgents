"""Provider Capability Registry — discover, probe, and route by capability."""

from __future__ import annotations

import logging
import time
from typing import Any

from .base import CapabilityStatus, FinancialDataProvider, ProviderCapability, PROVIDER_STATES

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Holds all registered providers and exposes capability-based routing."""

    def __init__(self) -> None:
        self._providers: dict[str, FinancialDataProvider] = {}
        self._capability_cache: dict[str, dict[str, CapabilityStatus]] = {}  # provider -> {capability: status}
        self._cache_ttl: float = 60.0
        self._last_probe: float = 0.0

    def register(self, name: str, provider: FinancialDataProvider) -> None:
        self._providers[name] = provider
        logger.info("registered provider %s with capabilities %s", name, provider.capabilities())

    def get_provider(self, name: str) -> FinancialDataProvider | None:
        return self._providers.get(name)

    def all_providers(self) -> dict[str, FinancialDataProvider]:
        return dict(self._providers)

    def known_capabilities(self) -> set[ProviderCapability]:
        caps: set[ProviderCapability] = set()
        for p in self._providers.values():
            caps |= p.capabilities()
        return caps

    def probe_all(self, force: bool = False) -> dict[str, dict[str, CapabilityStatus]]:
        """Lightweight probe of all capabilities across all providers.  Results cached."""
        now = time.time()
        if not force and (now - self._last_probe) < self._cache_ttl:
            return dict(self._capability_cache)
        result: dict[str, dict[str, CapabilityStatus]] = {}
        for name, provider in self._providers.items():
            caps: dict[str, CapabilityStatus] = result.setdefault(name, {})
            for cap in provider.capabilities():
                try:
                    status = provider.probe(cap)
                except Exception as exc:
                    status = CapabilityStatus(
                        provider=name, capability=cap, state="unavailable",
                        checked_at=_now_iso(), error_code=str(exc)[:80],
                    )
                caps[cap.value] = status
        self._capability_cache = result
        self._last_probe = now
        return result

    def best_available(self, capability: ProviderCapability,
                       policy: dict[str, Any] | None = None) -> tuple[str | None, CapabilityStatus | None]:
        """Find the best provider for a capability using the routing policy."""
        if policy is None:
            policy = {}
        preferred = policy.get(capability.value, {})
        primary = preferred.get("primary")
        fallbacks: list[str] = preferred.get("fallback", [])

        cache = self.probe_all()
        order = [primary] + fallbacks if primary else fallbacks
        for name in order:
            if name and name in cache:
                for cap_key, status in cache[name].items():
                    if cap_key == capability.value and status.state in ("available", "degraded", "stale"):
                        return name, status
        return None, None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

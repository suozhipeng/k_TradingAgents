"""Cninfo (巨潮资讯) provider — official announcements and corporate events.

Supports public_query and local_import modes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from .base import CapabilityStatus, FinancialDataProvider, ProviderCapability

logger = logging.getLogger(__name__)

CNINFO_LOCAL_DIR = os.environ.get("ASTOCK_CNINFO_LOCAL_DIR",
                                  str(Path.home() / ".tradingagents" / "cninfo"))


class CninfoProvider(FinancialDataProvider):
    """巨潮资讯 — official listed company disclosures.

    Two modes:
      public_query — lightweight online query of public announcements.
      local_import  — process pre-downloaded official files from local directory.
    """

    name = "cninfo"

    def __init__(self, local_dir: str = "", mode: str = "") -> None:
        self._local_dir = local_dir or CNINFO_LOCAL_DIR
        self._mode = mode or os.environ.get("ASTOCK_CNINFO_MODE", "public_or_local_import")

    def capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.ANNOUNCEMENTS, ProviderCapability.CORPORATE_EVENTS}

    def _probe_public(self) -> CapabilityStatus:
        """Lightweight public query probe — does not download full lists."""
        try:
            import httpx
        except ImportError:
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                state="missing_dependency", checked_at=_now(),
                source_kind="online_api",
                degradation_reason="httpx not installed",
            )
        start = time.monotonic()
        try:
            # Minimal public query — just test connectivity
            resp = httpx.get(
                "https://www.cninfo.com.cn/new/disclosure",
                params={"stockCode": "600519", "pageSize": 1},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10.0,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            if resp.status_code == 200:
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                    state="available", checked_at=_now(), latency_ms=elapsed,
                    source_kind="online_api", rows=1,
                )
            if resp.status_code in (403, 429):
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                    state="access_restricted", checked_at=_now(), latency_ms=elapsed,
                    source_kind="online_api", error_code=f"http_{resp.status_code}",
                )
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                state="unavailable", checked_at=_now(), latency_ms=elapsed,
                source_kind="online_api", error_code=f"http_{resp.status_code}",
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                state="unavailable", checked_at=_now(), latency_ms=elapsed,
                source_kind="online_api", error_code=str(exc)[:80],
            )

    def _probe_local_import(self) -> CapabilityStatus:
        """Check local manifest directory for imported official documents."""
        manifests = Path(self._local_dir) / "manifests"
        if manifests.is_dir():
            manifests_count = len(list(manifests.glob("*.json")))
            if manifests_count > 0:
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                    state="available", checked_at=_now(),
                    source_kind="local_import", rows=manifests_count,
                )
        if Path(self._local_dir).is_dir():
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
                state="manual_import_required", checked_at=_now(),
                source_kind="local_import",
                degradation_reason=f"place official documents in {self._local_dir}",
            )
        return CapabilityStatus(
            provider=self.name, capability=ProviderCapability.ANNOUNCEMENTS,
            state="unconfigured", checked_at=_now(),
            source_kind="local_import",
            degradation_reason=f"directory {self._local_dir} does not exist",
        )

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        if capability not in self.capabilities():
            return CapabilityStatus(
                provider=self.name, capability=capability, state="unavailable",
                checked_at=_now(), source_kind="unknown",
            )
        # Try public query first
        public = self._probe_public()
        if public.state == "available":
            return public
        # Fall back to local import
        if public.state in ("access_restricted", "unavailable", "timeout"):
            local = self._probe_local_import()
            if local.state == "available":
                return local
            if local.state == "manual_import_required":
                return local
        return public

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use specific CninfoAdapter methods for data fetch")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

"""V1.6.1 provider wrappers — Mootdx, AKShare, BaoStock, Cninfo community stack."""

from __future__ import annotations

import logging
import time
from typing import Any

from tradingagents.astock.data_sources.base import (
    CapabilityStatus, FinancialDataProvider, ProviderCapability,
)

logger = logging.getLogger(__name__)


class AkshareCapabilityProvider(FinancialDataProvider):
    """Wraps AKShare with V1.6.1 capability-based probe and upstream_changed detection."""

    name = "akshare"

    def capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.MARKET_KLINE, ProviderCapability.INDEX_KLINE,
            ProviderCapability.REALTIME_QUOTE, ProviderCapability.SECURITY_MASTER,
            ProviderCapability.FINANCIAL_INDICATORS, ProviderCapability.VALUATION_DAILY,
            ProviderCapability.CAPITAL_FLOW_STOCK, ProviderCapability.CAPITAL_FLOW_SECTOR,
            ProviderCapability.INDUSTRY_MEMBERSHIP, ProviderCapability.CONCEPT_MEMBERSHIP,
            ProviderCapability.NEWS, ProviderCapability.ANNOUNCEMENTS,
            ProviderCapability.LIMIT_UP_DOWN,
        }

    def _probe_adapter(self, capability: ProviderCapability) -> CapabilityStatus:
        try:
            import akshare as ak
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now(),
                                    source_kind="online_api")
        start = time.monotonic()
        try:
            if capability == ProviderCapability.TRADE_CALENDAR:
                df = ak.trade_calendar()
            elif capability == ProviderCapability.SECURITY_MASTER:
                df = ak.stock_info_a_code_name()
            else:
                df = ak.stock_zh_a_hist(symbol="600519", period="daily",
                                         start_date="20260701", end_date="20260723", adjust="")
            elapsed = int((time.monotonic() - start) * 1000)
            if df is not None and len(df) > 0:
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="available", checked_at=_now(),
                                        latency_ms=elapsed, rows=len(df), source_kind="public_web")
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="upstream_changed", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="public_web",
                                    error_code="empty_response")
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            msg = str(exc).lower()
            if any(kw in msg for kw in ("not found", "keyerror", "no attribute", "cannot find")):
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="upstream_changed", checked_at=_now(),
                                        latency_ms=elapsed, source_kind="public_web",
                                        error_code=msg[:80])
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="public_web",
                                    error_code=msg[:80])

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        return self._probe_adapter(capability)

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use existing AkshareAdapter for data fetch")


class MootdxCapabilityProvider(FinancialDataProvider):
    name = "mootdx"
    def capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.MARKET_KLINE, ProviderCapability.INDEX_KLINE}
    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        try:
            from mootdx.quotes import Quotes
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now(),
                                    source_kind="online_api")
        start = time.monotonic()
        try:
            client = Quotes.factory(market="std")
            bars = client.bars(symbol="600519", frequency=9, offset=0, start=0, count=5)
            elapsed = int((time.monotonic() - start) * 1000)
            if bars is not None and len(bars) > 0:
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="available", checked_at=_now(),
                                        latency_ms=elapsed, rows=len(bars), source_kind="online_api")
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="empty_response", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="online_api")
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="online_api",
                                    error_code=str(exc)[:80])
    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use existing MootdxAdapter for data fetch")


class BaoStockCapabilityProvider(FinancialDataProvider):
    name = "baostock"
    def capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.MARKET_KLINE, ProviderCapability.INDEX_KLINE,
                ProviderCapability.TRADE_CALENDAR, ProviderCapability.SECURITY_MASTER,
                ProviderCapability.ADJUSTMENT_FACTOR}
    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        try:
            import baostock as bs
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now(),
                                    source_kind="online_api")
        start = time.monotonic()
        try:
            lg = bs.login()
            elapsed = int((time.monotonic() - start) * 1000)
            if lg.error_code == "0":
                bs.logout()
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="available", checked_at=_now(),
                                        latency_ms=elapsed, source_kind="online_api")
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="online_api",
                                    error_code=lg.error_msg[:80])
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, source_kind="online_api",
                                    error_code=str(exc)[:80])
    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use existing BaoStockAdapter for data fetch")


def register_v1_6_1_providers(registry: Any) -> None:
    """Register all V1.6.1 community stack providers."""
    from tradingagents.astock.data_sources.cninfo_provider import CninfoProvider
    registry.register("akshare", AkshareCapabilityProvider())
    registry.register("mootdx", MootdxCapabilityProvider())
    registry.register("baostock", BaoStockCapabilityProvider())
    registry.register("cninfo", CninfoProvider())


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

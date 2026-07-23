"""Provider wrappers — adapt existing adapters to V1.6 FinancialDataProvider interface."""

from __future__ import annotations

import logging
import time
from typing import Any

from tradingagents.astock.data_sources.base import (
    CapabilityStatus, FinancialDataProvider, ProviderCapability,
)

logger = logging.getLogger(__name__)


class AkshareCapabilityProvider(FinancialDataProvider):
    """Wraps AkshareAdapter with V1.6 capability-based probe and fetch.

    Adds ``upstream_changed`` detection: when an API returns an empty DataFrame
    or raises an unexpected parse error, the wrapper returns ``upstream_changed``
    instead of ``unavailable`` so Operators can investigate the upstream website.
    """

    name = "akshare"

    def __init__(self, adapter: Any | None = None) -> None:
        self._adapter = adapter

    def capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.MARKET_KLINE,
            ProviderCapability.INDEX_KLINE,
            ProviderCapability.REALTIME_QUOTE,
            ProviderCapability.SECURITY_MASTER,
            ProviderCapability.FINANCIAL_INDICATORS,
            ProviderCapability.VALUATION_DAILY,
            ProviderCapability.CAPITAL_FLOW_STOCK,
            ProviderCapability.CAPITAL_FLOW_SECTOR,
            ProviderCapability.INDUSTRY_MEMBERSHIP,
            ProviderCapability.CONCEPT_MEMBERSHIP,
            ProviderCapability.NEWS,
            ProviderCapability.ANNOUNCEMENTS,
            ProviderCapability.LIMIT_UP_DOWN,
        }

    def _probe_adapter(self, capability: ProviderCapability) -> CapabilityStatus:
        """Lightweight probe — attempts a minimal API call through the adapter."""
        try:
            import akshare as ak
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now())

        start = time.monotonic()
        try:
            # Probe with a minimal call appropriate to the capability
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
                                        latency_ms=elapsed, detail_rows=len(df))
            # Empty response from a normally-working API → upstream likely changed
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="upstream_changed", checked_at=_now(),
                                    latency_ms=elapsed, error_code="empty_response")
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            msg = str(exc).lower()
            # Common upstream-change indicators
            if any(kw in msg for kw in ("not found", "keyerror", "no attribute",
                                         "cannot find", "字段", "列")):
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="upstream_changed", checked_at=_now(),
                                        latency_ms=elapsed, error_code=msg[:80],
                                        permission_hint="upstream website structure may have changed")
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, error_code=msg[:80])

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        return self._probe_adapter(capability)

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use the existing AkshareAdapter for data fetch")


class MootdxCapabilityProvider(FinancialDataProvider):
    """Wraps MootdxAdapter with V1.6 capability-based probe."""

    name = "mootdx"

    def capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.MARKET_KLINE,
            ProviderCapability.INDEX_KLINE,
        }

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        try:
            from mootdx.quotes import Quotes
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now())
        start = time.monotonic()
        try:
            client = Quotes.factory(market="std")
            # Lightweight: just check connection with a small request
            bars = client.bars(symbol="600519", frequency=9, offset=0, start=0, count=5)
            elapsed = int((time.monotonic() - start) * 1000)
            if bars is not None and len(bars) > 0:
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="available", checked_at=_now(),
                                        latency_ms=elapsed, detail_rows=len(bars))
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="empty_response", checked_at=_now(),
                                    latency_ms=elapsed)
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(),
                                    latency_ms=elapsed, error_code=str(exc)[:80])

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use the existing MootdxAdapter for data fetch")


class BaoStockCapabilityProvider(FinancialDataProvider):
    """Wraps BaoStockAdapter with V1.6 capability-based probe."""

    name = "baostock"

    def capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.MARKET_KLINE,
            ProviderCapability.INDEX_KLINE,
            ProviderCapability.TRADE_CALENDAR,
            ProviderCapability.SECURITY_MASTER,
        }

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        try:
            import baostock as bs
        except ImportError:
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="missing_dependency", checked_at=_now())
        start = time.monotonic()
        try:
            lg = bs.login()
            elapsed = int((time.monotonic() - start) * 1000)
            if lg.error_code == "0":
                bs.logout()
                return CapabilityStatus(provider=self.name, capability=capability,
                                        state="available", checked_at=_now(), latency_ms=elapsed)
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(), latency_ms=elapsed,
                                    error_code=lg.error_msg[:80])
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return CapabilityStatus(provider=self.name, capability=capability,
                                    state="unavailable", checked_at=_now(), latency_ms=elapsed,
                                    error_code=str(exc)[:80])

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("Use the existing BaoStockAdapter for data fetch")


def register_v1_6_providers(registry: Any) -> None:
    """Register all V1.6 capability providers into a ProviderRegistry."""
    from tradingagents.astock.data_sources.tushare_provider import TushareProvider
    registry.register("tushare", TushareProvider())
    registry.register("akshare", AkshareCapabilityProvider())
    registry.register("mootdx", MootdxCapabilityProvider())
    registry.register("baostock", BaoStockCapabilityProvider())


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

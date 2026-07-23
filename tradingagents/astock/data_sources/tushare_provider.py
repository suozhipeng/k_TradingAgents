"""Tushare Pro provider — structured research data (financials, valuation, capital flow, sectors, news)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .base import CapabilityStatus, FinancialDataProvider, ProviderCapability

logger = logging.getLogger(__name__)

# Tushare API → Capability mapping
_API_CAPABILITIES: dict[str, ProviderCapability] = {
    "daily_basic": ProviderCapability.VALUATION_DAILY,
    "fina_indicator": ProviderCapability.FINANCIAL_INDICATORS,
    "moneyflow": ProviderCapability.CAPITAL_FLOW_STOCK,
    "index_member_all": ProviderCapability.INDUSTRY_MEMBERSHIP,
    "trade_cal": ProviderCapability.TRADE_CALENDAR,
    "stock_basic": ProviderCapability.SECURITY_MASTER,
    "income": ProviderCapability.FINANCIAL_STATEMENTS,
    "balancesheet": ProviderCapability.FINANCIAL_STATEMENTS,
    "cashflow": ProviderCapability.FINANCIAL_STATEMENTS,
    "stk_limit": ProviderCapability.LIMIT_UP_DOWN,
    "news": ProviderCapability.NEWS,
    "major_news": ProviderCapability.NEWS,
    "dc_concept_cons": ProviderCapability.CONCEPT_MEMBERSHIP,
    "moneyflow_ind_dc": ProviderCapability.CAPITAL_FLOW_SECTOR,
    "moneyflow_ind_ths": ProviderCapability.CAPITAL_FLOW_SECTOR,
    "index_daily": ProviderCapability.INDEX_KLINE,
    "daily": ProviderCapability.MARKET_KLINE,
    "pro_bar": ProviderCapability.MARKET_KLINE,
}


class TushareProvider(FinancialDataProvider):
    name = "tushare"

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.environ.get("TUSHARE_TOKEN", "")
        self._ts = None  # lazy import

    def _import(self):
        if self._ts is None:
            import tushare as ts
            ts.set_token(self._token)
            self._ts = ts
        return self._ts

    def capabilities(self) -> set[ProviderCapability]:
        return set(_API_CAPABILITIES.values())

    def probe(self, capability: ProviderCapability) -> CapabilityStatus:
        if not self._token:
            return CapabilityStatus(
                provider=self.name, capability=capability, state="missing_token",
                checked_at=_now(), permission_hint="TUSHARE_TOKEN not configured",
            )
        # Check SDK is actually importable
        try:
            import tushare as ts  # noqa: F811
        except ImportError:
            return CapabilityStatus(
                provider=self.name, capability=capability, state="missing_dependency",
                checked_at=_now(), permission_hint="tushare SDK not installed",
            )
        if capability == ProviderCapability.TRADE_CALENDAR:
            return self._probe_trade_cal()
        if capability in (ProviderCapability.VALUATION_DAILY, ProviderCapability.FINANCIAL_INDICATORS):
            return self._probe_research(capability)
        return CapabilityStatus(
            provider=self.name, capability=capability, state="available",
            checked_at=_now(), detail_rows=1,
        )

    def _probe_trade_cal(self) -> CapabilityStatus:
        try:
            api = self._import()
            start = time.monotonic()
            df = api.trade_cal(start_date="20260701", end_date="20260723")
            elapsed = int((time.monotonic() - start) * 1000)
            rows = len(df) if df is not None else 0
            if df is not None and rows > 0:
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                    state="available", checked_at=_now(), latency_ms=elapsed, detail_rows=rows)
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                state="empty_response", checked_at=_now(), latency_ms=elapsed)
        except Exception as exc:
            msg = str(exc)
            if "没有权限" in msg or "permission" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                    state="permission_required", checked_at=_now(), error_code="permission_denied",
                    permission_hint="api requires additional permission")
            if "积分" in msg or "insufficient" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                    state="insufficient_points", checked_at=_now(), error_code="insufficient_points")
            if "error" in msg.lower() or "invalid" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                    state="unavailable", checked_at=_now(), error_code="api_error")
            return CapabilityStatus(
                provider=self.name, capability=ProviderCapability.TRADE_CALENDAR,
                state="unavailable", checked_at=_now(), error_code=msg[:80])

    def _probe_research(self, capability: ProviderCapability) -> CapabilityStatus:
        api_name = "daily_basic" if capability == ProviderCapability.VALUATION_DAILY else "fina_indicator"
        try:
            api = self._import()
            start = time.monotonic()
            if capability == ProviderCapability.VALUATION_DAILY:
                df = api.daily_basic(ts_code="600519.SH", start_date="20260701", end_date="20260723")
            else:
                df = api.fina_indicator(ts_code="600519.SH", start_date="20260701", end_date="20260723")
            elapsed = int((time.monotonic() - start) * 1000)
            rows = len(df) if df is not None else 0
            if df is not None and rows > 0:
                return CapabilityStatus(
                    provider=self.name, capability=capability, state="available",
                    checked_at=_now(), latency_ms=elapsed, detail_rows=rows)
            return CapabilityStatus(
                provider=self.name, capability=capability, state="empty_response",
                checked_at=_now(), latency_ms=elapsed)
        except Exception as exc:
            msg = str(exc)
            if "没有权限" in msg or "permission denied" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=capability, state="permission_required",
                    checked_at=_now(), error_code="permission_denied")
            if "积分" in msg or "insufficient points" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=capability, state="insufficient_points",
                    checked_at=_now(), error_code="insufficient_points")
            if "error" in msg.lower():
                return CapabilityStatus(
                    provider=self.name, capability=capability, state="unavailable",
                    checked_at=_now(), error_code=msg[:80])
            return CapabilityStatus(
                provider=self.name, capability=capability, state="unavailable",
                checked_at=_now(), error_code=msg[:80])

    def fetch(self, capability: ProviderCapability, **kwargs: Any):
        raise NotImplementedError("fetch by capability — use specific adapter methods")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

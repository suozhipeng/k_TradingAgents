"""Iwencai (问财) provider adapter for A-share data."""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase
from ..common import (
    _coerce_float,
    _coerce_int,
    _env,
    _ensure_records,
    _first_non_null,
    _format_timestamp,
    _records_from_payload,
)
from ...errors import AStockSourceUnavailableError
from ...schema import AStockRequest
from ...symbols import normalize_astock_symbol


class IwencaiAdapter(AStockAdapterBase):
    name = "iwencai"

    def __init__(self, wencai_module: Any = None, cookie: Optional[str] = None, user_agent: Optional[str] = None, retry: Optional[int] = None, sleep: Optional[float] = None, **config: Any):
        super(IwencaiAdapter, self).__init__(wencai_module=wencai_module, cookie=cookie, user_agent=user_agent, retry=retry, sleep=sleep, **config)
        self._module = wencai_module
        self.cookie = cookie if cookie is not None else _env("ASTOCK_IWENCAI_COOKIE")
        self.user_agent = user_agent if user_agent is not None else _env("ASTOCK_IWENCAI_USER_AGENT")
        self.retry = int(retry if retry is not None else config.get("retry", _env("ASTOCK_IWENCAI_RETRY", "2")))
        self.sleep = float(sleep if sleep is not None else config.get("sleep", _env("ASTOCK_IWENCAI_SLEEP", "0.2")))

    def _load(self):
        if self._module is not None:
            return self._module
        try:
            self._module = importlib.import_module("pywencai")
            return self._module
        except Exception as exc:  # pragma: no cover
            raise AStockSourceUnavailableError(self.name, "pywencai import failed: {0}".format(exc))

    def _call(self, request: AStockRequest, query: str):
        if not self.cookie:
            raise AStockSourceUnavailableError(self.name, "iwencai cookie not configured; set ASTOCK_IWENCAI_COOKIE", capability=request.capability)
        module = self._load()
        getter = getattr(module, "get", None)
        if getter is None:
            raise AStockSourceUnavailableError(self.name, "pywencai.get missing", capability=request.capability)
        try:
            return getter(
                query=query,
                loop=False,
                cookie=self.cookie,
                user_agent=self.user_agent,
                retry=self.retry,
                sleep=self.sleep,
                query_type=self.config.get("query_type", "stock"),
                request_params={"timeout": (5, 10)},
            )
        except Exception as exc:
            raise AStockSourceUnavailableError(self.name, "pywencai query failed: {0}".format(exc), capability=request.capability)

    def _parse_search(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "iwencai search returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            symbol = normalize_astock_symbol(str(_first_non_null(row, ("股票代码", "code", "symbol"), request.symbol)))
            items.append(
                {
                    "symbol": symbol,
                    "name": _first_non_null(row, ("股票简称", "name", "名称")),
                    "price": _coerce_float(_first_non_null(row, ("最新价", "price"))),
                    "pct_change": _coerce_float(_first_non_null(row, ("涨跌幅", "pct_change"))),
                    "keyword": _first_non_null(row, ("问财关键词", "query", "关键词"), request.query or request.raw_symbol),
                }
            )
        return {"items": items, "count": len(items), "query": request.query or request.raw_symbol}

    def _parse_expectation(self, request: AStockRequest, payload: Any) -> Dict[str, Any]:
        records = _ensure_records(_records_from_payload(payload), request, self.name, "iwencai expectation returned no rows")
        items: List[Dict[str, Any]] = []
        for row in records:
            items.append(
                {
                    "symbol": normalize_astock_symbol(str(_first_non_null(row, ("股票代码", "code", "symbol"), request.symbol))),
                    "name": _first_non_null(row, ("股票简称", "name", "名称")),
                    "institution_count": _coerce_int(_first_non_null(row, ("机构数", "机构家数", "report_count"))),
                    "consensus_rating": _first_non_null(row, ("一致预期评级", "评级", "rating")),
                    "eps_2026": _coerce_float(_first_non_null(row, ("2026预测每股收益", "2026E每股收益"))),
                }
            )
        return {"items": items, "count": len(items), "query": request.query or request.raw_symbol}

    def get_institution_expectation(self, request: AStockRequest):
        query = str(request.query or (request.raw_symbol + " 机构预期")).strip()
        return self._parse_expectation(request, self._call(request, query))

    def search_research(self, request: AStockRequest):
        query = str(request.query or request.raw_symbol).strip()
        if not query:
            raise AStockSourceUnavailableError(self.name, "iwencai query empty", capability=request.capability)
        return self._parse_search(request, self._call(request, query))

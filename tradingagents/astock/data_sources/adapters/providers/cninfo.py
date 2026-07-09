"""Cninfo (巨潮资讯) provider adapter for A-share announcements."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base import AStockAdapterBase

logger = logging.getLogger(__name__)
from ..common import (
    _coerce_float,
    _env,
    _ensure_records,
    _first_non_null,
    _format_timestamp,
    _random_sleep,
    _records_from_payload,
    _retry_with_backoff,
    _strip_html,
)
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest
from ...symbols import astock_code, normalize_astock_symbol, split_astock_symbol


class CninfoAdapter(AStockAdapterBase):
    name = "cninfo"

    def __init__(self, session: Any = None, timeout: Optional[float] = None, headers: Optional[Dict[str, str]] = None, cookie: Optional[str] = None, csrf_token: Optional[str] = None, **config: Any):
        super(CninfoAdapter, self).__init__(session=session, timeout=timeout, headers=headers, cookie=cookie, csrf_token=csrf_token, **config)
        self._session = session
        self.timeout = timeout if timeout is not None else _coerce_float(config.get("timeout") or _env("ASTOCK_CNINFO_TIMEOUT", "10")) or 10.0
        self.cookie = cookie if cookie is not None else _env("ASTOCK_CNINFO_COOKIE")
        self.csrf_token = csrf_token if csrf_token is not None else _env("ASTOCK_CNINFO_CSRF_TOKEN")
        self.headers = {
            "User-Agent": _env("ASTOCK_CNINFO_USER_AGENT", "Mozilla/5.0 TradingAgents/astock"),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/search",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.cookie:
            self.headers["Cookie"] = self.cookie
        if self.csrf_token:
            self.headers["X-CSRF-TOKEN"] = self.csrf_token
        if headers:
            self.headers.update(headers)
        self._org_cache: Dict[str, str] = {}

    def _get_session(self):
        if self._session is not None:
            return self._session
        try:
            import requests  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise AStockSourceUnavailableError(self.name, "requests import failed: {0}".format(exc))
        self._session = requests.Session()
        return self._session

    def _request_json(self, request: AStockRequest, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        session = self._get_session()
        # Anti-crawling: random delay before each request
        _random_sleep(0.5, 2.0)

        def _do_request():
            response = getattr(session, method.lower())(url, headers=self.headers, timeout=self.timeout, **kwargs)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("cninfo response is not a JSON object")
            return data

        try:
            return _retry_with_backoff(_do_request, max_retries=2, base_delay=1.0, name="cninfo." + method)
        except AStockNoDataError:
            raise
        except Exception as exc:
            raise AStockSourceUnavailableError(
                self.name, "cninfo request failed after retries: {0}".format(exc),
                capability=request.capability,
            )

    def _exchange_meta(self, request: AStockRequest) -> Dict[str, str]:
        code, exchange = split_astock_symbol(request.symbol)
        exchange = exchange or "SH"
        mapping = {
            "SH": {"column": "sse", "plate": "sh", "stock_list": "https://www.cninfo.com.cn/new/data/sse_stock.json"},
            "SZ": {"column": "szse", "plate": "sz", "stock_list": "https://www.cninfo.com.cn/new/data/szse_stock.json"},
            "BJ": {"column": "bjse", "plate": "bj", "stock_list": "https://www.cninfo.com.cn/new/data/bjse_stock.json"},
        }
        return mapping.get(exchange, mapping["SH"])

    def _get_org_id(self, request: AStockRequest) -> str:
        code = astock_code(request.symbol)
        if code in self._org_cache:
            return self._org_cache[code]
        meta = self._exchange_meta(request)
        data = self._request_json(request, "GET", meta["stock_list"])
        stock_list = data.get("stockList") or []
        for item in stock_list:
            if str(item.get("code")) == code and item.get("orgId"):
                self._org_cache[code] = str(item["orgId"])
                return self._org_cache[code]
        raise AStockNoDataError(request.raw_symbol, request.symbol, "cninfo orgId not found", source=self.name, capability=request.capability)

    def _query_announcements(self, request: AStockRequest) -> Dict[str, Any]:
        meta = self._exchange_meta(request)
        org_id = ""
        try:
            org_id = self._get_org_id(request)
        except Exception:
            org_id = ""
        payload = {
            "pageNum": request.page or 1,
            "pageSize": request.limit or int(self.config.get("page_size", 20)),
            "tabName": "fulltext",
            "column": meta["column"],
            "plate": meta["plate"],
            "stock": "{0},{1}".format(astock_code(request.symbol), org_id) if org_id else "",
            "searchkey": request.query or astock_code(request.symbol) or self.config.get("searchkey", ""),
            "secid": request.extras.get("secid", ""),
            "seDate": request.extras.get("seDate", self.config.get("seDate", "")),
            "sortName": request.extras.get("sortName", ""),
            "sortType": request.extras.get("sortType", ""),
            "isHLtitle": "true",
        }
        return self._request_json(request, "POST", "https://www.cninfo.com.cn/new/hisAnnouncement/query", data=payload)

    def _normalize_announcements(self, request: AStockRequest, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_items = payload.get("announcements") or []
        if not raw_items:
            raise AStockNoDataError(request.raw_symbol, request.symbol, "cninfo announcement list empty", source=self.name, capability=request.capability)
        items: List[Dict[str, Any]] = []
        for row in raw_items:
            adjunct = str(row.get("adjunctUrl") or "").lstrip("/")
            download_url = "https://static.cninfo.com.cn/{0}".format(adjunct) if adjunct else None
            items.append(
                {
                    "announcement_id": str(row.get("announcementId") or ""),
                    "symbol": normalize_astock_symbol(str(row.get("secCode") or request.symbol)),
                    "name": _strip_html(row.get("secName")),
                    "title": _strip_html(row.get("announcementTitle") or row.get("shortTitle")),
                    "published_at": _format_timestamp(row.get("announcementTime")),
                    "pdf_url": download_url,
                    "download_url": download_url,
                    "adjunct_size_kb": _coerce_float(row.get("adjunctSize")),
                    "adjunct_type": row.get("adjunctType"),
                    "page_column": row.get("pageColumn"),
                    "announcement_type": row.get("announcementType"),
                    "org_id": row.get("orgId"),
                }
            )
        return {
            "items": items,
            "count": len(items),
            "total": payload.get("totalAnnouncement") or len(items),
            "total_pages": payload.get("totalpages"),
            "has_more": bool(payload.get("hasMore")),
        }

    def get_announcement_summary(self, request: AStockRequest):
        payload = self._query_announcements(request)
        return self._normalize_announcements(request, payload)

    def get_announcement_full(self, request: AStockRequest):
        summary = self.get_announcement_summary(request)
        announcement_id = str(request.extras.get("announcement_id") or request.query or "").strip()
        items = summary.get("items", [])
        chosen = items[0]
        if announcement_id:
            for item in items:
                if str(item.get("announcement_id")) == announcement_id:
                    chosen = item
                    break
        return dict(chosen)

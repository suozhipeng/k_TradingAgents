"""
A-share suspension (停复牌) and price limit data sources.

Provides:
- SuspensionRecord schema for daily suspension/resumption events
- fetch_suspension_list() via multiple backends (akshare, EastMoney)
- get_price_limit_pct() — per-stock limit percentage (10% normal, 5% ST/*ST)
- is_suspended_today() — real-time suspension check
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from .errors import AStockNoDataError, AStockSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass
class SuspensionRecord:
    """Single suspension/resumption event for an A-share stock.

    Attributes
    ----------
    symbol : str
        Normalized A-share symbol (e.g. ``"600519.SH"``).
    code : str
        Raw exchange code (e.g. ``"600519"``).
    suspend_date : str
        Date the stock was suspended (YYYY-MM-DD).
    resume_date : str or None
        Date the stock resumed trading, if known.
    reason : str or None
        Reason for suspension, if available.
    is_suspended : bool
        Whether the stock is currently suspended as of the latest data.
    """
    symbol: str
    code: str
    suspend_date: str
    resume_date: Optional[str] = None
    reason: Optional[str] = None
    is_suspended: bool = True

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "code": self.code,
            "suspend_date": self.suspend_date,
            "resume_date": self.resume_date,
            "reason": self.reason,
            "is_suspended": self.is_suspended,
        }


# ---------------------------------------------------------------------------
# Price limit helpers
# ---------------------------------------------------------------------------


def get_price_limit_pct(st_stock: bool = False) -> float:
    """Return the daily price limit percentage for A-share stocks.

    Parameters
    ----------
    st_stock : bool
        True for ST/*ST stocks (5% limit).

    Returns
    -------
    float
        0.10 for normal stocks, 0.05 for ST stocks.

    Notes
    -----
    Northbound (沪港通/深港通) stocks also follow these rules.
    New IPO stocks have special rules (44% first day) handled separately.
    """
    return 0.05 if st_stock else 0.10


def get_price_limit_prices(
    prev_close: float,
    st_stock: bool = False,
    round_digits: int = 2,
) -> tuple[float, float]:
    """Compute upper and lower price limits for a stock.

    Parameters
    ----------
    prev_close : float
        Previous trading day's closing price.
    st_stock : bool
        Whether the stock is ST/*ST.
    round_digits : int
        Rounding for A-share price ticks (default 2).
        Most A-shares use 2 decimal places; some use 3.

    Returns
    -------
    (upper_limit, lower_limit) : tuple[float, float]
    """
    pct = get_price_limit_pct(st_stock)
    upper = round(prev_close * (1 + pct), round_digits)
    lower = round(prev_close * (1 - pct), round_digits)
    return upper, lower


# ---------------------------------------------------------------------------
# Akshare backend
# ---------------------------------------------------------------------------


def _normalize_code(code: str) -> str:
    """Normalize an A-share code to 6 digits."""
    code = str(code).strip().upper()
    if code.endswith((".SH", ".SZ")):
        code = code[:-3]
    return code.zfill(6) if code.isdigit() else code


def _make_symbol(code: str, exchange: Optional[str] = None) -> str:
    """Build a full symbol from a code.

    Exchange is inferred if not provided:
      - 6xxxxx → .SH
      - 0xxxxx, 3xxxxx → .SZ
    """
    code = _normalize_code(code)
    if exchange:
        suffix = ".SH" if exchange.upper() in ("SH", "SSE", "SHH") else ".SZ"
    elif code.startswith(("6", "9")):
        suffix = ".SH"
    else:
        suffix = ".SZ"
    return code + suffix


def fetch_suspension_via_akshare(
    date: Optional[str] = None,
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from akshare.

    Uses ``ak.stock_zh_a_suspend_daily()`` which returns stocks that are
    suspended on a given date.

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    list[SuspensionRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    try:
        import akshare as ak

        df = ak.stock_zh_a_suspend_daily(suspended_date=date)
    except ImportError:
        raise AStockSourceUnavailableError(
            "akshare",
            "akshare is not installed — cannot fetch suspension data",
        )
    except Exception as exc:
        raise AStockSourceUnavailableError(
            "akshare",
            str(exc),
        )

    if df is None or df.empty:
        return []

    records: list[SuspensionRecord] = []
    for _, row in df.iterrows():
        code = _normalize_code(str(row.get("code", "")))
        if not code:
            continue
        symbol = _make_symbol(code)
        records.append(
            SuspensionRecord(
                symbol=symbol,
                code=code,
                suspend_date=str(row.get("suspended_date", date)),
                resume_date=str(row.get("resumed_date", "")) or None,
                reason=str(row.get("reason", "")) or None,
                is_suspended=True,
            ),
        )

    return records


def is_symbol_suspended_akshare(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check if a single symbol is suspended via akshare on a given date.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.
    date : str or None
        Date in ``\"YYYY-MM-DD\"`` format.  Defaults to today.

    Returns
    -------
    (is_suspended, reason) : tuple[bool, str | None]
    """
    try:
        check_date = date or datetime.date.today().isoformat()
        records = fetch_suspension_via_akshare(check_date)
        code = _normalize_code(symbol)
        for rec in records:
            if rec.code == code:
                return True, rec.reason or "suspended_akshare"
        return False, None
    except Exception:
        return False, None


# ---------------------------------------------------------------------------
# EastMoney backend
# ---------------------------------------------------------------------------

EM_SUSPENSION_URL = (
    "https://datacenter.eastmoney.com/securities/api/data/v1/get"
)


def fetch_suspension_via_eastmoney(
    date: Optional[str] = None,
    page_size: int = 5000,
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from EastMoney.

    Uses the EastMoney datacenter API endpoint for suspension data.

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    page_size : int
        Max results per page (default 5000).

    Returns
    -------
    list[SuspensionRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    import requests

    params = {
        "reportName": "RPT_DMSK_FN_GKCP",
        "columns": "SECUCODE,SECURITY_NAME_ABBR,TRADE_DATE,SUSPEND_REASON",
        "filter": f'(TRADE_DATE=\'{date}\')',
        "pageNumber": 1,
        "pageSize": min(page_size, 10000),
        "sortTypes": -1,
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }

    try:
        resp = requests.get(
            EM_SUSPENSION_URL,
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            },
            timeout=15,
        )
        data = resp.json()
    except requests.RequestException as exc:
        raise AStockSourceUnavailableError(
            "eastmoney", f"HTTP error fetching suspension data: {exc}",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise AStockSourceUnavailableError(
            "eastmoney",
            f"JSON decode error: {exc}",
        )

    result_list = (
        data.get("result", {})
        if isinstance(data.get("result"), dict)
        else data.get("data", {})
        if isinstance(data.get("data"), dict)
        else data
    )

    # Try multiple response shapes
    rows = None
    if isinstance(result_list, dict):
        rows = result_list.get("list", result_list.get("data", []))
    elif isinstance(result_list, list):
        rows = result_list
    else:
        rows = data.get("list", data.get("data", []))

    if not rows:
        return []

    records: list[SuspensionRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        secucode = str(row.get("SECUCODE", ""))
        # SECUCODE format: "600519.SH" or "600519"
        code = _normalize_code(secucode)
        if not code:
            continue
        symbol = _make_symbol(code)
        records.append(
            SuspensionRecord(
                symbol=symbol,
                code=code,
                suspend_date=str(row.get("TRADE_DATE", date)),
                resume_date=None,
                reason=str(row.get("SUSPEND_REASON", "")) or None,
                is_suspended=True,
            ),
        )

    return records


# ---------------------------------------------------------------------------
# Unified facade
# ---------------------------------------------------------------------------


def fetch_suspension_list(
    date: Optional[str] = None,
    source: str = "akshare",
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from the specified source.

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    source : str
        One of ``"akshare"``, ``"eastmoney"``.

    Returns
    -------
    list[SuspensionRecord]
    """
    source_map: dict[str, Any] = {
        "akshare": fetch_suspension_via_akshare,
        "eastmoney": fetch_suspension_via_eastmoney,
    }
    fetcher = source_map.get(source)
    if fetcher is None:
        raise ValueError(
            f"Unknown suspension source {source!r}. "
            f"Available: {list(source_map)}",
        )
    return fetcher(date)


def is_suspended(
    symbol: str,
    source: str = "akshare",
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check if a stock is suspended (primary: akshare, fallback: EastMoney).

    This is the recommended entry point for run-time suspension checks.
    Falls back to EastMoney if akshare fails.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.
    source : str
        Primary source (``"akshare"`` or ``"eastmoney"``).
    date : str or None
        Date to check (YYYY-MM-DD).  Defaults to today.

    Returns
    -------
    (is_suspended, reason) : tuple[bool, str | None]
    """
    check_date = date or datetime.date.today().isoformat()
    # ── Primary source ──
    try:
        if source == "akshare":
            suspended, reason = is_symbol_suspended_akshare(symbol, check_date)
            if suspended:
                return True, reason or "suspended_akshare"
        else:
            code = _normalize_code(symbol)
            records = fetch_suspension_via_eastmoney(check_date)
            for rec in records:
                if rec.code == code:
                    return True, rec.reason or "suspended_eastmoney"
            return False, None
    except Exception:
        pass

    # ── Fallback: try the other source ──
    try:
        if source == "akshare":
            code = _normalize_code(symbol)
            records = fetch_suspension_via_eastmoney(check_date)
            for rec in records:
                if rec.code == code:
                    return True, rec.reason or "suspended_eastmoney"
            return False, None
        else:
            return is_symbol_suspended_akshare(symbol, check_date)
    except Exception:
        return False, None

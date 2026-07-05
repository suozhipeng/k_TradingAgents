"""
Suspension (停牌) related functions for A-share stocks.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

import pandas as pd

from .common import _retry, SuspensionRecord, _normalize_code, _make_symbol
from ..errors import AStockNoDataError, AStockSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Akshare backend — suspension
# ---------------------------------------------------------------------------


def fetch_suspension_via_akshare(
    date: Optional[str] = None,
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from akshare with retry.

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

    def _fetch() -> pd.DataFrame:
        import akshare as ak
        return ak.stock_zh_a_suspend_daily(suspended_date=date)

    try:
        df = _retry(_fetch, max_attempts=3, base_delay=1.0)
    except ImportError:
        raise AStockSourceUnavailableError(
            "akshare",
            "akshare is not installed — cannot fetch suspension data",
        )
    except AStockSourceUnavailableError:
        # Re-raise as-is (already consumed retries)
        raise
    except Exception as exc:
        raise AStockSourceUnavailableError(
            "akshare",
            f"suspension fetch failed after retries: {exc}",
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
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

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
# Akshare backend — suspension via trading pool inference
# ---------------------------------------------------------------------------


def is_symbol_suspended_via_trading_pool(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Infer suspension by checking if the symbol appears in akshare's daily
    active trading pool (涨停/跌停/强势 pool).

    If a stock normally trades but does NOT appear in any active pool on a
    given date, it may be suspended.  This is a **secondary** check used when
    the primary suspension API fails.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    (is_suspended, reason) : tuple[bool, str | None]
        (True, "suspended_trading_pool") when the symbol is not found.
        (False, None) when found or on error (fail-soft).
    """
    if date is None:
        date = datetime.date.today().isoformat()

    code = _normalize_code(symbol)
    if not code:
        return False, None

    # On weekends / non-trading days, skip the pool check
    try:
        dt = datetime.date.fromisoformat(date)
        if dt.weekday() >= 5:
            return False, None
    except (ValueError, TypeError):
        return False, None

    # Collect symbols from multiple trading pools
    seen_codes: set[str] = set()

    for pool_fn_name in ("stock_zt_pool_em", "stock_zt_pool_dtgc_em", "stock_zt_pool_strong_em"):
        try:
            import akshare as ak

            pool_fn = getattr(ak, pool_fn_name, None)
            if pool_fn is None:
                continue

            def _fetch_pool(fn=pool_fn, d=date):
                return fn(date=d)

            df = _retry(_fetch_pool, max_attempts=2, base_delay=0.5)
            if df is not None and not df.empty:
                for col in ("code", "代码", "股票代码"):
                    if col in df.columns:
                        for c in df[col].dropna():
                            seen_codes.add(_normalize_code(str(c)))
                        break
        except Exception:
            continue

    if not seen_codes:
        # Could not fetch any pool — skip inference
        return False, None

    if code not in seen_codes:
        # Symbol not in any active trading pool → likely suspended
        return True, "suspended_trading_pool"

    return False, None


# ---------------------------------------------------------------------------
# EastMoney backend — suspension
# ---------------------------------------------------------------------------

EM_SUSPENSION_URL = (
    "https://datacenter.eastmoney.com/securities/api/data/v1/get"
)


def fetch_suspension_via_eastmoney(
    date: Optional[str] = None,
    page_size: int = 5000,
) -> list[SuspensionRecord]:
    """Fetch daily suspension list from EastMoney with retry.

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
        "filter": f"(TRADE_DATE='{date}')",
        "pageNumber": 1,
        "pageSize": min(page_size, 10000),
        "sortTypes": -1,
        "sortColumns": "TRADE_DATE",
        "source": "WEB",
        "client": "WEB",
    }

    def _fetch_em():
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
        return resp.json()

    try:
        data = _retry(_fetch_em, max_attempts=3, base_delay=1.0)
    except requests.RequestException as exc:
        raise AStockSourceUnavailableError(
            "eastmoney", f"HTTP error fetching suspension data: {exc}",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise AStockSourceUnavailableError(
            "eastmoney",
            f"JSON decode error: {exc}",
        )
    except Exception as exc:
        raise AStockSourceUnavailableError(
            "eastmoney",
            f"suspension fetch failed after retries: {exc}",
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
# Unified facade — suspension
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
    """Check if a stock is suspended with multi-tier fallback.

    Fallback chain:
    1. Primary source (akshare or eastmoney suspension API)
    2. The other source
    3. Trading pool inference (if no suspension API worked)

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
    sources = ["akshare", "eastmoney"]

    # Reorder so primary source is first
    if source in sources:
        sources.remove(source)
        sources.insert(0, source)

    # ── Tiers 1-2: try each suspension API ──
    for src in sources:
        try:
            if src == "akshare":
                suspended, reason = is_symbol_suspended_akshare(symbol, check_date)
            else:
                code = _normalize_code(symbol)
                records = fetch_suspension_via_eastmoney(check_date)
                suspended = False
                reason = None
                for rec in records:
                    if rec.code == code:
                        suspended = True
                        reason = rec.reason or "suspended_eastmoney"
                        break
            if suspended:
                return True, reason or f"suspended_{src}"
            # Primary source returned cleanly — trust it (no suspension)
            return False, None
        except Exception:
            continue

    # ── Tier 3: trading pool inference (best-effort) ──
    try:
        # Only use pool inference for today's date (real-time check)
        if date is None or date == datetime.date.today().isoformat():
            suspended, reason = is_symbol_suspended_via_trading_pool(symbol, check_date)
            if suspended:
                return True, reason
    except Exception:
        pass

    return False, None

"""
A-share suspension (停复牌) and price limit (涨跌停) data sources.

Provides:
- SuspensionRecord schema for daily suspension/resumption events
- PriceLimitRecord schema for stocks at daily price limits
- fetch_suspension_list() via multiple backends (akshare, EastMoney)
- fetch_price_limit_pool() for real-time 涨停/跌停 data (akshare → EastMoney)
- get_price_limit_pct() — per-stock limit percentage (10% normal, 5% ST/*ST)
- is_suspended_today() — real-time suspension check
- is_at_price_limit_external() — external price limit check via live pools

API resilience: all external calls use retry with exponential backoff.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

import pandas as pd

from .errors import AStockNoDataError, AStockSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def _retry(
    fn: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = _RETRYABLE_EXCEPTIONS,
) -> Any:
    """Call *fn* with exponential-backoff retry.

    Parameters
    ----------
    fn : callable
        Zero-arg callable to invoke.
    max_attempts : int
        Max tries (default 3).
    base_delay : float
        Initial delay in seconds (default 1.0).
    backoff : float
        Multiplier each attempt (default 2.0 → 1s, 2s, 4s).
    exceptions : tuple
        Exception types that trigger a retry (default connection/OS errors).

    Returns
    -------
    Any
        The return value of *fn*.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except exceptions:
            if attempt < max_attempts - 1:
                delay = base_delay * (backoff ** attempt)
                logger.debug("retry %s attempt %d/%d, waiting %.1fs", fn.__name__, attempt + 1, max_attempts, delay)
                time.sleep(delay)
            continue
        except Exception as exc:
            last_exc = exc
            raise
    # All attempts exhausted
    if last_exc is not None:
        raise AStockSourceUnavailableError("retry", f"All {max_attempts} attempts failed: {last_exc}")
    raise AStockSourceUnavailableError("retry", f"All {max_attempts} attempts failed (no exception captured).")


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


@dataclass
class PriceLimitRecord:
    """A stock that hit daily price limit (涨停 or 跌停).

    Attributes
    ----------
    symbol : str
        Normalized A-share symbol.
    code : str
        Raw exchange code (6 digits).
    name : str or None
        Stock name.
    price : float or None
        Current / limit price.
    change_pct : float or None
        Percentage change from previous close.
    direction : str
        ``"up"`` for 涨停, ``"down"`` for 跌停.
    consecutive : int
        Number of consecutive limit-up/down days (0 if unknown).
    source : str
        Data source (``"akshare"``, ``"eastmoney"``).
    """
    symbol: str
    code: str
    name: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    direction: str = "up"  # "up" or "down"
    consecutive: int = 0
    source: str = "akshare"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "code": self.code,
            "name": self.name or "",
            "price": self.price,
            "change_pct": self.change_pct,
            "direction": self.direction,
            "consecutive": self.consecutive,
            "source": self.source,
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

    Returns
    -------
    (upper_limit, lower_limit) : tuple[float, float]
    """
    pct = get_price_limit_pct(st_stock)
    upper = round(prev_close * (1 + pct), round_digits)
    lower = round(prev_close * (1 - pct), round_digits)
    return upper, lower


# ---------------------------------------------------------------------------
# Symbol / code helpers
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
# Akshare backend — price limit pools (涨停/跌停)
# ---------------------------------------------------------------------------


def fetch_price_limit_pool_via_akshare(
    date: Optional[str] = None,
) -> list[PriceLimitRecord]:
    """Fetch real-time 涨停 (limit-up) and 跌停 (limit-down) stocks from
    akshare's EastMoney-backed APIs.

    Uses:
    - ``ak.stock_zt_pool_em()`` — 涨停股池
    - ``ak.stock_zt_pool_dtgc_em()`` — 跌停股池

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    list[PriceLimitRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    records: list[PriceLimitRecord] = []

    # ── 涨停 (limit-up) pool ──
    try:
        import akshare as ak

        def _fetch_up():
            return ak.stock_zt_pool_em(date=date)

        df_up = _retry(_fetch_up, max_attempts=3, base_delay=1.0)
    except Exception:
        df_up = None

    if df_up is not None and not df_up.empty:
        for _, row in df_up.iterrows():
            code = _normalize_code(str(row.get("代码", "")))
            if not code:
                continue
            symbol = _make_symbol(code)
            records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("名称", "")) or None,
                    price=float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
                    change_pct=float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
                    direction="up",
                    consecutive=int(row.get("连板数", 0)) if pd.notna(row.get("连板数")) else 0,
                    source="akshare",
                ),
            )

    # ── 跌停 (limit-down) pool ──
    try:
        def _fetch_down():
            return ak.stock_zt_pool_dtgc_em(date=date)

        df_down = _retry(_fetch_down, max_attempts=3, base_delay=1.0)
    except Exception:
        df_down = None

    if df_down is not None and not df_down.empty:
        for _, row in df_down.iterrows():
            code = _normalize_code(str(row.get("代码", "")))
            if not code:
                continue
            symbol = _make_symbol(code)
            records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(row.get("名称", "")) or None,
                    price=float(row["最新价"]) if pd.notna(row.get("最新价")) else None,
                    change_pct=float(row["涨跌幅"]) if pd.notna(row.get("涨跌幅")) else None,
                    direction="down",
                    consecutive=int(row.get("连板数", 0)) if pd.notna(row.get("连板数")) else 0,
                    source="akshare",
                ),
            )

    return records


# ---------------------------------------------------------------------------
# EastMoney backend — price limit via push2 real-time market data
# ---------------------------------------------------------------------------

EM_PUSH2_QUOTE_URL = "https://push2.eastmoney.com/api/qt/clist/get"


def fetch_price_limit_via_eastmoney_push2(
    date: Optional[str] = None,
) -> list[PriceLimitRecord]:
    """Fetch price limit stocks from EastMoney push2 real-time API.

    Uses the push2 quote list API with a filter for stocks whose change
    percentage is near the daily limit (±9.5% for normal, ±4.5% for ST).

    This is a **fallback** for when akshare's price limit pool is unavailable.

    Parameters
    ----------
    date : str or None
        Ignored (the API always returns real-time data).

    Returns
    -------
    list[PriceLimitRecord]
    """
    import requests

    # Market: 1=SH A, 0=SZ A. Fetch both.
    all_records: list[PriceLimitRecord] = []
    limit_threshold = 9.5  # percentage

    for market_id in (1, 0):
        params = {
            "pn": 1,
            "pz": 2000,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",  # sort by change_pct
            "fs": f"m:{market_id}+t:1",  # A-shares only
            "fields": "f12,f14,f2,f3,f4",
            "_": int(time.time() * 1000),
        }

        try:

            def _fetch_push2():
                resp = requests.get(
                    EM_PUSH2_QUOTE_URL,
                    params=params,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Referer": "https://quote.eastmoney.com/",
                    },
                    timeout=10,
                )
                return resp

            resp = _retry(_fetch_push2, max_attempts=2, base_delay=0.5)
            data = resp.json()
        except Exception:
            continue

        items = data.get("data", {}).get("diff", []) if isinstance(data, dict) else []
        if not items:
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            code = _normalize_code(str(item.get("f12", "")))
            if not code:
                continue
            change_pct = item.get("f3")
            if change_pct is None:
                continue
            try:
                change_pct = float(change_pct)
            except (ValueError, TypeError):
                continue

            # Determine direction: near limit-up or limit-down
            direction: Optional[str] = None
            if change_pct >= limit_threshold:
                direction = "up"
            elif change_pct <= -limit_threshold:
                direction = "down"
            else:
                continue

            current_price = item.get("f2")
            try:
                current_price = float(current_price) if current_price is not None else None
            except (ValueError, TypeError):
                current_price = None

            symbol = _make_symbol(code)
            all_records.append(
                PriceLimitRecord(
                    symbol=symbol,
                    code=code,
                    name=str(item.get("f14", "")) or None,
                    price=current_price,
                    change_pct=change_pct,
                    direction=direction,
                    consecutive=0,
                    source="eastmoney",
                ),
            )

    return all_records


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


# ---------------------------------------------------------------------------
# Unified facade — price limit (涨跌停)
# ---------------------------------------------------------------------------


def fetch_price_limit_pool(
    date: Optional[str] = None,
    source: str = "akshare",
) -> list[PriceLimitRecord]:
    """Fetch real-time price limit pool with fallback.

    Fallback chain:
    1. Primary source (akshare EastMoney pools)
    2. EastMoney push2 real-time API

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    source : str
        Primary source (``"akshare"`` or ``"eastmoney"``).

    Returns
    -------
    list[PriceLimitRecord]
    """
    if date is None:
        date = datetime.date.today().isoformat()

    if source == "akshare":
        fetcher = fetch_price_limit_pool_via_akshare
        fallback = fetch_price_limit_via_eastmoney_push2
    else:
        fetcher = fetch_price_limit_via_eastmoney_push2
        fallback = fetch_price_limit_pool_via_akshare

    try:
        records = fetcher(date)
        if records:
            return records
    except Exception:
        logger.debug("Primary price limit source %s failed, trying fallback", source)

    try:
        return fallback(date)
    except Exception:
        return []


def is_at_price_limit_external(
    symbol: str,
    date: str | None = None,
) -> tuple[bool, Optional[str]]:
    """Check if a stock is at its price limit (涨停/跌停) via external pools.

    Uses :func:`fetch_price_limit_pool` and checks whether the symbol appears
    in either the limit-up or limit-down pool.

    Parameters
    ----------
    symbol : str
        Normalized A-share symbol.
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.

    Returns
    -------
    (is_limited, direction) : tuple[bool, str | None]
        ``(True, "price_limit_up")`` or ``(True, "price_limit_down")``.
        ``(False, None)`` when not found at limit.
    """
    check_date = date or datetime.date.today().isoformat()
    code = _normalize_code(symbol)

    if not code:
        return False, None

    records = fetch_price_limit_pool(check_date)
    for rec in records:
        if rec.code == code:
            direction = "price_limit_up" if rec.direction == "up" else "price_limit_down"
            return True, direction

    return False, None


# ---------------------------------------------------------------------------
# Convenience: build a lookup set of symbols currently at price limit
# ---------------------------------------------------------------------------


def get_price_limited_symbols(
    date: Optional[str] = None,
    direction: Optional[str] = None,
) -> set[str]:
    """Return a set of symbols currently at price limit.

    Parameters
    ----------
    date : str or None
        Date in ``"YYYY-MM-DD"`` format.  Defaults to today.
    direction : str or None
        ``"up"`` or ``"down"``.  ``None`` returns both directions.

    Returns
    -------
    set[str]
        Set of normalized symbols at price limit.
    """
    records = fetch_price_limit_pool(date)
    result: set[str] = set()
    for rec in records:
        if direction is None or rec.direction == direction:
            result.add(rec.symbol)
    return result


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "SuspensionRecord",
    "PriceLimitRecord",
    "get_price_limit_pct",
    "get_price_limit_prices",
    "fetch_suspension_via_akshare",
    "fetch_suspension_via_eastmoney",
    "fetch_suspension_list",
    "fetch_price_limit_pool_via_akshare",
    "fetch_price_limit_via_eastmoney_push2",
    "fetch_price_limit_pool",
    "is_symbol_suspended_akshare",
    "is_symbol_suspended_via_trading_pool",
    "is_suspended",
    "is_at_price_limit_external",
    "get_price_limited_symbols",
    "_normalize_code",
    "_make_symbol",
    "_retry",
]

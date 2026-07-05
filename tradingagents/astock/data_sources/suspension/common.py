"""
Shared helpers, schemas, and utility functions for suspension and price limit data.
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

from ..errors import AStockNoDataError, AStockSourceUnavailableError

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

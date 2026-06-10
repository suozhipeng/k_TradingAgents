"""A-share symbol normalization helpers.

The unified layer works with canonical A-share tickers so routing, caching, and
response schemas stay stable across providers. The public entry point is
``normalize_astock_symbol``.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

_A_SHARE_PREFIX_RE = re.compile(r"^(?P<exchange>SH|SZ|BJ)[\._-]?(?P<code>\d{6})$", re.IGNORECASE)
_A_SHARE_SUFFIX_RE = re.compile(r"^(?P<code>\d{6})(?:[\._-]?(?P<exchange>SH|SZ|BJ|SS))?$", re.IGNORECASE)


def _infer_exchange(code: str) -> str:
    """Infer exchange from a 6-digit A-share code."""
    if not code:
        return ""
    head = code[0]
    if head in ("4", "8"):
        return "BJ"
    if head in ("0", "2", "3"):
        return "SZ"
    if head in ("6", "7", "9"):
        return "SH"
    return "SH"


def split_astock_symbol(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(code, exchange)`` when ``raw`` looks like an A-share ticker."""
    if not isinstance(raw, str):
        return None, None

    text = raw.strip().upper()
    if not text:
        return None, None

    prefix_match = _A_SHARE_PREFIX_RE.match(text)
    if prefix_match:
        return prefix_match.group("code"), prefix_match.group("exchange").replace("SS", "SH")

    suffix_match = _A_SHARE_SUFFIX_RE.match(text)
    if suffix_match:
        code = suffix_match.group("code")
        exchange = suffix_match.group("exchange")
        if exchange:
            return code, exchange.replace("SS", "SH")
        return code, _infer_exchange(code)

    if text.isdigit() and len(text) == 6:
        return text, _infer_exchange(text)

    return None, None


def normalize_astock_symbol(raw: str) -> str:
    """Canonicalize A-share ticker input into ``000001.SZ`` style symbols.

    Supported inputs:
    - ``600519`` -> ``600519.SH``
    - ``600519.sh`` / ``sh600519`` -> ``600519.SH``
    - ``000001.SZ`` -> ``000001.SZ``
    - ``830899`` -> ``830899.BJ``
    """
    if not isinstance(raw, str):
        return raw

    text = raw.strip().upper()
    if not text:
        return text

    code, exchange = split_astock_symbol(text)
    if code and exchange:
        return "{0}.{1}".format(code, exchange)

    return text


def astock_code(raw: str) -> str:
    """Extract the 6-digit A-share code when possible; otherwise return the input."""
    code, _exchange = split_astock_symbol(raw)
    return code or raw

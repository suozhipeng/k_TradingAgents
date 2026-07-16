"""BaoStock provider adapter for A-share data."""

from __future__ import annotations

import logging
import socket
import threading
from typing import Any, Dict

from ..base import AStockAdapterBase

logger = logging.getLogger(__name__)
# Module-level lock to protect process-global socket timeout during baostock login
_baostock_login_lock = threading.Lock()
from ..common import (
    _coerce_float,
    _ensure_records,
    _first_non_null,
    _format_timestamp,
    _random_sleep,
    _retry_with_backoff,
)
from ...errors import AStockNoDataError, AStockSourceUnavailableError
from ...schema import AStockRequest


class BaoStockAdapter(AStockAdapterBase):
    """Baostock 数据源适配器 — 免费开源证券数据平台。

    支持能力:
        - kline (日K, 后复权 adjustflag=2)
        - 无需 API Key, 无需注册, 无限流量

    Baostock 的 symbol 格式为 ``sh.600519`` / ``sz.000001``。
    ``AStockRequest.symbol`` 已标准化为 ``600519.SH``，适配器内部转换。
    """

    name = "baostock"

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self._logged_in = False
        self._login_lock = threading.Lock()

    def _login(self) -> None:
        if self._logged_in:
            return
        try:
            import baostock as bs  # type: ignore
        except ImportError:
            raise AStockSourceUnavailableError(
                self.name, "baostock package not installed. Run: pip install baostock"
            )
        # Per-instance lock protects process-global socket timeout so that
        # concurrent threads on the same adapter don't interfere with each
        # other.  A module-level lock (_baostock_login_lock) is also held
        # to prevent cross-instance interference.
        with self._login_lock, _baostock_login_lock:
            try:
                socket.setdefaulttimeout(5.0)
                lg = bs.login()
            finally:
                socket.setdefaulttimeout(None)
        if lg.error_code != "0":
            raise AStockSourceUnavailableError(
                self.name, "baostock login failed: {0}".format(lg.error_msg)
            )
        self._logged_in = True

    def _logout(self) -> None:
        if self._logged_in:
            try:
                import baostock as bs

                bs.logout()
            except Exception:
                pass
            self._logged_in = False

    @staticmethod
    def _to_bs_symbol(symbol: str) -> str:
        """Convert ``600519.SH`` → ``sh.600519``."""
        code, market = symbol.upper().split(".")
        if market == "SH":
            return "sh." + code
        return "sz." + code

    def get_kline(self, request: AStockRequest) -> dict:
        """获取日 K 线数据（后复权）。

        Baostock 的 adjustflag:
            1=前复权  2=后复权  3=不复权
        """
        self._login()
        bs_symbol = self._to_bs_symbol(request.symbol)
        start = request.start_date or "2000-01-01"
        end = request.end_date or "2026-12-31"

        # Anti-crawling: baostock 虽然免费，但礼貌性延迟
        _random_sleep(0.3, 1.0)

        try:
            import baostock as bs
            import pandas as pd  # noqa: F811
        except ImportError:
            raise AStockSourceUnavailableError(
                self.name, "baostock package not installed"
            )

        def _do_query():
            rs = bs.query_history_k_data_plus(
                bs_symbol,
                fields="date,open,high,low,close,preclose,volume,amount,pctChg",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="2",  # 后复权
            )
            if rs.error_code != "0":
                raise AStockNoDataError(
                    request.raw_symbol,
                    request.symbol,
                    "baostock query failed: {0}".format(rs.error_msg),
                    source=self.name,
                    capability=request.capability,
                )
            bars = []
            while rs.next():
                row = rs.get_row_data()
                date_str = row[0]
                if not date_str:
                    continue
                try:
                    bar = {
                        "date": date_str,
                        "open": float(row[1]) if row[1] else 0.0,
                        "high": float(row[2]) if row[2] else 0.0,
                        "low": float(row[3]) if row[3] else 0.0,
                        "close": float(row[4]) if row[4] else 0.0,
                        "preclose": float(row[5]) if row[5] else 0.0,
                        "volume": float(row[6]) if row[6] else 0.0,
                        "amount": float(row[7]) if row[7] else 0.0,
                        "pctChg": float(row[8]) if row[8] else 0.0,
                    }
                    bars.append(bar)
                except (ValueError, IndexError):
                    continue
            if not bars:
                raise AStockNoDataError(
                    request.raw_symbol,
                    request.symbol,
                    "no kline data from baostock",
                    source=self.name,
                    capability=request.capability,
                )
            return {"bars": bars, "count": len(bars)}

        return _retry_with_backoff(_do_query, max_retries=2, base_delay=0.5, name="baostock.kline")

    def __del__(self):
        """Safety net: ensure logout on garbage collection."""
        try:
            self._logout()
        except Exception:
            pass

    def __enter__(self) -> "BaoStockAdapter":
        return self

    def __exit__(self, *args: Any) -> None:
        self._logout()

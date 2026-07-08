"""Multi-stock price fetching utility."""

from __future__ import annotations

import numpy as np
import pandas as pd


def fetch_multi_stock_prices(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    column: str = "close",
    use_baostock: bool = True,
    use_adjust: str = "2",
) -> pd.DataFrame:
    """批量获取多只股票的历史价格，返回统一 DataFrame。

    优先使用 baostock 光标模式（~3s/23只），
    降级到 AStockDataFacade 逐只获取。

    Parameters
    ----------
    symbols : list of str
        股票代码列表（如 ``\"600519.SH\"``）。
    start_date, end_date : str
        ``\"YYYY-MM-DD\"``。
    column : str
        要获取的列名（默认 ``\"close\"``）。
    use_baostock : bool
        是否优先用 baostock（默认 True）。
    use_adjust : str
        复权类型（baostock: ``\"1\"`` 未复权, ``\"2\"`` 前复权, ``\"3\"`` 后复权; 默认 ``\"2\"``）。

    Returns
    -------
    pd.DataFrame
        列名为股票代码，索引为日期，每列对应一只股票的价格序列。
        返回空 DataFrame 表示全部失败。
    """
    _symbols = list(set(symbols))
    price_data: dict[str, pd.Series] = {}

    if use_baostock:
        import baostock as bs
        import logging

        _log = logging.getLogger(__name__)
        try:
            bs.login()
            try:
                for sym in _symbols:
                    prefix = "sh" if sym.endswith(".SH") else "sz"
                    code = sym.split(".")[0]
                    bs_code = f"{prefix}.{code}"
                    try:
                        rs = bs.query_history_k_data_plus(
                            bs_code,
                            f"date,{column}",
                            start_date=start_date,
                            end_date=end_date,
                            frequency="d",
                            adjustflag=use_adjust,
                        )
                        rows = []
                        while rs.next():
                            row = rs.get_row_data()
                            if len(row) >= 2 and row[0] and row[1]:
                                rows.append(row)
                        if rows:
                            df = pd.DataFrame(rows, columns=["date", column])
                            df["date"] = pd.to_datetime(df["date"])
                            df[column] = df[column].astype(float)
                            df = df.set_index("date").sort_index()
                            price_data[sym] = df[column]
                    except Exception as exc:
                        _log.debug("baostock fetch failed for %s: %s", sym, exc)
            finally:
                bs.logout()
        except Exception:
            _log.warning("baostock logout failed")

    # Fallback: AStockDataFacade 逐只获取
    if not price_data:
        try:
            from tradingagents.astock.data_sources import AStockDataFacade

            facade = AStockDataFacade()
            for sym in _symbols:
                try:
                    resp = facade.get_kline(
                        symbol=sym,
                        start_date=start_date,
                        end_date=end_date,
                        interval="1d",
                    )
                    if resp.status == "ok" and resp.data and resp.data.get("bars"):
                        bars = resp.data["bars"]
                        df = pd.DataFrame(bars)
                        if "date" in df.columns:
                            df["date"] = pd.to_datetime(df["date"])
                            df = df.set_index("date").sort_index()
                            if column in df.columns:
                                price_data[sym] = df[column].astype(float)
                            elif "close" in df.columns:
                                price_data[sym] = df["close"].astype(float)
                except Exception:
                    _log.debug("Facade fetch failed for %s", sym)
        except Exception:
            _log.warning("Facade data fetch failed for all symbols")

    if not price_data:
        return pd.DataFrame()

    result = pd.DataFrame(price_data)
    result = result.dropna(axis=1, how="all")
    return result

"""TradingView Charting Library data API — serves bars in TV-expected JSON format.

GET /api/v1/tv/history?symbol=600519.SH&resolution=5&from=1696000000&to=1697000000
  → returns {s: "ok", t: [...], o: [...], h: [...], l: [...], c: [...], v: [...]}

GET /api/v1/tv/symbols?symbol=600519.SH
  → returns TV symbol info object

Resolution mapping:
  1, 5, 15, 30, 60  → 1m, 5m, 15m, 30m, 60m
  240               → 1d  (4h = 240m, also D, 1D)
  1W, 1M, 1Y         → 1w, 1mo, 1y
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from .envelope import error_response
from tradingagents.astock.quality import BlockedImportError

bp = Blueprint("tv", __name__)
logger = logging.getLogger(__name__)

from ._helpers import bounded_int_arg, df_to_json, get_store  # noqa: E402

RESOLUTION_MAP: dict[str, str] = {
    "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "60m",
    "240": "1d", "1440": "1d", "D": "1d", "1D": "1d", "1d": "1d",
    "1W": "1w", "W": "1w", "10080": "1w",
    "1M": "1mo", "M": "1mo", "43200": "1mo",
    "1Y": "1y", "Y": "1y", "12M": "1y", "525600": "1y",
}


def _router() -> Any:
    return current_app.config.get("DATA_FACADE")


def _tv_resolution(resolution: str) -> str:
    """Convert TradingView resolution to internal interval string."""
    return RESOLUTION_MAP.get(resolution, "1d")


# A-share code → exchange + board labels
_BOARD_MAP: dict[str, tuple[str, str]] = {
    # prefix: (exchange_label, board_label)
    "6":   ("沪", "主板"),
    "68":  ("沪", "科创板"),
    "00":  ("深", "主板"),
    "001": ("深", "主板"),
    "002": ("深", "中小板"),
    "003": ("深", "主板"),
    "30":  ("深", "创业板"),
    "4":   ("京", "北交所"),
    "8":   ("京", "北交所"),
    "92":  ("京", "北交所"),
}


def _stock_board(symbol: str) -> dict[str, str]:
    """Derive exchange & board labels from A-share stock code."""
    code = symbol.upper().split(".")[0]
    exchange_suffix = symbol.upper().split(".")[1] if "." in symbol else ""
    exchange_map = {"SH": "沪", "SZ": "深", "BJ": "京"}
    ex_label = exchange_map.get(exchange_suffix, exchange_suffix)
    board = "其他"
    for prefix, (_, board_label) in sorted(_BOARD_MAP.items(), key=lambda x: -len(x[0])):
        if code.startswith(prefix):
            board = board_label
            break
    return {"exchange": ex_label, "board": board, "code": code}


# TDX industry code → name (通达信行业分类)
_TDX_INDUSTRY: dict[int, str] = {
    1: "银行", 2: "保险", 3: "证券", 4: "多元金融",
    5: "房地产", 6: "建筑", 7: "建材", 8: "钢铁",
    9: "有色", 10: "煤炭", 11: "石油", 12: "化工",
    13: "化纤", 14: "塑料", 15: "橡胶", 16: "造纸",
    17: "农林牧渔", 18: "食品", 19: "纺织服饰", 20: "日用化工",
    21: "医药", 22: "商业连锁", 23: "酒店餐饮", 24: "旅游",
    25: "家电", 26: "汽车", 27: "机械", 28: "电气设备",
    29: "航天军工", 30: "船舶", 31: "运输设备", 32: "交通设施",
    33: "运输服务", 34: "仓储物流", 35: "半导体", 36: "元器件",
    37: "酿酒", 38: "软件服务", 39: "互联网", 40: "传媒娱乐",
    41: "通信设备", 42: "电信运营", 43: "电源设备", 44: "水务",
    45: "供气供热", 46: "环境保护", 47: "电力", 48: "商贸代理",
}  # fmt: skip

# Index constituent caches (lazy-loaded)
_index_constituents: dict[str, set[str]] = {}
_index_labels: dict[str, str] = {
    "000300": "沪深300", "000016": "上证50",
    "000905": "中证500", "399006": "创业板指",
}


def _code_to_astock(code: str) -> str:
    """Convert bare code like '600118' to '600118.SH'."""
    code = code.strip()
    if "." in code:
        return code.upper()
    if code.startswith("6") or code.startswith("9"):
        return code + ".SH"
    if code.startswith("0") or code.startswith("3") or code.startswith("2"):
        return code + ".SZ"
    return code + ".SH"


def _load_index_constituents() -> dict[str, set[str]]:
    """Lazy-load index constituent sets from akshare."""
    if _index_constituents:
        return _index_constituents
    try:
        import akshare as ak
        for idx_code, label in _index_labels.items():
            try:
                df = ak.index_stock_cons(symbol=idx_code)
                codes = {_code_to_astock(c) for c in df.iloc[:, 0].astype(str).tolist()}
                _index_constituents[idx_code] = codes
            except Exception as exc:
                logger.debug("Failed to fetch index constituent %s: %s", idx_code, exc)
    except Exception as exc:
        logger.debug("Failed to fetch index constituents from akshare: %s", exc)
    return _index_constituents


def _check_index_membership(symbol: str) -> list[str]:
    """Return labels of indices this stock belongs to."""
    constituents = _load_index_constituents()
    members = []
    for idx_code, codes in constituents.items():
        if symbol.upper() in codes:
            members.append(_index_labels.get(idx_code, idx_code))
    return members


def _aggregate_bars(daily_bars: list[dict[str, Any]], interval: str) -> list[dict[str, Any]]:
    """Aggregate daily bars into weekly, monthly, or yearly bars."""
    from datetime import datetime

    grouped: dict[str, dict[str, Any]] = {}
    for bar in daily_bars:
        td = bar.get("bar_time") or bar.get("trade_date") or bar.get("date") or ""
        if not td:
            continue
        dt = datetime.strptime(td[:10], "%Y-%m-%d")
        if interval == "1w":
            # ISO week: year + '-' + week number
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        elif interval == "1y":
            key = f"{dt.year}"
        else:
            # Monthly: year + '-' + month
            key = f"{dt.year}-{dt.month:02d}"

        if key not in grouped:
            grouped[key] = {
                "open": bar.get("open", 0),
                "high": bar.get("high", 0),
                "low": bar.get("low", 0),
                "close": bar.get("close", 0),
                "volume": float(bar.get("volume", 0)),
                "trade_date": td[:10],
            }
        else:
            g = grouped[key]
            g["high"] = max(g["high"], bar.get("high", 0))
            g["low"] = min(g["low"], bar.get("low", 0))
            g["close"] = bar.get("close", 0)
            g["volume"] = g["volume"] + float(bar.get("volume", 0))
            g["trade_date"] = td[:10]  # keep last date as the bar date

    return sorted(grouped.values(), key=lambda b: b["trade_date"])


# ── Stock list (lazy-loaded from mootdx) ──
_stock_list_cache: list[dict[str, str | tuple[str, str]]] | None = None
_stock_list_loaded = False


def _load_stock_list() -> list[dict[str, str | tuple[str, str]]]:
    global _stock_list_cache, _stock_list_loaded
    if _stock_list_loaded:
        return _stock_list_cache or []
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std")
        df = client.stocks()
        if df is not None and not df.empty:
            from pypinyin import lazy_pinyin, Style
            rows: list[dict[str, str | tuple[str, str]]] = []
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", "")).strip()
                if not code or not name or len(code) > 6:
                    continue
                symbol = _code_to_astock(code)
                nm = name.lower()
                py = "".join(lazy_pinyin(name, style=Style.NORMAL)).lower()
                init = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()
                rows.append({"code": code, "name": name, "symbol": symbol,
                             "pinyin": (py, init)})
            _stock_list_cache = rows
            _stock_list_loaded = True
    except Exception as exc:
        logger.debug("Failed to load stock list from mootdx: %s", exc)
    return _stock_list_cache or []


@bp.route("/tv/stock-search")
def tv_stock_search() -> tuple[Response, int]:
    """Search stocks by code, name, or pinyin."""
    q = request.args.get("q", "").strip().lower()
    if not q or len(q) < 1:
        return jsonify({"items": []}), 200
    try:
        limit = bounded_int_arg("limit", 10, minimum=1, maximum=50)
    except ValueError:
        return error_response("invalid_limit", 400)

    stocks = _load_stock_list()
    if not stocks:
        return jsonify({"items": []}), 200

    # Pinyin conversion for name search
    try:
        from pypinyin import lazy_pinyin, Style
        q_pinyin = "".join(lazy_pinyin(q, style=Style.NORMAL)).lower()
        q_initials = "".join(lazy_pinyin(q, style=Style.FIRST_LETTER)).lower()
    except Exception as exc:
        logger.debug("Failed to convert pinyin for search: %s", exc)
        q_pinyin = ""
        q_initials = ""

    scored: list[tuple[int, dict]] = []
    seen_symbols: set[str] = set()

    for s in stocks:
        sym = s["symbol"]
        if sym in seen_symbols:
            continue
        code = s["code"]
        name = s["name"]
        score = 0

        # Exact code match
        if code == q:
            score = 100
        elif code.startswith(q):
            score = 80
        # Name exact or prefix
        elif name.lower() == q:
            score = 90
        elif name.lower().startswith(q):
            score = 70
        elif q in name.lower():
            score = 50
        # Pinyin full match
        elif q_pinyin:
            py, init = s["pinyin"]  # pre-computed in _load_stock_list
            if py == q_pinyin:
                score = 85
            elif py.startswith(q_pinyin):
                score = 65
            elif q_pinyin in py:
                score = 45
            elif init == q_initials:
                score = 60
            elif init.startswith(q_initials):
                score = 40
            elif q_initials in init:
                score = 20

        if score >= 20:
            board_info = _stock_board(sym)
            scored.append((score, {
                "symbol": sym,
                "code": code,
                "name": name,
                "exchange": board_info["exchange"],
                "board": board_info["board"],
            }))
            seen_symbols.add(sym)

    scored.sort(key=lambda x: -x[0])
    items = [item for _, item in scored[:limit]]
    return jsonify({"items": items}), 200


@bp.route("/tv/stock-info")
def tv_stock_info() -> tuple[Response, int]:
    """Return A-share stock info: name, exchange, board."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol required", 400)
    info = _stock_board(symbol)
    router = _router()
    name = ""
    industry = ""
    if router is not None:
        try:
            resp = router.get_valuation(symbol, source="tencent")
            if resp.status == "ok" and resp.data:
                name = resp.data.get("name", "")
        except Exception as exc:
            logger.debug("Failed to fetch valuation from router: %s", exc)
        try:
            from tradingagents.astock.data_sources.adapters import build_default_adapters
            adapters = build_default_adapters()
            mootdx_adapter = adapters.get("mootdx")
            if mootdx_adapter:
                from tradingagents.astock.data_sources.schema import AStockRequest
                req = AStockRequest(raw_symbol=symbol, symbol=symbol, capability="f10")
                resp2 = mootdx_adapter.get_f10(req)
                if resp2:
                    ind_code = resp2.get("industry")
                    if isinstance(ind_code, int) and ind_code in _TDX_INDUSTRY:
                        industry = _TDX_INDUSTRY[ind_code]
        except Exception as exc:
            logger.debug("Failed to fetch industry from mootdx adapter: %s", exc)
    info["name"] = name
    info["industry"] = industry
    info["indices"] = _check_index_membership(symbol)
    info["symbol"] = symbol
    # Listing date via baostock
    info["listing_date"] = _listing_date(symbol)
    return jsonify(info), 200


def _listing_date(symbol: str) -> str:
    """Return stock listing date (YYYY-MM-DD) or empty string."""
    try:
        import baostock as bs
        bs.login()
        try:
            clean = symbol.replace(".SH", ".sh").replace(".SZ", ".sz")
            rs = bs.query_stock_basic(code=clean)
            while rs.next():
                row = rs.get_row_data()
                if len(row) > 2 and row[2]:
                    return row[2]
            return ""
        finally:
            bs.logout()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# GET /api/v1/tv/symbols
# ---------------------------------------------------------------------------


@bp.route("/tv/symbols")
def tv_symbols() -> tuple[Response, int]:
    """Return TradingView symbol info for a given symbol."""
    symbol = request.args.get("symbol", "")
    if not symbol:
        return error_response("symbol is required", 400)

    try:
        store = get_store()
        df = store.query_kline(symbol, interval="1d", limit=2)
        bars = df_to_json(df)
        # bars may use 'bar_time' or 'trade_date' as time column
        last_price = bars[-1]["close"] if bars else 100.0
        prev_close = bars[-2]["close"] if len(bars) > 1 else last_price
    except Exception as exc:
        logger.debug("Failed to get market summary for %s: %s", symbol, exc)
        last_price = 100.0
        prev_close = 100.0

    parts = symbol.upper().split(".")
    ticker = parts[0]
    exchange = parts[1] if len(parts) > 1 else "SSE"

    return jsonify({
        "symbol": symbol,
        "ticker": ticker,
        "name": symbol,
        "full_name": f"{exchange}:{ticker}",
        "description": f"{symbol} - A-Share Stock",
        "exchange": exchange,
        "type": "stock",
        "session": "0930-1130,1300-1500",
        "timezone": "Asia/Shanghai",
        "minmov": 1,
        "pricescale": 100,
        "minmove2": 0,
        "fractional": False,
        "has_intraday": True,
        "has_daily": True,
        "has_weekly_and_monthly": True,
        "supported_resolutions": [
            "1", "5", "15", "30", "60", "240", "D", "W", "M"
        ],
        "intraday_multipliers": ["1", "5", "15", "30", "60"],
        "volume_precision": 0,
        "data_status": "streaming",
        "prices": [],
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/tv/history
# ---------------------------------------------------------------------------


@bp.route("/tv/history")
def tv_history() -> tuple[Response, int]:
    """Return OHLCV bars for TradingView.

    Query params:
        symbol  (str)    — e.g. 600519.SH
        resolution (str) — e.g. 5 (minutes), D (daily)
        from    (int)    — UTC timestamp (seconds)
        to      (int)    — UTC timestamp (seconds)
    """
    symbol = request.args.get("symbol", "")
    resolution = request.args.get("resolution", "D")
    from_ts = request.args.get("from", type=int)
    to_ts = request.args.get("to", type=int)

    if not symbol:
        return jsonify({"s": "error", "errmsg": "symbol required"}), 400

    interval = _tv_resolution(resolution)
    include_cold = request.args.get("include_cold", "0").lower() in ("1", "true", "yes")
    # Bound response work before converting a potentially huge local range to
    # JSON.  TradingView will request adjacent ranges as the user pans.
    max_bars = min(max(request.args.get("countback", 2000, type=int) or 2000, 1), 5000)

    try:
        store = get_store()
        start_str = __import__("datetime").datetime.utcfromtimestamp(from_ts).strftime("%Y-%m-%d") if from_ts else None  # noqa: E501
        end_str = __import__("datetime").datetime.utcfromtimestamp(to_ts).strftime("%Y-%m-%d") if to_ts else None
        # Reuse the market-data local-first path: hot store then permanent
        # local warehouse.  Keeping this logic in one place prevents the
        # chart endpoint from drifting into an unnecessary provider request.
        from .routes_data_query import _query_local_kline
        df, _local_source = _query_local_kline(
            store, symbol, start=start_str, end=end_str, interval=interval,
            limit=max_bars, include_cold=include_cold,
        )
        bars = df_to_json(df)

        # Weekly/Monthly/Yearly: aggregate from daily data
        if not bars and interval in ("1w", "1mo", "1y"):
            df_daily, _daily_source = _query_local_kline(
                store, symbol, start=start_str, end=end_str, interval="1d",
                limit=max_bars, include_cold=include_cold,
            )
            daily_bars = df_to_json(df_daily)
            if daily_bars:
                bars = _aggregate_bars(daily_bars, interval)
        if not bars:
            router = _router()
            if router is not None:
                try:
                    resp = router.get_kline(symbol, interval=interval, source="mootdx", limit=400)
                    if resp.status == "ok" and resp.data:
                        from tradingagents.astock.store.loader import KlineLoader
                        from tradingagents.astock.store.permanent_kline import get_permanent_kline_store

                        permanent = (
                            get_permanent_kline_store(current_app.config.get("ASTOCK_PERMANENT_KLINE_DB_PATH", "kline/kline.duckdb"))
                            if current_app.config.get("ASTOCK_PERMANENT_KLINE_ENABLED", True) else None
                        )
                        KlineLoader(store, router, permanent_store=permanent).write_response(
                            symbol, resp, interval=interval, source=resp.source or "mootdx"
                        )
                        df, _local_source = _query_local_kline(
                            store, symbol, start=start_str, end=end_str, interval=interval,
                            limit=max_bars, include_cold=include_cold,
                        )
                        bars = df_to_json(df)
                except (ValueError, BlockedImportError) as exc:
                    logger.warning("TV provider returned malformed K-line data for %s: %s", symbol, exc)
                    return jsonify({"s": "error", "errmsg": "invalid_kline_data"}), 422
                except Exception:
                    logger.warning("TV intraday fetch failed for %s", symbol, exc_info=True)

        if not bars:
            return jsonify({"s": "no_data", "nextTime": int(to_ts or 0)}), 200

        # Build TV OHLCV arrays
        times: list[int] = []
        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        volumes: list[float] = []

        for b in bars:
            # Try multiple time column names: bar_time (primary), trade_date, date
            td = b.get("bar_time") or b.get("trade_date") or b.get("date") or ""
            if not td:
                continue
            if len(td) <= 10:
                dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d")
                ts = int(dt.timestamp())
            else:
                try:
                    dt = __import__("datetime").datetime.strptime(td, "%Y-%m-%d %H:%M")
                    ts = int(dt.timestamp())
                except ValueError:
                    continue

            if from_ts and ts < from_ts:
                continue
            if to_ts and ts > to_ts:
                continue

            times.append(ts)
            opens.append(float(b.get("open", 0)))
            highs.append(float(b.get("high", 0)))
            lows.append(float(b.get("low", 0)))
            closes.append(float(b.get("close", 0)))
            volumes.append(float(b.get("volume", 0)))

        if not times:
            return jsonify({"s": "no_data", "nextTime": int(to_ts or 0)}), 200

        times, opens, highs, lows, closes, volumes = zip(
            *sorted(zip(times, opens, highs, lows, closes, volumes))
        )

        return jsonify({
            "s": "ok",
            "t": list(times),
            "o": list(opens),
            "h": list(highs),
            "l": list(lows),
            "c": list(closes),
            "v": list(volumes),
        }), 200

    except Exception as exc:
        logger.error("TV history error: %s", exc)
        return jsonify({"s": "error", "errmsg": str(exc)}), 500

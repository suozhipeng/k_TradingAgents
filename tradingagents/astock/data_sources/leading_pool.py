"""动态龙头股池管理 — 基于行业板块领涨股自动获取.

核心逻辑:
1. 从东方财富行业板块接口获取各板块排行数据
2. 每个板块提取领涨龙头 (leader / leader_change)
3. 通过内置映射表或 AkShare 解析股票代码
4. 获取最近交易日实时估值数据 (价格、涨跌幅、换手率、市值、PB)
5. 缓存结果，支持手动刷新

数据源: 东方财富 push2 API → AkShare 兜底

内置常用龙头股代码映射表 (名称 → 标准符号):
    覆盖 A 股主要赛道的知名龙头企业.
"""

from __future__ import annotations

import logging
from datetime import datetime, date as date_type
from typing import Any

from tradingagents.astock.data_sources.calendar import prev_trading_day, is_trading_day
from tradingagents.astock.data_sources.eastmoney import industry_comparison as em_industry_comparison
from tradingagents.astock.data_sources.router import AStockDataFacade

logger = logging.getLogger(__name__)

_router = AStockDataFacade()

# ── 内置龙头股名称到代码的映射表 ─────────────────────────────────────

_LEADER_CODE_MAP: dict[str, str] = {
    # 新能源
    "宁德时代": "300750.SZ",
    "比亚迪": "002594.SZ",
    "赛力斯": "601127.SH",
    "亿纬锂能": "300014.SZ",
    "阳光电源": "300274.SZ",
    # 科技
    "中芯国际": "688981.SH",
    "寒武纪": "688256.SH",
    "工业富联": "601138.SH",
    "新易盛": "300502.SZ",
    "中际旭创": "300308.SZ",
    "胜宏科技": "300476.SZ",
    "天孚通信": "300394.SZ",
    "海光信息": "688041.SH",
    "科大讯飞": "002230.SZ",
    "紫光股份": "000938.SZ",
    "沪电股份": "002463.SZ",
    # 消费
    "贵州茅台": "600519.SH",
    "五粮液": "000858.SZ",
    "泸州老窖": "000568.SZ",
    "山西汾酒": "600809.SH",
    "美的集团": "000333.SZ",
    "海尔智家": "600690.SH",
    # 医药
    "药明康德": "603259.SH",
    "恒瑞医药": "600276.SH",
    "片仔癀": "600436.SH",
    "云南白药": "000538.SZ",
    "迈瑞医疗": "300760.SZ",
    # 金融
    "建设银行": "601939.SH",
    "工商银行": "601398.SH",
    "招商银行": "600036.SH",
    "中国平安": "601318.SH",
    "新华保险": "601336.SH",
    "中国人保": "601319.SH",
    "农业银行": "601288.SH",
    # 有色
    "紫金矿业": "601899.SH",
    "北方稀土": "600111.SH",
    "赣锋锂业": "002460.SZ",
    "天齐锂业": "002466.SZ",
    "洛阳钼业": "603993.SH",
    "中国铝业": "601600.SH",
    # 军工
    "中航西飞": "000768.SZ",
    "航发动力": "600893.SH",
    "中航沈飞": "600760.SH",
    "中国船舶": "600150.SH",
    # 其他
    "隆基绿能": "601012.SH",
    "通威股份": "600438.SH",
    "天赐材料": "002709.SZ",
    "恩捷股份": "002812.SZ",
    "中信证券": "600030.SH",
    "立讯精密": "002475.SZ",
    "海康威视": "002415.SZ",
}

# ── 缓存 ──────────────────────────────────────────────────────────────

_leading_pool_cache: list[dict[str, Any]] | None = None
_pool_trade_date: str = ""
_pool_source: str = "none"


def _resolve_latest_trade_date() -> str:
    """获取最近一个交易日日期字符串 (YYYY-MM-DD)."""
    today = date_type.today()
    if is_trading_day(today):
        return today.isoformat()
    prev = prev_trading_day(today)
    return prev.isoformat()


def _resolve_leader_code_by_name(name: str) -> str:
    """根据龙头股名称解析股票代码.

    优先级:
    1. 内置映射表精确匹配
    2. 内置映射表模糊匹配 (名称包含)
    3. AkShare 全量 A 股列表匹配 (备用)

    Returns:
        标准符号格式如 "600519.SH"，失败返回空字符串
    """
    if not name:
        return ""

    name = name.strip()

    # 1. 精确匹配内置映射表
    if name in _LEADER_CODE_MAP:
        return _LEADER_CODE_MAP[name]

    # 2. 模糊匹配 (名称包含，优先长匹配)
    best_match = None
    best_len = 0
    for mapped_name, code in _LEADER_CODE_MAP.items():
        if name in mapped_name or mapped_name in name:
            if len(mapped_name) > best_len:
                best_match = code
                best_len = len(mapped_name)
    if best_match:
        return best_match

    # 3. 备用: 通过 AkShare 查找
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty and "名称" in df.columns and "代码" in df.columns:
            # 精确匹配
            match = df[df["名称"] == name]
            if not match.empty:
                return _parse_symbol(str(match.iloc[0]["代码"]))
            # 模糊匹配
            matches = df[df["名称"].str.contains(name, na=False)]
            if not matches.empty:
                return _parse_symbol(str(matches.iloc[0]["代码"]))
    except Exception as e:
        logger.debug(f"AkShare lookup failed for {name}: {e}")

    return ""


def _parse_symbol(code: str) -> str:
    """将东财6位代码转换为标准符号格式 (如 600519.SH).

    东财代码规则:
    - 6开头 → SH (上海)
    - 0/3开头 → SZ (深圳)
    - 8/4开头 → BJ (北京)
    """
    if not code or len(code) != 6:
        return ""
    if code.startswith("6"):
        return f"{code}.SH"
    elif code.startswith(("0", "3")):
        return f"{code}.SZ"
    elif code.startswith(("8", "4")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _fetch_leaders_from_industry(top_n: int = 30) -> list[dict[str, Any]]:
    """从东财行业板块数据中提取各板块领涨龙头.

    Returns:
        list of dicts with keys: name, sector, change_pct, leader_change
    """
    try:
        data = em_industry_comparison(top_n=top_n)
        sectors = data.get("top", [])
        if not sectors:
            return []

        leaders = []
        seen_names = set()

        for sec in sectors:
            leader_name = sec.get("leader", "").strip()
            leader_change = sec.get("leader_change", 0)
            sector_name = sec.get("name", "")
            change_pct = sec.get("change_pct", 0)

            if not leader_name or leader_name in seen_names:
                continue
            
            seen_names.add(leader_name)

            leaders.append({
                "name": leader_name,
                "sector": sector_name,
                "leader_change": float(leader_change) if leader_change else 0,
                "sector_change": float(change_pct) if change_pct else 0,
                "symbol": "",  # 待解析
                "rank": sec.get("rank", 0),
            })

        return leaders
    except Exception as exc:
        logger.warning(f"Failed to fetch leaders from industry: {exc}")
        return []


def _resolve_leader_codes(leaders: list[dict]) -> list[dict]:
    """为龙头股解析股票代码."""
    for leader in leaders:
        name = leader.get("name", "")
        if name:
            code = _resolve_leader_code_by_name(name)
            leader["symbol"] = code
    
    return leaders


def _fetch_valuation_data(stocks: list[dict]) -> list[dict]:
    """为有代码的龙头股获取实时估值数据."""
    for stock in stocks:
        symbol = stock.get("symbol", "")
        if not symbol:
            continue
        
        try:
            resp = _router.get_valuation(symbol)
            if resp.status == "ok" and resp.data and isinstance(resp.data, dict):
                stock["price"] = resp.data.get("price", 0)
                stock["turnover_rate"] = resp.data.get("turnover_rate", 0)
                stock["market_cap"] = resp.data.get("market_cap", 0)
                stock["pb"] = resp.data.get("pb", 0)
                stock["pe"] = resp.data.get("pe", 0)
            else:
                stock["price"] = 0
                stock["turnover_rate"] = 0
                stock["market_cap"] = 0
                stock["pb"] = 0
                stock["pe"] = 0
        except Exception:
            stock["price"] = 0
            stock["turnover_rate"] = 0
            stock["market_cap"] = 0
            stock["pb"] = 0
            stock["pe"] = 0
    
    return stocks


def get_dynamic_leading_pool(top_n: int = 30) -> tuple[list[dict[str, Any]], str]:
    """获取动态龙头股池.

    从东财行业板块数据中提取各板块领涨股，并附加最近交易日估值数据.

    Parameters
    ----------
    top_n : int
        获取排名前 N 的行业板块的领涨股

    Returns
    -------
    tuple[list[dict], str]
        - list: 龙头股列表，每项包含 symbol, name, sector, price, change_pct 等
        - str: 数据来源 ("eastmoney" / "akshare" / "default")
    """
    global _leading_pool_cache, _pool_trade_date, _pool_source

    # 检查缓存是否有效 (同一天)
    today = _resolve_latest_trade_date()
    if _leading_pool_cache and _pool_trade_date == today:
        return _leading_pool_cache, _pool_source

    # 从东财获取行业领涨股
    leaders = _fetch_leaders_from_industry(top_n=top_n)

    if not leaders:
        # 回退到默认硬编码池 (避免循环导入)
        default_stocks = [
            {"symbol": "600111.SH", "name": "北方稀土", "sector": "有色"},
            {"symbol": "002460.SZ", "name": "赣锋锂业", "sector": "有色"},
            {"symbol": "601899.SH", "name": "紫金矿业", "sector": "有色"},
            {"symbol": "600988.SH", "name": "赤峰黄金", "sector": "有色"},
            {"symbol": "002230.SZ", "name": "科大讯飞", "sector": "科技"},
            {"symbol": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
            {"symbol": "002594.SZ", "name": "比亚迪", "sector": "新能源"},
            {"symbol": "603259.SH", "name": "药明康德", "sector": "医药"},
            {"symbol": "601939.SH", "name": "建设银行", "sector": "金融"},
            {"symbol": "688256.SH", "name": "寒武纪", "sector": "科技"},
            {"symbol": "601606.SH", "name": "长城军工", "sector": "军工"},
            {"symbol": "688981.SH", "name": "中芯国际", "sector": "科技"},
            {"symbol": "300502.SZ", "name": "新易盛", "sector": "科技"},
            {"symbol": "601138.SH", "name": "工业富联", "sector": "科技"},
            {"symbol": "300308.SZ", "name": "中际旭创", "sector": "科技"},
            {"symbol": "300476.SZ", "name": "胜宏科技", "sector": "科技"},
            {"symbol": "300394.SZ", "name": "天孚通信", "sector": "科技"},
            {"symbol": "688041.SH", "name": "海光信息", "sector": "科技"},
            {"symbol": "601336.SH", "name": "新华保险", "sector": "金融"},
            {"symbol": "600519.SH", "name": "贵州茅台", "sector": "消费"},
            {"symbol": "601288.SH", "name": "农业银行", "sector": "金融"},
            {"symbol": "601319.SH", "name": "中国人保", "sector": "金融"},
        ]
        _leading_pool_cache = default_stocks
        _pool_trade_date = today
        _pool_source = "default"
        return default_stocks, "default"

    # 解析股票代码
    leaders = _resolve_leader_codes(leaders)
    
    # 获取估值数据
    leaders = _fetch_valuation_data(leaders)

    _leading_pool_cache = leaders
    _pool_trade_date = today
    _pool_source = "eastmoney"

    return leaders, "eastmoney"


def refresh_leading_pool() -> tuple[list[dict[str, Any]], str]:
    """强制刷新龙头股池，清除缓存重新获取."""
    global _leading_pool_cache
    _leading_pool_cache = None
    return get_dynamic_leading_pool()


def get_leading_pool_summary() -> dict[str, Any]:
    """获取龙头股池摘要信息 (用于快速查看).

    Returns:
        dict with keys: trade_date, source, count, sectors, leaders
    """
    leaders, source = get_dynamic_leading_pool()

    # 按板块分组
    sectors: dict[str, list] = {}
    for leader in leaders:
        sector = leader.get("sector", "其他")
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append({
            "name": leader.get("name", ""),
            "symbol": leader.get("symbol", ""),
            "change_pct": leader.get("leader_change", 0),
            "price": leader.get("price", 0),
            "market_cap": leader.get("market_cap", 0),
        })

    return {
        "trade_date": _pool_trade_date,
        "source": source,
        "count": len(leaders),
        "sectors": {k: v for k, v in sorted(sectors.items(), key=lambda x: -len(x[1]))},
        "leaders": leaders[:20],  # 前20只
    }

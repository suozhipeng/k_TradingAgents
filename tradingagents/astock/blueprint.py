"""A-share requirements blueprint derived from the provided image set.

The screenshots describe an A-stock assistant with five layers:
market, research, news, fundamentals, and announcements. The same material
also splits the system into three delivery phases:
backtesting, simulated trading, and QMT-linked live trading.

This module turns that presentation into structured data so the project can
consume it as a machine-readable capability catalog instead of only a slide
deck.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .verification_provenance import load_verification_provenance


@dataclass(frozen=True)
class AStockCapability:
    """One concrete A-share capability exposed by the blueprint."""

    layer: str
    name: str
    source_candidates: tuple[str, ...]
    access_mode: str
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AStockLayer:
    """A user-facing layer in the A-share stack."""

    name: str
    summary: str
    capabilities: tuple[AStockCapability, ...]


@dataclass(frozen=True)
class AStockPhase:
    """A rollout phase shown in the slide deck."""

    name: str
    objective: str
    highlights: tuple[str, ...]


@dataclass(frozen=True)
class AStockBlueprint:
    """The full A-share capability blueprint."""

    title: str
    subtitle: str
    disclaimer: str
    tech_stack: tuple[str, ...]
    layers: tuple[AStockLayer, ...]
    phases: tuple[AStockPhase, ...]

    def capability_count(self) -> int:
        return sum(len(layer.capabilities) for layer in self.layers)

    def payload(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "disclaimer": self.disclaimer,
            "tech_stack": list(self.tech_stack),
            "capability_count": self.capability_count(),
            "data_entrypoint": {
                "package": "tradingagents.astock.data_sources",
                "class": "AStockDataFacade",
                "router": "AStockDataRouter",
                "scope": "read-only data acquisition layer; no order placement or execution",
                "upper_layer_bridge": {
                    "package": "tradingagents.astock.interface",
                    "class": "AStockInterface",
                    "tools_package": "tradingagents.astock.tools",
                    "analyst_class": "tradingagents.astock.analyst.AStockAnalyst",
                    "implemented": ["market", "news", "fundamentals", "announcements", "research"],
                    "display_integrations": [
                        "CLI",
                        "Streamlit read-only UI",
                        "legacy multi-market dispatcher",
                        "Trader / Risk / Portfolio Manager advisory chain",
                        "runtime profile isolation (deterministic_verification / live_research)",
                        "BacktestEngine / PaperTrader",
                        "QMT bridge controlled execution (safety mode)",
                    ],
                    "todo": [],
                },
                "provider_status": {
                    "akshare": {
                        "implemented": ["daily_kline", "valuation", "stock_news", "research_list", "quarterly_financials"],
                        "live_verified": ["daily_kline", "valuation", "stock_news", "research_list", "quarterly_financials"],
                        "live_verification": load_verification_provenance("akshare").to_dict(),
                        "fixture_verified": ["daily_kline", "valuation", "stock_news", "research_list", "quarterly_financials"],
                        "optional_dependency": "akshare",
                        "requires_credentials": False,
                        "notes": ["Tencent valuation supplement is disabled by default; enable with allow_tencent_valuation_supplement=True or ASTOCK_AKSHARE_ALLOW_TENCENT_SUPPLEMENT=1."],
                    },
                    "tencent": {
                        "implemented": ["snapshot", "order_book", "trade_tape", "turnover_rate"],
                        "live_verified": ["snapshot", "order_book", "trade_tape", "turnover_rate"],
                        "live_verification": load_verification_provenance("tencent").to_dict(),
                        "fixture_verified": ["snapshot", "order_book", "trade_tape", "turnover_rate"],
                        "optional_dependency": "requests",
                        "requires_credentials": False,
                    },
                    "cninfo": {
                        "implemented": ["announcement_summary", "announcement_full"],
                        "live_verified": ["announcement_summary", "announcement_full"],
                        "live_verification": load_verification_provenance("cninfo").to_dict(),
                        "fixture_verified": ["announcement_summary", "announcement_full"],
                        "optional_dependency": "requests",
                        "requires_credentials": False,
                    },
                    "mootdx": {
                        "implemented": ["daily_kline", "order_book", "trade_tape", "f10"],
                        "live_verified": ["daily_kline", "order_book", "trade_tape", "f10"],
                        "live_verification": load_verification_provenance("mootdx").to_dict(),
                        "fixture_verified": ["daily_kline", "order_book", "trade_tape", "f10"],
                        "optional_dependency": "mootdx",
                        "requires_credentials": False,
                        "notes": ["Live verification requires a reachable TDX quote server; configure ASTOCK_MOOTDX_HOST/PORT/MARKET if auto discovery fails."],
                    },
                    "iwencai": {
                        "implemented": ["nl_search", "institution_expectation"],
                        "live_verified": [],
                        "live_verification": load_verification_provenance("iwencai").to_dict(),
                        "fixture_verified": ["nl_search", "institution_expectation"],
                        "optional_dependency": "pywencai",
                        "requires_credentials": True,
                        "notes": ["Live verification requires ASTOCK_IWENCAI_COOKIE; credentials are never logged or stored in fixtures."],
                    },
                    "qmt": {
                        "implemented": ["read_only_placeholder"],
                        "live_verified": [],
                        "live_verification": load_verification_provenance("qmt").to_dict(),
                        "fixture_verified": [],
                        "optional_dependency": "QMT local client",
                        "requires_credentials": True,
                        "notes": ["No order placement or execution logic is implemented in this data-source phase."],
                    },
                },
                "implemented": [
                    "five-layer callable interface mapping",
                    "symbol normalization",
                    "source routing and fallback",
                    "history/snapshot/summary cache buckets",
                    "normalized ok/empty/error responses",
                    "real read-only adapters for akshare, Tencent Finance, and cninfo",
                    "optional live bridges for mootdx and iwencai with env-driven configuration",
                    "fixture-based provider parser tests and opt-in live integration tests",
                    "formal AStockGraphRuntime entry for the minimal A-share research bridge",
                ],
                "adapter_status": {
                    "mootdx": "✅ verified — mootdx 0.11.7 installed, TDX connectivity confirmed (2026-06-19), live kline/quotes work for sh.600519",
                    "iwencai": "⚠️ pywencai 0.13.1 installed, but ASTOCK_IWENCAI_COOKIE not set — run 'hermes skills' or see docs/ASTOCK_LIVE_RESEARCH_SETUP.md for cookie setup instructions",
                },
                "todo": [
                    "TODO: keep QMT read-only bridge separate from any future execution adapter",
                ],
            },
            "layers": [
                {
                    "name": layer.name,
                    "summary": layer.summary,
                    "capabilities": [asdict(cap) for cap in layer.capabilities],
                }
                for layer in self.layers
            ],
            "phases": [asdict(phase) for phase in self.phases],
        }


ASTOCK_BLUEPRINT = AStockBlueprint(
    title="TradingAgents-Astock",
    subtitle="A股辅助看盘系统蓝图",
    disclaimer="本内容仅用于辅助看盘、研究与工程实现，不构成任何投资建议或交易承诺。",
    tech_stack=(
        "VS Code + GitHub Copilot",
        "Claude Code",
        "DeepSeek V4 Pro",
        "Python 3.12",
        "Jinja2 / 原生 JS",
        "Backtrader",
        "Flask",
        "Matplotlib / Chart.js",
        "pandas / numpy",
        "python-pptx",
        "WSGI Flask 内置服务器",
    ),
    layers=(
        AStockLayer(
            name="行情层",
            summary="用于盘面、盘口与估值观察的第一层行情输入。",
            capabilities=(
                AStockCapability(
                    layer="行情层",
                    name="K线",
                    source_candidates=("mootdx", "腾讯财经", "akshare"),
                    access_mode="pip install / HTTP GET / Python 调用",
                    notes=("覆盖日线、分钟线等常用 K 线观察需求",),
                ),
                AStockCapability(
                    layer="行情层",
                    name="五档盘口",
                    source_candidates=("mootdx", "腾讯财经"),
                    access_mode="TCP 协议 / HTTP GET",
                    notes=("适合盘中快速观察委托簿",),
                ),
                AStockCapability(
                    layer="行情层",
                    name="逐笔成交",
                    source_candidates=("mootdx", "腾讯财经"),
                    access_mode="TCP 协议 / HTTP GET",
                    notes=("用于识别大单、扫单与盘口博弈",),
                ),
                AStockCapability(
                    layer="行情层",
                    name="PE / PB",
                    source_candidates=("akshare", "mootdx"),
                    access_mode="Python 调用",
                    notes=("估值类指标，便于横向比较",),
                ),
                AStockCapability(
                    layer="行情层",
                    name="市值",
                    source_candidates=("akshare", "mootdx"),
                    access_mode="Python 调用",
                    notes=("用于区分大盘股、中盘股与题材股",),
                ),
                AStockCapability(
                    layer="行情层",
                    name="换手率",
                    source_candidates=("akshare", "腾讯财经", "mootdx"),
                    access_mode="HTTP GET / Python 调用",
                    notes=("观察流动性与筹码活跃度",),
                ),
            ),
        ),
        AStockLayer(
            name="研报层",
            summary="聚焦机构研报、研报摘要与语义搜索。",
            capabilities=(
                AStockCapability(
                    layer="研报层",
                    name="研报列表",
                    source_candidates=("东方财富", "akshare"),
                    access_mode="HTTP GET / Python 调用",
                    notes=("用于发现最新机构观点",),
                ),
                AStockCapability(
                    layer="研报层",
                    name="PDF 下载",
                    source_candidates=("东方财富", "akshare"),
                    access_mode="HTTP GET",
                    notes=("便于离线阅读与归档",),
                ),
                AStockCapability(
                    layer="研报层",
                    name="机构预期",
                    source_candidates=("iwencai", "tushare", "akshare"),
                    access_mode="REST API / Python 调用",
                    notes=("适合做一致预期与盈利预期跟踪",),
                ),
                AStockCapability(
                    layer="研报层",
                    name="NL 语义搜索",
                    source_candidates=("iwencai",),
                    access_mode="REST API",
                    notes=("适合自然语言检索研究主题与标的",),
                ),
            ),
        ),
        AStockLayer(
            name="新闻层",
            summary="覆盖个股新闻、快讯和宏观外部资讯。",
            capabilities=(
                AStockCapability(
                    layer="新闻层",
                    name="个股新闻",
                    source_candidates=("akshare", "腾讯财经"),
                    access_mode="HTTP GET",
                    notes=("适合事件驱动的题材追踪",),
                ),
                AStockCapability(
                    layer="新闻层",
                    name="财联社快讯",
                    source_candidates=("akshare", "财联社公开源"),
                    access_mode="HTTP GET",
                    notes=("适合盘中快讯与题材异动",),
                ),
                AStockCapability(
                    layer="新闻层",
                    name="全球资讯",
                    source_candidates=("akshare", "外部宏观源"),
                    access_mode="HTTP GET",
                    notes=("用于宏观与海外市场联动观察",),
                ),
            ),
        ),
        AStockLayer(
            name="基础数据",
            summary="覆盖财务报表、F10 和基本面信息。",
            capabilities=(
                AStockCapability(
                    layer="基础数据",
                    name="季报 37 字段",
                    source_candidates=("akshare", "tushare"),
                    access_mode="Python 调用",
                    notes=("用于财务趋势、盈利质量和资产负债分析",),
                ),
                AStockCapability(
                    layer="基础数据",
                    name="F10 九大类",
                    source_candidates=("mootdx", "akshare"),
                    access_mode="Python 调用",
                    notes=("便于快速查看公司概览、股东、财务与行业信息",),
                ),
                AStockCapability(
                    layer="基础数据",
                    name="基本面",
                    source_candidates=("tushare", "akshare"),
                    access_mode="Python 调用",
                    notes=("用于形成长期和中期的基本面画像",),
                ),
            ),
        ),
        AStockLayer(
            name="公告层",
            summary="覆盖公告全文与摘要，适合盘后复盘与风险提示。",
            capabilities=(
                AStockCapability(
                    layer="公告层",
                    name="公告全文",
                    source_candidates=("巨潮资讯", "mootdx"),
                    access_mode="HTTP GET",
                    notes=("适合查看原始公告、异动说明与重大事项",),
                ),
                AStockCapability(
                    layer="公告层",
                    name="最新摘要",
                    source_candidates=("巨潮资讯", "mootdx"),
                    access_mode="HTTP GET",
                    notes=("用于快速提炼公告核心风险点",),
                ),
            ),
        ),
    ),
    phases=(
        AStockPhase(
            name="回测验证",
            objective="先验证选股、策略打分与风控是否在历史数据上成立。",
            highlights=(
                "2023.01 -> 2026.05",
                "Backtrader 周期调仓",
                "避免行情匹配但策略亏钱",
                "完整费用率与滑点模拟",
            ),
        ),
        AStockPhase(
            name="模拟盘试跑",
            objective="在真实盘面下验证调度、虚拟成交和实时告警。",
            highlights=(
                "2026 年 5 月起运行",
                "完整交易引擎",
                "调度器定时调仓",
                "SSE 流式实时进度",
            ),
        ),
        AStockPhase(
            name="实盘出击",
            objective="通过 QMT 桥接到真实交易，但默认保持人工确认。",
            highlights=(
                "安全模式默认开启",
                "人工确认后下单",
                "QMT 桥接执行",
                "ATR 动态止损 + 跟踪止盈",
            ),
        ),
    ),
)


def build_blueprint_payload() -> dict:
    """Return the blueprint as a JSON-serializable dictionary."""
    return ASTOCK_BLUEPRINT.payload()


def build_blueprint_markdown() -> str:
    """Render the A-stock blueprint as Markdown for CLI or docs output."""
    payload = build_blueprint_payload()
    lines = [
        f"# {payload['title']}",
        "",
        payload["subtitle"],
        "",
        f"## 能力覆盖",
        f"- {payload['capability_count']} 个能力点覆盖",
        "- 截图里提到的 13 个接口，这里按五层能力展开为可实现的 18 个能力点，便于拆分开发与落地。",
        "",
        f"## 免责声明",
        f"- {payload['disclaimer']}",
        "",
        "## 研发栈",
    ]
    lines.extend(f"- {item}" for item in payload["tech_stack"])
    lines.append("")
    lines.append("## 五层能力")
    for layer in payload["layers"]:
        lines.append(f"### {layer['name']}")
        lines.append(f"- {layer['summary']}")
        for cap in layer["capabilities"]:
            sources = " / ".join(cap["source_candidates"])
            lines.append(f"  - {cap['name']}: {sources} ({cap['access_mode']})")
    lines.append("")
    lines.append("## 已实现 / 待实现边界")
    lines.append("- 已实现：`tradingagents.astock.data_sources` 提供统一 A 股数据访问层，包含 schema / cache / router / facade / adapters 分层。")
    lines.append("- 已实现：五层能力入口已统一到可调用方法与稳定返回结构；路由支持主源 / 备源 / 淘汰源语义与无数据语义。")
    lines.append("- 待实现：QMT 实盘桥接、下单执行、页面联动与更完整的真实供应商 SDK 对接。")
    lines.append("")
    entrypoint = payload["data_entrypoint"]
    lines.append("## 统一数据入口")
    lines.append(f"- 入口：`{entrypoint['package']}.{entrypoint['class']}` / `{entrypoint['router']}`")
    lines.append(f"- 边界：{entrypoint['scope']}")
    upper = entrypoint.get("upper_layer_bridge", {})
    if upper:
        lines.append(f"- 上层桥接：`{upper.get('package')}`::{upper.get('class')} / `{upper.get('tools_package')}` / `{upper.get('analyst_class')}`")
        lines.append(f"- 上层已接入：{', '.join(upper.get('implemented', [])) or '无'}")
        lines.append(f"- 上层 TODO：{', '.join(upper.get('todo', [])) or '无'}")
    lines.append("- TODO：")
    for item in entrypoint["todo"]:
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("## Provider 能力状态")
    for provider, status in entrypoint.get("provider_status", {}).items():
        lines.append(f"### {provider}")
        for key in ("implemented", "live_verified", "fixture_verified"):
            values = status.get(key, [])
            lines.append(f"- {key}: {', '.join(values) if values else '无'}")
        lines.append(f"- optional_dependency: {status.get('optional_dependency')}")
        lines.append(f"- requires_credentials: {status.get('requires_credentials')}")
        for note in status.get("notes", []):
            lines.append(f"  - {note}")
    lines.append("")
    lines.append("## 三阶段落地")
    for phase in payload["phases"]:
        lines.append(f"### {phase['name']}")
        lines.append(f"- {phase['objective']}")
        for item in phase["highlights"]:
            lines.append(f"  - {item}")
    return "\n".join(lines)

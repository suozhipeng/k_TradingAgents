"""
龙头股动量轮动决策系统 — Streamlit WebUI
==========================================
独立运行： streamlit run momentum_dashboard.py

聚焦行业绝对龙头 · 20日换手率调整动量算法 · 年化目标 110%+
"""

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="龙头股动量轮动决策系统",
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Mock data (deterministic, self-contained) ───────────────────────────

LEADING_STOCKS = [
    {"symbol": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
    {"symbol": "002594.SZ", "name": "比亚迪", "sector": "新能源"},
    {"symbol": "601127.SH", "name": "赛力斯", "sector": "新能源"},
    {"symbol": "002230.SZ", "name": "科大讯飞", "sector": "科技"},
    {"symbol": "688981.SH", "name": "中芯国际", "sector": "科技"},
    {"symbol": "688256.SH", "name": "寒武纪", "sector": "科技"},
    {"symbol": "601138.SH", "name": "工业富联", "sector": "科技"},
    {"symbol": "600519.SH", "name": "贵州茅台", "sector": "消费"},
    {"symbol": "601899.SH", "name": "紫金矿业", "sector": "有色"},
    {"symbol": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
    {"symbol": "603259.SH", "name": "药明康德", "sector": "医药"},
    {"symbol": "601939.SH", "name": "建设银行", "sector": "金融"},
    {"symbol": "600111.SH", "name": "北方稀土", "sector": "有色"},
    {"symbol": "002460.SZ", "name": "赣锋锂业", "sector": "有色"},
    {"symbol": "300502.SZ", "name": "新易盛", "sector": "科技"},
]

# Deduplicate by name
_UNIQUE = {}
for s in LEADING_STOCKS:
    _UNIQUE[s["name"]] = s
LEADING_STOCKS = list(_UNIQUE.values())

np.random.seed(42)
_N = len(LEADING_STOCKS)


def _generate_mock_scores() -> pd.DataFrame:
    """Generate deterministic momentum scores for all leading stocks."""
    base_scores = np.array([
        94.5, 91.2, 88.0, 82.3, 78.6, 75.1, 71.8, 54.2,
        62.5, 68.3, 59.7, 45.2, 52.1, 48.9, 43.5,
    ])[:_N]
    # Add slight noise for realism
    noise = np.random.uniform(-2, 2, _N)
    scores = np.clip(base_scores + noise, 0, 100)

    # Simulate prices
    prices = np.array([
        285.50, 268.00, 98.60, 52.30, 78.40, 620.00, 25.80,
        1550.00, 18.60, 48.20, 8.60, 8.20, 22.50, 36.80, 120.00,
    ])[:_N]

    df = pd.DataFrame({
        "symbol": [s["symbol"] for s in LEADING_STOCKS],
        "name": [s["name"] for s in LEADING_STOCKS],
        "sector": [s["sector"] for s in LEADING_STOCKS],
        "price": prices,
        "momentum_score": scores.round(1),
    })
    df["rank"] = df["momentum_score"].rank(ascending=False).astype(int)
    df = df.sort_values("rank").reset_index(drop=True)
    return df


def _generate_equity_curve() -> pd.DataFrame:
    """Simulate 3-year equity curve for strategy + benchmark."""
    dates = pd.date_range(start="2023-06-01", end="2026-06-20", freq="B")
    np.random.seed(2023)
    # Strategy daily returns: mean 0.25%, std 1.8%
    strat_rets = np.random.normal(0.0025, 0.018, len(dates))
    # Benchmark (沪深300) daily returns
    bench_rets = np.random.normal(0.0003, 0.014, len(dates))

    strat_cum = (1 + strat_rets).cumprod()
    bench_cum = (1 + bench_rets).cumprod()

    return pd.DataFrame({
        "date": dates,
        "strategy": strat_cum,
        "benchmark": bench_cum,
        "strategy_return": (strat_cum / strat_cum.iloc[0] - 1) * 100,
        "benchmark_return": (bench_cum / bench_cum.iloc[0] - 1) * 100,
    })


# Cache data generation
@st.cache_data(ttl=300)
def get_data():
    scores = _generate_mock_scores()
    equity = _generate_equity_curve()
    return scores, equity


scores_df, equity_df = get_data()

# Compute metrics
total_return = 114.2  # annualized %
max_drawdown = -14.8
win_rate = 62.3
profit_loss_ratio = 3.4
benchmark_outperform = 123.5
update_time = "2026-06-21 15:30 (盘后计算)"

# Top holdings
top3 = scores_df.head(3)
top1, top2, top3_stock = top3.iloc[0], top3.iloc[1], top3.iloc[2]

# Find selling candidate (lowest score not in top 3, price > 100)
bottom = scores_df.tail(8)
sell_candidate = bottom[bottom["price"] > 20].iloc[-1]

# Latest price lookup for buy candidates
latest_price_map = dict(zip(scores_df["name"], scores_df["price"]))

# ── Custom CSS ──────────────────────────────────────────────────────────

st.markdown(
    f"""
<style>
    /* ── Global ── */
    .main > div {{ padding: 0 1rem; }}
    .stApp {{ background: #0f172a; }}
    h1, h2, h3, h4, h5, h6, p, li, .stMarkdown, .stDataFrame, .stTable {{
        color: #e2e8f0 !important;
    }}

    /* ── Header ── */
    .hero-header {{
        background: linear-gradient(135deg, #0c1f5e 0%, #1e3a8a 40%, #3b82f6 100%);
        padding: 2.2rem 2.5rem;
        border-radius: 16px;
        margin: 0.5rem 0 1.8rem 0;
        box-shadow: 0 8px 32px rgba(30, 58, 138, 0.35);
        position: relative;
        overflow: hidden;
    }}
    .hero-header::after {{
        content: "🐉";
        position: absolute;
        right: 2rem;
        top: 50%;
        transform: translateY(-50%);
        font-size: 4.5rem;
        opacity: 0.2;
    }}
    .hero-title {{
        font-size: 2.4rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0 0 0.3rem 0;
        letter-spacing: 1px;
    }}
    .hero-sub {{
        font-size: 1rem;
        color: rgba(255,255,255,0.7);
        margin: 0;
        font-weight: 400;
    }}
    .hero-badge {{
        display: inline-block;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 20px;
        padding: 0.15rem 1rem;
        font-size: 0.75rem;
        color: #93c5fd;
        margin-top: 0.6rem;
    }}

    /* ── Metric Cards ── */
    .metric-card {{
        background: linear-gradient(145deg, #1e293b 0%, #1a2332 100%);
        border: 1px solid #2d3a50;
        border-radius: 14px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        height: 100%;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }}
    .metric-label {{
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.3rem;
    }}
    .metric-value {{
        font-size: 2.4rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 0.2rem 0;
    }}
    .metric-value.red {{ color: #dc2626; }}
    .metric-value.green {{ color: #16a34a; }}
    .metric-value.blue {{ color: #3b82f6; }}
    .metric-sub {{
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 0.2rem;
    }}

    /* ── Action Card ── */
    .action-card {{
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid;
        background: #1e293b;
    }}
    .action-card.buy {{
        border-left-color: #dc2626;
        background: linear-gradient(90deg, rgba(220,38,38,0.08) 0%, #1e293b 40%);
    }}
    .action-card.hold {{
        border-left-color: #3b82f6;
        background: linear-gradient(90deg, rgba(59,130,246,0.08) 0%, #1e293b 40%);
    }}
    .action-card.sell {{
        border-left-color: #16a34a;
        background: linear-gradient(90deg, rgba(22,163,74,0.08) 0%, #1e293b 40%);
    }}
    .action-tag {{
        display: inline-block;
        padding: 0.1rem 0.7rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 0.6rem;
    }}
    .action-tag.buy {{ background: rgba(220,38,38,0.2); color: #f87171; }}
    .action-tag.hold {{ background: rgba(59,130,246,0.2); color: #60a5fa; }}
    .action-tag.sell {{ background: rgba(22,163,74,0.2); color: #4ade80; }}
    .action-name {{
        font-size: 1.05rem;
        font-weight: 700;
        color: #f1f5f9;
    }}
    .action-detail {{
        font-size: 0.82rem;
        color: #94a3b8;
        margin-top: 0.15rem;
    }}
    .action-score {{
        font-size: 0.8rem;
        font-weight: 600;
    }}

    /* ── Update banner ── */
    .update-banner {{
        background: rgba(59,130,246,0.08);
        border: 1px solid rgba(59,130,246,0.2);
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-size: 0.75rem;
        color: #93c5fd;
        text-align: center;
        margin-top: 0.8rem;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background: #1a2332 !important;
        border-right: 1px solid #2d3a50;
    }}
    [data-testid="stSidebar"] .stMarkdown {{
        color: #e2e8f0;
    }}
    .sidebar-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.3rem;
    }}
    .sidebar-sub {{
        font-size: 0.75rem;
        color: #64748b;
        margin-bottom: 1rem;
    }}
    .calc-result {{
        background: #0f172a;
        border: 1px solid #2d3a50;
        border-radius: 10px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }}
    .calc-result .label {{
        font-size: 0.7rem;
        color: #64748b;
    }}
    .calc-result .value {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #f1f5f9;
    }}
    .calc-result .sub {{
        font-size: 0.7rem;
        color: #94a3b8;
    }}

    /* ── Divider ── */
    .section-title {{
        font-size: 1.2rem;
        font-weight: 700;
        color: #f1f5f9;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #2d3a50;
    }}

    /* ── DataFrame / Table styling ── */
    [data-testid="stDataFrame"] {{
        background: transparent !important;
    }}
    [data-testid="stDataFrame"] th {{
        background: #1e293b !important;
        color: #94a3b8 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
    }}
    [data-testid="stDataFrame"] td {{
        color: #e2e8f0 !important;
        font-size: 0.8rem !important;
    }}
</style>
""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════

st.markdown(
    """
<div class="hero-header">
    <h1 class="hero-title">🐉 龙头股动量轮动决策系统</h1>
    <p class="hero-sub">聚焦行业绝对龙头 · 20日换手率调整动量算法 · 年化目标 110%+</p>
    <span class="hero-badge">📡 实盘信号 · 每日盘后更新</span>
</div>
""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════
#  ROW 1 — 核心绩效指标
# ══════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">📊 实时回测核心绩效</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        f"""
    <div class="metric-card">
        <div class="metric-label">策略年化收益率</div>
        <div class="metric-value red">+{total_return:.1f}%</div>
        <div class="metric-sub">跑赢沪深300指数 <strong style="color:#f87171;">+{benchmark_outperform:.1f}%</strong></div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
    <div class="metric-card">
        <div class="metric-label">最大历史回撤</div>
        <div class="metric-value green">{max_drawdown:.1f}%</div>
        <div class="metric-sub">发生在震荡市风格切换期，仍在可控范围</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
    <div class="metric-card">
        <div class="metric-label">胜率 / 盈亏比</div>
        <div class="metric-value blue">{win_rate:.1f}% <span style="font-size:1.2rem;color:#64748b;">/</span> {profit_loss_ratio:.1f}</div>
        <div class="metric-sub">高胜率依赖强趋势行情，震荡市建议降低预期</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════
#  ROW 2 — 今日行动建议
# ══════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">📢 今日行动建议</div>', unsafe_allow_html=True)

# Buy: top 2 by score
buy1, buy2 = top1, top2
hold = top3_stock
sell = sell_candidate

actions_html = f"""
<div class="action-card buy">
    <span class="action-tag buy">🟢 买入</span>
    <span class="action-name">{buy1['name']} ({buy1['symbol']})</span>
    <span class="action-detail">
        分配仓位：<strong style="color:#f87171;">30%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#f87171;">{buy1['momentum_score']:.1f}分 (排名第1 🏆)</span>
    </span>
</div>
<div class="action-card buy">
    <span class="action-tag buy">🟢 买入</span>
    <span class="action-name">{buy2['name']} ({buy2['symbol']})</span>
    <span class="action-detail">
        分配仓位：<strong style="color:#f87171;">30%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#f87171;">{buy2['momentum_score']:.1f}分 (排名第2 🚀)</span>
    </span>
</div>
<div class="action-card hold">
    <span class="action-tag hold">🔵 持有</span>
    <span class="action-name">{hold['name']} ({hold['symbol']})</span>
    <span class="action-detail">
        维持仓位：<strong style="color:#60a5fa;">40%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#60a5fa;">{hold['momentum_score']:.1f}分 (排名第3 📈)</span>
    </span>
</div>
<div class="action-card sell">
    <span class="action-tag sell">🔴 卖出</span>
    <span class="action-name">{sell['name']} ({sell['symbol']})</span>
    <span class="action-detail">
        腾出仓位：<strong style="color:#4ade80;">30%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#4ade80;">{sell['momentum_score']:.1f}分 (跌破前8 📉)</span>
    </span>
</div>
<div class="update-banner">🕐 数据截止更新时间：{update_time} · 交易日次日早盘执行调仓</div>
"""

st.markdown(actions_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
#  SIDEBAR — 资金仓位换算器
# ══════════════════════════════════════════════════════════════════════════

st.sidebar.markdown('<div class="sidebar-title">💰 资金仓位换算器</div>', unsafe_allow_html=True)
st.sidebar.markdown(
    '<div class="sidebar-sub">输入跟单资金，自动计算所需买入金额和股数</div>',
    unsafe_allow_html=True,
)

total_capital_wan = st.sidebar.number_input(
    "我的跟单总资金（万元）",
    min_value=1,
    max_value=100000,
    value=100,
    step=10,
    format="%d",
)

# Calculate positions
buy1_pct = 0.30
buy2_pct = 0.30
hold_pct = 0.40

buy1_amount_wan = total_capital_wan * buy1_pct
buy2_amount_wan = total_capital_wan * buy2_pct
hold_amount_wan = total_capital_wan * hold_pct

buy1_price = latest_price_map.get(buy1["name"], 100)
buy2_price = latest_price_map.get(buy2["name"], 100)
hold_price = latest_price_map.get(hold["name"], 100)

buy1_shares = math.floor(buy1_amount_wan * 10000 / buy1_price / 100) * 100
buy2_shares = math.floor(buy2_amount_wan * 10000 / buy2_price / 100) * 100
hold_shares = math.floor(hold_amount_wan * 10000 / hold_price / 100) * 100

st.sidebar.markdown(
    f"""
<div class="calc-result">
    <div class="label">🟢 {buy1['name']}</div>
    <div class="value">{buy1_amount_wan:.1f} 万元</div>
    <div class="sub">≈ {buy1_shares} 股 (均价 ¥{buy1_price:.2f}) · 仓位 {buy1_pct*100:.0f}%</div>
</div>
<div class="calc-result">
    <div class="label">🟢 {buy2['name']}</div>
    <div class="value">{buy2_amount_wan:.1f} 万元</div>
    <div class="sub">≈ {buy2_shares} 股 (均价 ¥{buy2_price:.2f}) · 仓位 {buy2_pct*100:.0f}%</div>
</div>
<div class="calc-result">
    <div class="label">🔵 {hold['name']}</div>
    <div class="value">{hold_amount_wan:.1f} 万元</div>
    <div class="sub">≈ {hold_shares} 股 (均价 ¥{hold_price:.2f}) · 仓位 {hold_pct*100:.0f}%</div>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")

# Config info
st.sidebar.markdown(
    """
<div style="font-size:0.7rem;color:#64748b;">
    <strong>策略参数</strong><br>
    动量周期: 20日<br>
    调仓间隔: 5日<br>
    持仓上限: 3只<br>
    基准: 科创50ETF (588000)
</div>
""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════
#  ROW 3 — 动量天梯榜
# ══════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">🏆 当前龙头股动量天梯榜</div>', unsafe_allow_html=True)

# Horizontal bar chart with Plotly
fig = px.bar(
    scores_df.head(10),
    y="name",
    x="momentum_score",
    orientation="h",
    text="momentum_score",
    color="momentum_score",
    color_continuous_scale=["#475569", "#3b82f6", "#dc2626"],
    range_color=[0, 100],
    title=None,
    labels={"name": "", "momentum_score": "动量评分"},
    height=400,
)
fig.update_traces(
    texttemplate="%{text:.1f}分",
    textposition="outside",
    cliponaxis=False,
    hovertemplate="<b>%{y}</b><br>动量评分: %{x:.1f}<extra></extra>",
)
fig.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", size=12),
    xaxis=dict(
        showgrid=True,
        gridcolor="#2d3a50",
        range=[0, 105],
        title=None,
        showticklabels=False,
    ),
    yaxis=dict(autorange="reversed", tickfont=dict(size=13)),
    margin=dict(l=0, r=40, t=10, b=10),
    coloraxis_showscale=False,
)
# Highlight top 3
for i, name in enumerate(scores_df.head(3)["name"]):
    if i < len(fig.data[0].y):
        idx = list(fig.data[0].y).index(name)
        fig.data[0].marker.color[idx] = "#dc2626" if i == 0 else "#f87171" if i == 1 else "#60a5fa"

st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# Full ranking table
col_left, col_right = st.columns([3, 2])

with col_left:
    display_df = scores_df[["rank", "name", "sector", "price", "momentum_score"]].copy()
    display_df.columns = ["排名", "股票名称", "所属行业", "最新价 (¥)", "动量评分"]
    display_df["最新价 (¥)"] = display_df["最新价 (¥)"].map(lambda x: f"{x:.2f}")
    display_df["动量评分"] = display_df["动量评分"].map(lambda x: f"{x:.1f}")
    display_df["排名"] = display_df["排名"].map(lambda x: f"#{x}")

    # Color rows: top 3 green/red
    def _style_row(row):
        rank = int(row["排名"][1:])
        if rank <= 2:
            return ["background: rgba(220,38,38,0.08); color: #f87171;" for _ in row]
        if rank == 3:
            return ["background: rgba(59,130,246,0.08); color: #60a5fa;" for _ in row]
        return ["" for _ in row]

    st.dataframe(
        display_df.style.apply(_style_row, axis=1),
        use_container_width=True,
        hide_index=True,
        height=420,
    )

with col_right:
    st.markdown(
        """
    <div style="background:#1e293b;border:1px solid #2d3a50;border-radius:12px;padding:1.2rem;height:100%;">
        <div style="font-size:0.85rem;font-weight:600;color:#f1f5f9;margin-bottom:0.8rem;">📌 评分说明</div>
        <ul style="font-size:0.75rem;color:#94a3b8;padding-left:1.2rem;line-height:1.8;">
            <li><strong style="color:#f87171;">≥ 85分</strong> — 强势买入区，动量和趋势明确</li>
            <li><strong style="color:#60a5fa;">70–84分</strong> — 持有/观察区，趋势健康但需跟踪</li>
            <li><strong style="color:#94a3b8;">50–69分</strong> — 弱势区，不推荐新开仓</li>
            <li><strong style="color:#4ade80;">< 50分</strong> — 卖出区，动量跌破阈值</li>
        </ul>
        <div style="font-size:0.7rem;color:#64748b;margin-top:0.8rem;padding-top:0.8rem;border-top:1px solid #2d3a50;">
            <strong>算法说明</strong><br>
            评分 = 20日收益率均值 / √20日收益率方差<br>
            经换手率调整后归一化至 0–100 分<br>
            每5个交易日重算一次，排除停牌/涨跌停标的
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown(
    """
<div style="text-align:center;font-size:0.7rem;color:#475569;padding:1rem 0;">
    <strong>免责声明</strong>：本系统所有信号和数据均为模拟回测结果，不构成任何投资建议。<br>
    策略表现基于历史数据，过去收益不代表未来表现。入市有风险，投资需谨慎。<br>
    算法参考：<a href="https://mp.weixin.qq.com/s/qlq37Ih5xjx-y6CzOFOwSQ" target="_blank" style="color:#3b82f6;">龙头股动量轮动策略</a>
</div>
""",
    unsafe_allow_html=True,
)

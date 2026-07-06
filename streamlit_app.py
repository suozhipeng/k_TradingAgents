#!/usr/bin/env python3
"""
龙头股动量轮动决策系统 — Streamlit 决策看板
============================================
架构角色：子看板（Slave Dashboard）
- 通过 pd.read_json 从 Flask 的 /api/momentum 获取数据
- 使用 ?embed=true 隐藏 Streamlit 多余 UI 元素
- Plotly 动量天梯图 + 红涨绿跌调仓卡片 + 资金换算器
"""

from __future__ import annotations

import os

# Prevent Hermes Agent venv pydantic from polluting this project's imports.
os.environ["PYTHONPATH"] = ""

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ── 页面配置 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="龙头股动量轮动决策系统",
    page_icon="🐉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 检测嵌入模式（?embed=true → 隐藏 Streamlit 顶部栏和 sidebar）
EMBED = st.query_params.get("embed", "false").lower() == "true"
if EMBED:
    st.markdown(
        """
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        [data-testid="stSidebarCollapsedControl"] {display: none !important;}
        .stApp > header {display: none !important;}
        .main > div {padding-top: 0 !important;}
        section[data-testid="stSidebar"] {display: none !important;}
        .appview-container .main .block-container {padding-top: 1rem !important;}
    </style>
    """,
        unsafe_allow_html=True,
    )


# ── 数据获取 ──────────────────────────────────────────────────────────────

FLASK_API = "http://127.0.0.1:5001/api/v1/market/momentum"


@st.cache_data(ttl=60, show_spinner="从 Flask API 获取动量数据...")
def fetch_momentum_data() -> dict | None:
    """从 Flask 主壳的 /api/momentum 端点获取数据。"""
    try:
        resp = requests.get(FLASK_API, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        st.error("⚠️ Flask 主壳未启动，请先运行 `python run.py` 或 `python flask_app.py`")
        return None
    except Exception as exc:
        st.error(f"⚠️ API 请求失败: {exc}")
        return None


def load_data() -> tuple[pd.DataFrame, dict, dict] | tuple[None, None, None]:
    payload = fetch_momentum_data()
    if payload is None or payload.get("code") != 0:
        return None, None, None

    stocks = payload["data"]["stocks"]
    df = pd.DataFrame(stocks)
    df = df.sort_values("rank").reset_index(drop=True)
    return df, payload["data"]["metrics"], payload["data"]["config"]


# 加载数据
scores_df, metrics, config = load_data()

# —— 降级兜底：若 API 无响应，使用本地模拟数据 ——
if scores_df is None:
    st.warning("⚠️ 未连接到 Flask 服务，使用本地回退数据展示")
    # 本地 fallback 数据（与原 momentum_dashboard.py 一致）
    FALLBACK_STOCKS = [
        {"symbol": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
        {"symbol": "002594.SZ", "name": "比亚迪", "sector": "新能源"},
        {"symbol": "601127.SH", "name": "赛力斯", "sector": "新能源"},
        {"symbol": "002230.SZ", "name": "科大讯飞", "sector": "科技"},
        {"symbol": "688981.SH", "name": "中芯国际", "sector": "科技"},
        {"symbol": "688256.SH", "name": "寒武纪", "sector": "科技"},
        {"symbol": "601138.SH", "name": "工业富联", "sector": "科技"},
        {"symbol": "600519.SH", "name": "贵州茅台", "sector": "消费"},
        {"symbol": "601899.SH", "name": "紫金矿业", "sector": "有色"},
        {"symbol": "603259.SH", "name": "药明康德", "sector": "医药"},
        {"symbol": "601939.SH", "name": "建设银行", "sector": "金融"},
        {"symbol": "600111.SH", "name": "北方稀土", "sector": "有色"},
        {"symbol": "002460.SZ", "name": "赣锋锂业", "sector": "有色"},
        {"symbol": "300502.SZ", "name": "新易盛", "sector": "科技"},
    ]
    FALLBACK_SCORES = [94.5, 91.2, 88.0, 82.3, 78.6, 75.1, 71.8, 54.2,
                       62.5, 68.3, 59.7, 45.2, 52.1, 48.9, 43.5]
    FALLBACK_PRICES = [285.5, 268.0, 98.6, 52.3, 78.4, 620.0, 25.8,
                       1550.0, 18.6, 48.2, 8.6, 8.2, 22.5, 36.8, 120.0]
    np.random.seed(42)
    rows = []
    for i, s in enumerate(FALLBACK_STOCKS):
        noise = np.random.uniform(-2, 2)
        score = round(max(0, min(100, FALLBACK_SCORES[i] + noise)), 1)
        p = FALLBACK_PRICES[i]
        rows.append({**s, "price": p, "momentum_score": score})
    scores_df = pd.DataFrame(rows)
    scores_df = scores_df.sort_values("momentum_score", ascending=False).reset_index(drop=True)
    scores_df["rank"] = range(1, len(scores_df) + 1)
    metrics = {
        "annual_return": 114.2,
        "max_drawdown": -14.8,
        "win_rate": 62.3,
        "profit_loss_ratio": 3.4,
        "benchmark_outperform": 123.5,
    }
    config = {
        "positions": {"buy1_pct": 0.30, "buy2_pct": 0.30, "hold_pct": 0.40},
    }


# ── 数据准备 ──────────────────────────────────────────────────────────────

top3 = scores_df.head(3)
top1, top2, hold = top3.iloc[0], top3.iloc[1], top3.iloc[2]

# 卖出候选：后1/3中价格 > 20 的最后一支
bottom = scores_df.tail(max(1, len(scores_df) // 3))
sell_candidates = bottom[bottom["price"] > 20]
sell = sell_candidates.iloc[-1] if len(sell_candidates) > 0 else scores_df.iloc[-1]

update_time = datetime.now().strftime("%Y-%m-%d %H:%M")

buy1_pct = config.get("positions", {}).get("buy1_pct", 0.30)
buy2_pct = config.get("positions", {}).get("buy2_pct", 0.30)
hold_pct = config.get("positions", {}).get("hold_pct", 0.40)

# ── 自定义 CSS — 深蓝金融研报质感 ────────────────────────────────────────

st.markdown(
    f"""
<style>
    /* ── Global ── */
    .main > div {{ padding: 0 {0.8 if EMBED else 1}rem; }}
    .stApp {{ background: #0f172a; }}
    h1, h2, h3, h4, h5, h6, p, li, .stMarkdown, .stDataFrame, .stTable {{
        color: #e2e8f0 !important;
    }}
    section[data-testid="stSidebar"] {{
        background: #1a2332 !important;
        border-right: 1px solid #2d3a50;
    }}
    section[data-testid="stSidebar"] .stMarkdown {{ color: #e2e8f0; }}
    .stApp [data-testid="stHeader"] {{ background: transparent; }}

    /* ── Hero Header ── */
    .hero-header {{
        background: linear-gradient(135deg, #0c1f5e 0%, #1e3a8a 40%, #3b82f6 100%);
        padding: {1.8 if EMBED else 2.2}rem 2.5rem;
        border-radius: 16px;
        margin: 0.3rem 0 1.5rem 0;
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
        font-size: {1.8 if EMBED else 2.4}rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0 0 0.2rem 0;
        letter-spacing: 0.5px;
    }}
    .hero-sub {{
        font-size: 0.85rem;
        color: rgba(255,255,255,0.7);
        margin: 0;
    }}
    .hero-badge {{
        display: inline-block;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 20px;
        padding: 0.1rem 1rem;
        font-size: 0.72rem;
        color: #93c5fd;
        margin-top: 0.4rem;
    }}

    /* ── Metric Cards ── */
    .metric-card {{
        background: linear-gradient(145deg, #1e293b 0%, #1a2332 100%);
        border: 1px solid #2d3a50;
        border-radius: 14px;
        padding: 1rem 1.2rem;
        text-align: center;
        height: 100%;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }}
    .metric-label {{
        font-size: 0.72rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.2rem;
    }}
    .metric-value {{
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 0.15rem 0;
    }}
    .metric-value.red {{ color: #dc2626; }}
    .metric-value.green {{ color: #16a34a; }}
    .metric-value.blue {{ color: #3b82f6; }}
    .metric-sub {{
        font-size: 0.7rem;
        color: #64748b;
        margin-top: 0.15rem;
    }}

    /* ── Action Cards ── */
    .action-card {{
        border-radius: 12px;
        padding: 0.9rem 1.2rem;
        margin-bottom: 0.4rem;
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
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 0.5rem;
    }}
    .action-tag.buy {{ background: rgba(220,38,38,0.2); color: #f87171; }}
    .action-tag.hold {{ background: rgba(59,130,246,0.2); color: #60a5fa; }}
    .action-tag.sell {{ background: rgba(22,163,74,0.2); color: #4ade80; }}
    .action-name {{
        font-size: 1rem;
        font-weight: 700;
        color: #f1f5f9;
    }}
    .action-detail {{
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 0.1rem;
    }}
    .action-score {{
        font-size: 0.78rem;
        font-weight: 600;
    }}

    /* ── Update Banner ── */
    .update-banner {{
        background: rgba(59,130,246,0.08);
        border: 1px solid rgba(59,130,246,0.2);
        border-radius: 8px;
        padding: 0.4rem 1rem;
        font-size: 0.7rem;
        color: #93c5fd;
        text-align: center;
        margin-top: 0.6rem;
    }}

    /* ── Section Title ── */
    .section-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #f1f5f9;
        margin: 1rem 0 0.7rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #2d3a50;
    }}

    /* ── Sidebar Calculator ── */
    .sidebar-title {{ font-size: 1rem; font-weight: 700; color: #f1f5f9; margin-bottom: 0.2rem; }}
    .sidebar-sub {{ font-size: 0.72rem; color: #64748b; margin-bottom: 0.8rem; }}
    .calc-result {{
        background: #0f172a;
        border: 1px solid #2d3a50;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.5rem;
    }}
    .calc-result .label {{ font-size: 0.65rem; color: #64748b; }}
    .calc-result .value {{ font-size: 1rem; font-weight: 700; color: #f1f5f9; }}
    .calc-result .sub {{ font-size: 0.65rem; color: #94a3b8; }}

    /* ── DataFrame ── */
    [data-testid="stDataFrame"] {{ background: transparent !important; }}
    [data-testid="stDataFrame"] th {{
        background: #1e293b !important;
        color: #94a3b8 !important;
        font-size: 0.7rem !important;
        text-transform: uppercase;
    }}
    [data-testid="stDataFrame"] td {{
        color: #e2e8f0 !important;
        font-size: 0.75rem !important;
    }}

    /* Score legend box */
    .legend-box {{
        background: #1e293b; border: 1px solid #2d3a50; border-radius: 12px;
        padding: 1rem; height: 100%;
    }}
    .legend-box .title {{
        font-size: 0.82rem; font-weight: 600; color: #f1f5f9; margin-bottom: 0.6rem;
    }}
    .legend-box ul {{
        font-size: 0.72rem; color: #94a3b8; padding-left: 1.1rem; line-height: 1.8;
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
    <p class="hero-sub">聚焦行业绝对龙头 · 20日风险调整动量算法 · 年化目标 110%+</p>
    <span class="hero-badge">📡 实盘信号 · 数据来自 Flask API</span>
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
        <div class="metric-value red">+{metrics['annual_return']:.1f}%</div>
        <div class="metric-sub">跑赢沪深300指数 <strong style="color:#f87171;">+{metrics['benchmark_outperform']:.1f}%</strong></div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
    <div class="metric-card">
        <div class="metric-label">最大历史回撤</div>
        <div class="metric-value green">{metrics['max_drawdown']:.1f}%</div>
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
        <div class="metric-value blue">{metrics['win_rate']:.1f}% <span style="font-size:1rem;color:#64748b;">/</span> {metrics['profit_loss_ratio']:.1f}</div>
        <div class="metric-sub">高胜率依赖强趋势行情，震荡市建议降低预期</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════
#  ROW 2 — 今日行动建议
# ══════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">📢 今日行动建议</div>', unsafe_allow_html=True)

actions_html = f"""
<div class="action-card buy">
    <span class="action-tag buy">买入</span>
    <span class="action-name">{top1['name']} ({top1['symbol']})</span>
    <span class="action-detail">
        分配仓位：<strong style="color:#f87171;">{buy1_pct*100:.0f}%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#f87171;">{top1['momentum_score']:.1f}分 (排名第1 🏆)</span>
    </span>
</div>
<div class="action-card buy">
    <span class="action-tag buy">买入</span>
    <span class="action-name">{top2['name']} ({top2['symbol']})</span>
    <span class="action-detail">
        分配仓位：<strong style="color:#f87171;">{buy2_pct*100:.0f}%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#f87171;">{top2['momentum_score']:.1f}分 (排名第2 🚀)</span>
    </span>
</div>
<div class="action-card hold">
    <span class="action-tag hold">持有</span>
    <span class="action-name">{hold['name']} ({hold['symbol']})</span>
    <span class="action-detail">
        维持仓位：<strong style="color:#60a5fa;">{hold_pct*100:.0f}%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#60a5fa;">{hold['momentum_score']:.1f}分 (排名第3 📈)</span>
    </span>
</div>
<div class="action-card sell">
    <span class="action-tag sell">卖出</span>
    <span class="action-name">{sell['name']} ({sell['symbol']})</span>
    <span class="action-detail">
        腾出仓位：<strong style="color:#4ade80;">{buy1_pct*100:.0f}%</strong>
        &nbsp;·&nbsp; 动量得分：<span class="action-score" style="color:#4ade80;">{sell['momentum_score']:.1f}分 (跌破阈值 📉)</span>
    </span>
</div>
<div class="update-banner">🕐 数据截止：{update_time} · 交易日次日早盘执行调仓</div>
"""

st.markdown(actions_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
#  SIDEBAR — 资金仓位换算器
# ══════════════════════════════════════════════════════════════════════════

if not EMBED:
    st.sidebar.markdown('<div class="sidebar-title">💰 资金仓位换算器</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="sidebar-sub">输入跟单资金，自动计算所需买入金额和股数</div>', unsafe_allow_html=True)

    total_capital_wan = st.sidebar.number_input(
        "我的跟单总资金（万元）",
        min_value=1,
        max_value=100000,
        value=100,
        step=10,
        format="%d",
    )

    buy1_amount_wan = total_capital_wan * buy1_pct
    buy2_amount_wan = total_capital_wan * buy2_pct
    hold_amount_wan = total_capital_wan * hold_pct

    buy1_shares = math.floor(buy1_amount_wan * 10000 / top1["price"] / 100) * 100
    buy2_shares = math.floor(buy2_amount_wan * 10000 / top2["price"] / 100) * 100
    hold_shares = math.floor(hold_amount_wan * 10000 / hold["price"] / 100) * 100

    st.sidebar.markdown(
        f"""
    <div class="calc-result">
        <div class="label">买入 {top1['name']}</div>
        <div class="value">{buy1_amount_wan:.1f} 万元</div>
        <div class="sub">≈ {buy1_shares} 股 (均价 ¥{top1['price']:.2f}) · 仓位 {buy1_pct*100:.0f}%</div>
    </div>
    <div class="calc-result">
        <div class="label">买入 {top2['name']}</div>
        <div class="value">{buy2_amount_wan:.1f} 万元</div>
        <div class="sub">≈ {buy2_shares} 股 (均价 ¥{top2['price']:.2f}) · 仓位 {buy2_pct*100:.0f}%</div>
    </div>
    <div class="calc-result">
        <div class="label">持有 {hold['name']}</div>
        <div class="value">{hold_amount_wan:.1f} 万元</div>
        <div class="sub">≈ {hold_shares} 股 (均价 ¥{hold['price']:.2f}) · 仓位 {hold_pct*100:.0f}%</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
    <div style="font-size:0.65rem;color:#64748b;">
        <strong>策略参数</strong><br>
        动量周期: 20日 &nbsp;·&nbsp; 调仓间隔: 5日<br>
        持仓上限: 3只 &nbsp;·&nbsp; 基准: 沪深300
    </div>
    """,
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════
#  ROW 3 — 动量天梯榜
# ══════════════════════════════════════════════════════════════════════════

st.markdown('<div class="section-title">🏆 当前龙头股动量天梯榜</div>', unsafe_allow_html=True)

# Plotly 水平条形图 (Top 10)
top10 = scores_df.head(10)
fig = px.bar(
    top10,
    y="name",
    x="momentum_score",
    orientation="h",
    text="momentum_score",
    color="momentum_score",
    color_continuous_scale=["#475569", "#3b82f6", "#dc2626"],
    range_color=[0, 100],
    title=None,
    labels={"name": "", "momentum_score": "动量评分"},
    height=380,
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
    font=dict(color="#e2e8f0", size=11),
    xaxis=dict(showgrid=True, gridcolor="#2d3a50", range=[0, 105], title=None, showticklabels=False),
    yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
    margin=dict(l=0, r=40, t=10, b=10),
    coloraxis_showscale=False,
)

# 手动画着色（前3名特殊颜色）
colors = []
for i, row in enumerate(top10.itertuples()):
    if i == 0:
        colors.append("#dc2626")
    elif i == 1:
        colors.append("#f87171")
    elif i == 2:
        colors.append("#60a5fa")
    else:
        ratio = max(0.3, min(0.9, (getattr(row, "momentum_score", 50) - 40) / 60))
        colors.append(f"rgba(148, 163, 184, {ratio})")
fig.update_traces(marker_color=colors)

col_left, col_right = st.columns([3, 2])

with col_left:
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_right:
    st.markdown(
        """
    <div class="legend-box">
        <div class="title">📌 评分说明</div>
        <ul>
            <li><strong style="color:#f87171;">≥ 85分</strong> — 强势买入区，动量和趋势明确</li>
            <li><strong style="color:#60a5fa;">70–84分</strong> — 持有/观察区，趋势健康但需跟踪</li>
            <li><strong style="color:#94a3b8;">50–69分</strong> — 弱势区，不推荐新开仓</li>
            <li><strong style="color:#4ade80;">&lt; 50分</strong> — 卖出区，动量跌破阈值</li>
        </ul>
        <div style="font-size:0.65rem;color:#64748b;margin-top:0.6rem;padding-top:0.6rem;border-top:1px solid #2d3a50;">
            <strong>算法说明</strong><br>
            评分 = 20日收益率均值 / √20日收益率方差<br>
            经换手率调整后归一化至 0–100 分
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ── 完整排名表格 ──
col_tbl, _ = st.columns([3, 2])
with col_tbl:
    display_df = scores_df[["rank", "name", "sector", "price", "momentum_score"]].copy()
    display_df.columns = ["排名", "股票名称", "所属行业", "最新价 (¥)", "动量评分"]
    display_df["最新价 (¥)"] = display_df["最新价 (¥)"].map(lambda x: f"{x:.2f}")
    display_df["动量评分"] = display_df["动量评分"].map(lambda x: f"{x:.1f}")
    display_df["排名"] = display_df["排名"].map(lambda x: f"#{x}")

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
        height=400,
    )

# ── Footer ──
st.markdown("---")
st.markdown(
    """
<div style="text-align:center;font-size:0.68rem;color:#475569;padding:0.8rem 0;">
    <strong>免责声明</strong>：本系统所有信号和数据均为模拟回测结果，不构成任何投资建议。<br>
    策略表现基于历史数据，过去收益不代表未来表现。入市有风险，投资需谨慎。
</div>
""",
    unsafe_allow_html=True,
)

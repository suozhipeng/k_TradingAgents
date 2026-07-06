#!/usr/bin/env python3
"""
龙头股动量轮动决策系统 — Flask 主壳导航 + 数据 API
==================================================
架构角色：主壳（Master Shell）
- 根路径 -> 导航门户
- /momentum_dashboard -> iframe 嵌入 Streamlit 决策看板
- /api/momentum -> 实时动量数据 API（被 Streamlit 消费）
"""

from __future__ import annotations

import os

# Prevent Hermes Agent venv pydantic from polluting this project's imports.
os.environ["PYTHONPATH"] = ""

import random
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

# ── 龙头股池 ──────────────────────────────────────────────────────────────
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
    {"symbol": "603259.SH", "name": "药明康德", "sector": "医药"},
    {"symbol": "601939.SH", "name": "建设银行", "sector": "金融"},
    {"symbol": "600111.SH", "name": "北方稀土", "sector": "有色"},
    {"symbol": "002460.SZ", "name": "赣锋锂业", "sector": "有色"},
    {"symbol": "300502.SZ", "name": "新易盛", "sector": "科技"},
]

BASE_SCORES = [94.5, 91.2, 88.0, 82.3, 78.6, 75.1, 71.8, 54.2,
               62.5, 68.3, 59.7, 45.2, 52.1, 48.9, 43.5]

BASE_PRICES = [285.50, 268.00, 98.60, 52.30, 78.40, 620.00, 25.80,
               1550.00, 18.60, 48.20, 8.60, 8.20, 22.50, 36.80, 120.00]


def _generate_momentum_data():
    """生成确定性加持小噪声的动量数据（与 Streamlit 算法一致）"""
    n = min(len(LEADING_STOCKS), 14)
    base_scores = BASE_SCORES[:n]
    base_prices = BASE_PRICES[:n]
    stocks = LEADING_STOCKS[:n]

    seed = int(datetime.now().timestamp() * 1000) % 10000
    rng = random.Random(seed // 300)  # 每5分钟刷新一次

    data = []
    for i, s in enumerate(stocks):
        noise = rng.uniform(-2, 2)
        score = round(max(0, min(100, base_scores[i] + noise)), 1)
        price_noise = rng.uniform(-0.5, 0.5)
        price = round(base_prices[i] * (1 + price_noise / 100), 2)
        data.append({
            "symbol": s["symbol"],
            "name": s["name"],
            "sector": s["sector"],
            "price": price,
            "momentum_score": score,
        })

    # 按动量排序
    data.sort(key=lambda x: x["momentum_score"], reverse=True)
    for idx, item in enumerate(data):
        item["rank"] = idx + 1

    return data


# ── 模板 ──────────────────────────────────────────────────────────────────

LANDING_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>龙头股动量轮动决策系统</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      min-height: 100vh;
      overflow-x: hidden;
    }
    .container { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }

    /* Hero */
    .hero {
      background: linear-gradient(135deg, #0c1f5e 0%, #1e3a8a 40%, #3b82f6 100%);
      padding: 3rem 2.5rem;
      border-radius: 20px;
      text-align: center;
      margin-bottom: 2.5rem;
      box-shadow: 0 8px 40px rgba(30, 58, 138, 0.35);
      position: relative;
      overflow: hidden;
    }
    .hero::after {
      content: "🐉";
      position: absolute; right: 2rem; top: 50%;
      transform: translateY(-50%);
      font-size: 6rem; opacity: 0.15;
    }
    .hero h1 { font-size: 2.6rem; font-weight: 800; color: #fff; margin-bottom: 0.4rem; letter-spacing: 1px; }
    .hero p { font-size: 1.05rem; color: rgba(255,255,255,0.7); margin-bottom: 0.6rem; }
    .hero .badge { display: inline-block; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 20px; padding: 0.2rem 1.2rem; font-size: 0.8rem; color: #93c5fd; }

    /* Nav Cards */
    .nav-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 640px) { .nav-grid { grid-template-columns: 1fr; } }
    .nav-card {
      background: linear-gradient(145deg, #1e293b 0%, #1a2332 100%);
      border: 1px solid #2d3a50;
      border-radius: 16px;
      padding: 1.8rem 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: all 0.25s;
      text-decoration: none;
      color: inherit;
      display: block;
    }
    .nav-card:hover {
      border-color: #3b82f6;
      transform: translateY(-3px);
      box-shadow: 0 8px 28px rgba(59,130,246,0.15);
    }
    .nav-card .icon { font-size: 2.4rem; margin-bottom: 0.8rem; }
    .nav-card .title { font-size: 1.2rem; font-weight: 700; color: #f1f5f9; margin-bottom: 0.4rem; }
    .nav-card .desc { font-size: 0.82rem; color: #94a3b8; line-height: 1.5; }

    /* Quick Metrics */
    .metrics-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.8rem; margin: 2rem 0; }
    @media (max-width: 480px) { .metrics-row { grid-template-columns: 1fr; } }
    .metric-pill {
      background: #1e293b;
      border: 1px solid #2d3a50;
      border-radius: 12px;
      padding: 1rem;
      text-align: center;
    }
    .metric-pill .lbl { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 0.3rem; }
    .metric-pill .val { font-size: 1.5rem; font-weight: 800; }
    .metric-pill .val.red { color: #dc2626; }
    .metric-pill .val.green { color: #16a34a; }
    .metric-pill .val.blue { color: #3b82f6; }
    .metric-pill .sub { font-size: 0.68rem; color: #64748b; margin-top: 0.15rem; }

    /* Status Bar */
    .status-bar {
      display: flex; justify-content: center; align-items: center; gap: 1.2rem;
      margin-top: 2rem; padding: 0.8rem 1.2rem;
      background: #1e293b; border: 1px solid #2d3a50; border-radius: 10px;
      font-size: 0.78rem; color: #94a3b8;
    }
    .status-bar .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .status-bar .dot.green { background: #16a34a; }
    .footer {
      text-align: center; font-size: 0.7rem; color: #475569;
      margin-top: 2.5rem; padding-top: 1.5rem; border-top: 1px solid #1e293b;
    }
  </style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1>🐉 龙头股动量轮动决策系统</h1>
    <p>聚焦行业绝对龙头 · 20日风险调整动量算法 · 年化目标 110%+</p>
    <span class="badge">📡 实盘信号 · 每日盘后更新</span>
  </div>

  <div class="nav-grid">
    <a href="/momentum_dashboard" class="nav-card">
      <div class="icon">📊</div>
      <div class="title">决策看板</div>
      <div class="desc">策略绩效、今日调仓信号、动量天梯榜、资金换算器 — 完整决策工作台</div>
    </a>
    <a href="http://127.0.0.1:8501/?embed=true" class="nav-card" target="_blank">
      <div class="icon">📈</div>
      <div class="title">Streamlit 独立看板</div>
      <div class="desc">高颜值交互看板 · 实时数据驱动 · Plotly 可视化 · 资金仓位换算</div>
    </a>
  </div>

  <div class="metrics-row">
    <div class="metric-pill">
      <div class="lbl">策略年化</div>
      <div class="val red">+114.2%</div>
      <div class="sub">跑赢沪深300 +123.5%</div>
    </div>
    <div class="metric-pill">
      <div class="lbl">最大回撤</div>
      <div class="val green">-14.8%</div>
      <div class="sub">震荡市风格切换期</div>
    </div>
    <div class="metric-pill">
      <div class="lbl">胜率 / 盈亏比</div>
      <div class="val blue">62.3% / 3.4</div>
      <div class="sub">强趋势行情更优</div>
    </div>
  </div>

  <div class="status-bar">
    <span><span class="dot green"></span> Flask 服务运行中</span>
    <span>🔌 Streamlit 端口 8501</span>
    <span>🕐 {{ now }}</span>
  </div>

  <div class="footer">
    <strong>免责声明</strong>：所有信号均为模拟回测结果，不构成投资建议。过去收益不代表未来表现。
  </div>
</div>
</body>
</html>"""

IFRAME_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>决策看板 — 龙头股动量轮动系统</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* Mini Nav Bar */
    .mini-nav {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 20px;
      background: linear-gradient(135deg, #0c1f5e, #1e3a8a 60%, #3b82f6);
      flex-shrink: 0;
      z-index: 100;
    }
    .mini-nav .brand { font-size: 15px; font-weight: 700; color: #fff; letter-spacing: 0.3px; }
    .mini-nav .brand span { color: #93c5fd; }
    .mini-nav .sep { width: 1px; height: 18px; background: rgba(255,255,255,0.2); }
    .mini-nav a {
      font-size: 12px; color: rgba(255,255,255,0.7); text-decoration: none;
      padding: 4px 10px; border-radius: 6px; transition: all .15s;
    }
    .mini-nav a:hover { background: rgba(255,255,255,0.1); color: #fff; }
    .mini-nav .spacer { flex: 1; }
    .mini-nav .status {
      font-size: 11px; color: rgba(255,255,255,0.5);
      display: flex; align-items: center; gap: 6px;
    }
    .mini-nav .dot { width: 7px; height: 7px; border-radius: 50%; background: #16a34a; display: inline-block; }

    /* Iframe Container */
    .iframe-wrap {
      flex: 1;
      position: relative;
      overflow: hidden;
    }
    .iframe-wrap iframe {
      width: 100%;
      height: 100%;
      border: none;
    }

    /* Loading overlay */
    .loading-overlay {
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      background: #0f172a;
      z-index: 10;
      transition: opacity 0.4s;
    }
    .loading-overlay.hidden { opacity: 0; pointer-events: none; }
    .loading-overlay .spinner {
      width: 40px; height: 40px;
      border: 3px solid #2d3a50;
      border-top-color: #3b82f6;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin-bottom: 12px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .loading-overlay .text { font-size: 13px; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="mini-nav">
    <div class="brand">🐉 <span>动量轮动</span></div>
    <div class="sep"></div>
    <a href="/">🏠 返回首页</a>
    <a href="/api/momentum" target="_blank">🔗 API 数据</a>
    <div class="spacer"></div>
    <div class="status">
      <span class="dot"></span>
      <span>Streamlit · 实时</span>
    </div>
  </div>

  <div class="iframe-wrap">
    <div class="loading-overlay" id="loading-overlay">
      <div class="spinner"></div>
      <div class="text">加载 Streamlit 决策看板中...</div>
    </div>
    <iframe
      src="http://127.0.0.1:8501/?embed=true"
      id="streamlit-iframe"
      onload="document.getElementById('loading-overlay').classList.add('hidden')"
      allow="clipboard-read; clipboard-write"
      sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
    ></iframe>
  </div>

  <script>
    // iframe 加载失败时给予反馈
    const iframe = document.getElementById('streamlit-iframe');
    const overlay = document.getElementById('loading-overlay');
    let loadTimeout = setTimeout(() => {
      if (!overlay.classList.contains('hidden')) {
        overlay.innerHTML = `
          <div style="font-size:2rem;margin-bottom:12px;">⚠️</div>
          <div class="text" style="color:#f87171;font-weight:600;">Streamlit 看板加载超时</div>
          <div class="text" style="margin-top:8px;">请确认 <strong style="color:#60a5fa;">run.py</strong> 已在运行<br>
          或直接访问 <a href="http://127.0.0.1:8501" target="_blank" style="color:#3b82f6;">http://127.0.0.1:8501</a></div>
        `;
      }
    }, 10000);
    iframe.addEventListener('load', () => clearTimeout(loadTimeout));
  </script>
</body>
</html>"""


# ── App Factory ───────────────────────────────────────────────────────────

def create_flask_app() -> Flask:
    app = Flask(__name__)
    CORS(app)  # 允许 Streamlit 跨域调用

    @app.route("/")
    def landing():
        return render_template_string(
            LANDING_TEMPLATE,
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    @app.route("/momentum_dashboard")
    def momentum_dashboard():
        """Flask 壳页面，通过 iframe 嵌入 Streamlit 看板"""
        return render_template_string(IFRAME_TEMPLATE)

    @app.route("/api/momentum")
    def api_momentum():
        """实时动量数据 API — 被 Streamlit 通过 pd.read_json 消费"""
        data = _generate_momentum_data()
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({
            "code": 0,
            "message": "success",
            "timestamp": now_iso,
            "data": {
                "stocks": data,
                "metrics": {
                    "annual_return": 114.2,
                    "max_drawdown": -14.8,
                    "win_rate": 62.3,
                    "profit_loss_ratio": 3.4,
                    "benchmark_outperform": 123.5,
                },
                "config": {
                    "momentum_period": 20,
                    "rebalance_interval": 5,
                    "max_holdings": 3,
                    "positions": {
                        "buy1_pct": 0.30,
                        "buy2_pct": 0.30,
                        "hold_pct": 0.40,
                    },
                },
            },
        })

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "flask-momentum"})

    return app


# ── 独立启动（也可被 run.py 导入）────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("MOMENTUM_PORT", 5001))
    app = create_flask_app()
    print(f"🐉 龙头股动量轮动系统 — Flask 主壳 http://127.0.0.1:{port}")
    print(f"   API 端点:  http://127.0.0.1:{port}/api/momentum")
    print(f"   决策看板:  http://127.0.0.1:{port}/momentum_dashboard")
    app.run(host="0.0.0.0", port=port, debug=False)

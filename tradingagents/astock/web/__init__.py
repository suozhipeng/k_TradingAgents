"""Flask Jinja2 WebUI Blueprint — Phase 17.

Provides 9 pages with Tailwind CSS (dark theme) that consume the Flask REST
API at ``/api/v1/`` via client-side ``fetch()``.
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, redirect, render_template, render_template_string, request

bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/web/static",
)

# ── iframe 嵌入模板（嵌入 Streamlit 决策看板） ─────────────────────────

IFRAME_TEMPLATE = """<!DOCTYPE html>
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
      background: #0f172a; color: #e2e8f0;
      height: 100vh; display: flex; flex-direction: column; overflow: hidden;
    }
    .mini-nav {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 20px;
      background: linear-gradient(135deg, #0c1f5e, #1e3a8a 60%, #3b82f6);
      flex-shrink: 0; z-index: 100;
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
    .mini-nav .status { font-size: 11px; color: rgba(255,255,255,0.5); display: flex; align-items: center; gap: 6px; }
    .mini-nav .dot { width: 7px; height: 7px; border-radius: 50%; background: #16a34a; display: inline-block; }
    .iframe-wrap { flex: 1; position: relative; overflow: hidden; }
    .iframe-wrap iframe { width: 100%; height: 100%; border: none; }
    .loading-overlay {
      position: absolute; inset: 0;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      background: #0f172a; z-index: 10; transition: opacity 0.4s;
    }
    .loading-overlay.hidden { opacity: 0; pointer-events: none; }
    .loading-overlay .spinner {
      width: 40px; height: 40px;
      border: 3px solid #2d3a50; border-top-color: #3b82f6;
      border-radius: 50%; animation: spin 0.8s linear infinite; margin-bottom: 12px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .loading-overlay .text { font-size: 13px; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="mini-nav">
    <div class="brand">🐉 <span>动量轮动</span></div>
    <div class="sep"></div>
    <a href="/momentum_standalone">📋 经典版</a>
    <a href="/api/v1/momentum" target="_blank">🔗 API 数据</a>
    <div class="spacer"></div>
    <div class="status"><span class="dot"></span><span>Streamlit · 实时</span></div>
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
    const iframe = document.getElementById('streamlit-iframe');
    const overlay = document.getElementById('loading-overlay');
    let loadTimeout = setTimeout(() => {
      if (!overlay.classList.contains('hidden')) {
        overlay.innerHTML = `
          <div style="font-size:2rem;margin-bottom:12px;">\\u26a0\\ufe0f</div>
          <div class="text" style="color:#f87171;font-weight:600;">Streamlit \\u770b\\u677f\\u52a0\\u8f7d\\u8d85\\u65f6</div>
          <div class="text" style="margin-top:8px;">\\u8bf7\\u786e\\u8ba4 <strong style="color:#60a5fa;">streamlit_app.py</strong> \\u5df2\\u5728\\u8fd0\\u884c<br>
          \\u6216\\u76f4\\u63a5\\u8bbf\\u95ee <a href="http://127.0.0.1:8501" target="_blank" style="color:#3b82f6;">http://127.0.0.1:8501</a></div>
        `;
      }
    }, 10000);
    iframe.addEventListener('load', () => clearTimeout(loadTimeout));
  </script>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@bp.route("/")
def root():
    return redirect("/dashboard", 302)


@bp.route("/trading")
def trading() -> str:
    return render_template("trading.html")


@bp.route("/dashboard")
def dashboard() -> str:
    return render_template("dashboard.html")


@bp.route("/research")
def research() -> str:
    return render_template("research.html")


@bp.route("/strategy_hub")
def strategy_hub() -> str:
    """三位一体策略研究控制台"""
    return render_template("strategy_hub.html")


@bp.route("/strategies")
def strategies() -> str:
    return render_template("strategies.html")


@bp.route("/paper")
def paper() -> str:
    return render_template("paper.html")


@bp.route("/qmt")
def qmt() -> str:
    return render_template("qmt.html")


@bp.route("/risk")
def risk() -> str:
    return render_template("risk.html")


@bp.route("/reports")
def reports() -> str:
    return render_template("reports.html")


@bp.route("/watchlist")
def watchlist_page() -> str:
    """自选股管理页面"""
    return render_template("watchlist.html")


@bp.route("/batch-analyze")
def batch_analyze_page() -> str:
    """批量分析入口"""
    return render_template("watchlist.html", batch_mode=True)


@bp.route("/settings")
def settings() -> str:
    return render_template("settings.html")


@bp.route("/settings/notifications")
def settings_notifications() -> str:
    """通知设置专用页面"""
    return render_template("settings.html", section="notifications")


@bp.route("/screener")
def screener() -> str:
    return render_template("screener.html")


@bp.route("/dragon_tiger")
def dragon_tiger() -> str:
    """旧入口 — 已迁移到 /market_leaders"""
    return render_template("dragon_tiger.html", today=datetime.now().strftime("%Y-%m-%d"),
                           legacy_redirect="/market_leaders")


@bp.route("/sectors")
def sectors() -> str:
    """旧入口 — 已迁移到 /market_leaders"""
    return render_template("sectors.html", legacy_redirect="/market_leaders")


@bp.route("/northbound")
def northbound() -> str:
    """旧入口 — 已迁移到 /market_leaders"""
    return render_template("northbound.html", legacy_redirect="/market_leaders")


@bp.route("/data_health")
def data_health() -> str:
    return render_template("data_health.html")


@bp.route("/tv_chart")
def tv_chart() -> str:
    symbol = request.args.get("symbol", "600519.SH")
    return render_template("tv_chart.html", symbol=symbol)


@bp.route("/kc_chart")
def kc_chart() -> str:
    symbol = request.args.get("symbol", "600519.SH")
    standalone = request.args.get("standalone", "0") == "1"
    return render_template("kc_chart.html", symbol=symbol, standalone=standalone)


@bp.route("/momentum_rotation")
def momentum_rotation() -> str:
    """旧入口 — 已迁移到 /market_leaders"""
    return render_template("momentum_rotation.html", legacy_redirect="/market_leaders")


@bp.route("/market_leaders")
def market_leaders() -> str:
    """统一市场龙头入口（整合龙头/板块/资金/轮动/龙虎榜）"""
    return render_template("market_leaders.html")


@bp.route("/momentum_dashboard")
def momentum_dashboard() -> str:
    """旧入口 — 已迁移到 /market_leaders"""
    return render_template("momentum_dashboard.html", legacy_redirect="/market_leaders")


@bp.route("/momentum_standalone")
def momentum_standalone() -> str:
    """经典 Jinja2 版决策看板（无 Streamlit 依赖）"""
    return render_template("momentum_dashboard.html", legacy_redirect="/market_leaders")


@bp.route("/portfolio")
def portfolio() -> str:
    """组合工作台"""
    return render_template("portfolio.html")


@bp.route("/ops_audit")
def ops_audit() -> str:
    """运维审计面板"""
    return render_template("ops_audit.html")


@bp.route("/ai_agent")
def ai_agent() -> str:
    return render_template("ai_agent.html")


# ---------------------------------------------------------------------------
# Old entry redirects (Phase 34-01)
# ---------------------------------------------------------------------------


@bp.route("/backtest")
def backtest_console() -> str:
    """AStock Pro 三位一体策略研究控制台（全新推平重建版）"""
    return render_template("backtest.html")


@bp.route("/comparison")
@bp.route("/compare")
def comparison_redirect() -> str:
    """Old /comparison → /strategy_hub"""
    from flask import redirect, url_for
    return redirect(url_for("web.strategy_hub"), 301)


@bp.route("/performance")
def performance_redirect() -> str:
    """Old /performance → /strategy_hub"""
    from flask import redirect, url_for
    return redirect(url_for("web.strategy_hub"), 301)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = ["bp"]

# Phase 36 — Portfolio Risk & Attribution (Evidence)

## 代码实装

### Portfolio/Risk/Attribution schema
- **文件**: `tradingagents/astock/schemas/portfolio.py`
- **类**: Portfolio, RiskExposure, Attribution (Pydantic)
- **Commit**: `5c828f7`

### Portfolio risk 计算引擎
- **文件**: `tradingagents/astock/execution/portfolio_risk.py`
- **函数**:
  - `calculate_var()` — VaR 95% 参数化计算 (NormalDist)
  - `calculate_industry_exposure()` — 行业暴露分析（含 HHI 集中度）
  - `calculate_attribution()` — Brinson 归因（selection + timing + cost + slippage）
  - `calculate_risk_exposure()` — 聚合风险暴露（VaR + 集中度 + 流动 + 压力测试 2.5x）
- **Commit**: `5c828f7`

### API 路由
- **文件**: `tradingagents/astock/api/routes_portfolio.py`
- **Blueprint**: "portfolio", url_prefix="/api/v1"
- **端点**:
  - `GET /api/v1/portfolio/risk` — 返回 RiskExposure JSON
  - `GET /api/v1/portfolio/attribution` — 返回 Attribution JSON
- **注册**: `api/__init__.py` line 114
- **Commit**: `5c828f7`

### 前端页面
- **模板**: `portfolio.html`
- **内容**: 组合风险仪表盘（VaR 卡片、行业暴露、集中度图、Brinson 归因表）

## 测试结果

```bash
# Phase 33-38 schema 验证（含 Portfolio/RiskExposure/Attribution）
pytest tests/test_astock_phases_33_38.py -q
→ 26 passed in 0.05s

# API 完整性验证
pytest tests/test_astock_api.py -q
→ 162 包含 portfolio 路由覆盖
```

## 完成标准判定

| 验收项 | 判定 | 证据 |
|--------|------|------|
| 组合风险 schema 可复用回测和 paper 状态 | ✅ 完成 | Position schema 来自 trading_execution，可跨模块复用 |
| 风险暴露/VaR/压力测试字段明确 | ✅ 完成 | `portfolio_risk.py` 含全部计算实现 |
| Brinson 归因字段明确 | ✅ 完成 | selection/timing/cost/slippage/residual |
| 前台 Portfolio Workbench 有页面 | ✅ 完成 | `portfolio.html` + API endpoints |
| API 合约明确定义 | ✅ 完成 | `routes_portfolio.py` 显式定义 |

---

**Commit SHA**: `5c828f7` + `b410074`

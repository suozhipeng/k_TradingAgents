# Phase 36 Portfolio Risk & Attribution 需求与 Hermes 任务包

| 状态：完成 | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 32：BacktestResult schema、Strategy Registry（组合风险需要复用回测结果）
- Phase 35：Order/Position/Fill schema、reconciliation（组合状态需要订单和持仓数据）

## 1. Phase 目标

从单股/单策略升级到组合级风险和绩效归因，复用 Strategy Lab 回测结果与 Trading/Paper 状态。

## 2. 范围

后台模块：

- `tradingagents/astock/execution/metrics.py`
- `routes_dashboard.py`
- future portfolio API module

前台模块：

- future `portfolio.html`
- Dashboard 风险摘要
- Strategy Lab / Trading 组合风险入口

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 36-01 | 定义 Portfolio schema。 | API contracts、data dictionary。 | holdings/cash/nav 字段明确。 |
| 36-02 | 定义 RiskExposure schema。 | API contracts、data dictionary。 | industry/concentration/beta/liquidity 字段明确。 |
| 36-03 | 定义 Attribution schema。 | API contracts、data dictionary。 | benchmark/selection/timing/cost/slippage 明确。 |
| 36-04 | 梳理回测结果复用字段。 | data dictionary。 | 可接 Strategy Lab。 |
| 36-05 | 梳理 paper 状态复用字段。 | data dictionary。 | 可接 Trading。 |
| 36-06 | 画 Portfolio Workbench 效果图。 | progress plan / WebUI spec。 | 风险+归因页面结构明确。 |
| 36-07 | 定义页面输入输出。 | WebUI checklist。 | 输入/输出明确。 |
| 36-08 | 定义压力测试指标。 | metrics/Ops、API contracts。 | VaR/DD/stress 字段明确。 |
| 36-09 | 补测试计划。 | test plan。 | 单元+API slice 覆盖面明确。 |
| 36-10 | 更新追踪矩阵状态。 | traceability matrix。 | PROD-07 有证据路径。 |

## 4. 测试命令

```bash
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_paper_trader.py -q
pytest tests/test_astock_api.py -q
```
---
**Commit SHA**: `22f2a71` (Phase 36 portfolio page), incremental in `e33b362`

## 5. 完成标准

- 组合风险 schema 可复用回测和 paper 状态。
- 风险暴露、VaR、压力测试、归因字段明确。
- 前台 Portfolio Workbench 有页面验收清单。

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-36-evidence-portfolio-risk.md`

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

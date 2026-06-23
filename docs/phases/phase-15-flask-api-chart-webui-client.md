# Phase 15：Flask REST API + Chart.js + WebUI API Client

## 元数据

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-15`
- Owner: `Hermes`
- Branch: `xg_dev`
- Commit SHA: `eff5d24`

## 产品目标

为 A 股 WebUI 提供 Flask REST API、Chart.js 图表和前端 API client，使回测、行情、策略和执行状态可以通过 WebUI 消费。

## 范围

### 包含

- Flask REST API 端点扩展。
- Chart.js 图表集成。
- WebUI API client。
- KlineChart / BacktestChart 能力。
- API 测试和 Codex review。

### 排除

- 不引入真实券商下单。
- 不改变 Phase 14 策略逻辑。
- 不负责后续批量回测调度和 SSE；该能力归 Phase 16。

## 实现证据

提交 `eff5d24`：`Phase 15: Flask REST API + Chart.js + WebUI API client — 19 endpoints, KlineChart, BacktestChart, 28 tests, Codex accept`

涉及文件包括：

- `tradingagents/astock/api/__init__.py`
- `tradingagents/astock/api/routes_backtest.py`
- `tradingagents/astock/api/routes_data.py`
- `tradingagents/astock/api/routes_market.py`
- `tradingagents/astock/api/routes_paper.py`
- `tradingagents/astock/api/routes_qmt.py`

## 验收

- REST API 端点：19 个
- 测试：28 tests
- Codex review：`accept`

## 风险与缺口

- 后续 API 能力等级需要继续标注 `research` / `paper` / `managed` / `live-ready`。
- 后续 Data & Ops 应统一 provider、缓存和刷新任务状态。

## 下一入口条件

进入 Phase 16 批量回测、市场分析器、调度器和 SSE。

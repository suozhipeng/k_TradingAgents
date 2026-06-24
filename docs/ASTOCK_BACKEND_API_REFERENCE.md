# A 股后台 API 文档

| 更新时间：2026-06-24 |

本文梳理 TradingAgents-Astock 当前后台 API、所属模块、数据源、能力等级、真实/模拟边界和测试验收。`docs/ASTOCK_API_CONTRACTS.md` 定义 API 规范；本文列出现有与 Phase 30-38 目标 API 清单。

## 1. API 通用约定

- 基础前缀：`/api/v1`
- 能力等级：`research` / `paper` / `managed` / `live-ready` / `mock`

## 2. 请求/响应示例

### 2.1 K 线查询

**请求：**
```bash
curl -X GET "http://localhost:8080/api/v1/kline?symbol=600519.SH&start=2025-01-01&end=2025-06-01&interval=1d"
```

**响应：**
```json
{
  "success": true,
  "data": {
    "bars": [
      {"date": "2025-01-02", "open": 1700.5, "high": 1720.0, "low": 1695.0, "close": 1715.3, "volume": 12345, "provider": "mootdx"}
    ]
  },
  "error": null,
  "meta": {
    "capability": "research",
    "source": "provider",
    "request_id": "abc-123",
    "generated_at": "2026-06-25T10:00:00Z",
    "freshness": "ok",
    "quality": "ok"
  }
}
```

### 2.2 AI 分析

**请求：**
```bash
curl -X POST "http://localhost:8080/api/v1/ai/analyze" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH", "mode": "live_research", "date": "2025-06-01"}'
```

**响应：**
```json
{
  "success": true,
  "data": {
    "task_id": "task-xyz-789",
    "status": "completed",
    "report": {
      "research_conclusion": {...},
      "trader_proposal": {...},
      "risk_decision": {...},
      "portfolio_decision": {...}
    }
  },
  "error": null,
  "meta": {
    "capability": "research",
    "source": "provider",
    "request_id": "def-456",
    "generated_at": "2026-06-25T10:05:00Z",
    "model": "deepseek-v4-flash",
    "advisory_only": true
  }
}
```

### 2.3 回测运行

**请求：**
```bash
curl -X POST "http://localhost:8080/api/v1/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{"strategy": "macd_trend", "symbol": "600519.SH", "start": "2024-01-01", "end": "2025-06-01", "params": {"fast": 12, "slow": 26, "signal": 9}}'
```

**响应：**
```json
{
  "success": true,
  "data": {
    "result_id": "bt-001",
    "metrics": {"return": 0.15, "sharpe": 1.2, "drawdown": -0.08},
    "data_assumption": {"adjust": "qfq", "cost_model": {...}, "t_plus_1": true}
  },
  "error": null,
  "meta": {
    "capability": "research",
    "source": "duckdb",
    "request_id": "ghi-789",
    "generated_at": "2026-06-25T10:10:00Z"
  }
}
```

### 2.4 错误响应

**请求：**
```bash
curl -X GET "http://localhost:8080/api/v1/kline?symbol=INVALID&start=2025-01-01"
```

**响应：**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "symbol is not a valid A-share code",
    "category": "validation",
    "retryable": false,
    "details": {"provided": "INVALID"}
  },
  "meta": {
    "capability": "research",
    "request_id": "err-001",
    "generated_at": "2026-06-25T10:15:00Z"
  }
}
```
- 当前不把 QMT 相关接口纳入真实数据源要求。
- 数据类 API 必须逐步补齐：`source`、`provider`、`freshness`、`quality`、`fallback_path`、`snapshot_id`。
- 长任务类 API 必须逐步补齐：`task_id`、`status`、`progress`、`audit_event_id`。

## 3. Health / Dashboard

| API | Method | 模块 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/health` | GET | Core Runtime | research | Flask app state | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/dashboard/overview` | GET | Dashboard / Ops | research / paper | DuckDB、PaperTrader、回测结果 | 已实现 | `tests/test_astock_api.py`, `tests/test_astock_web.py` |

目标补充：

- 返回 capability、degraded services、latest task、latest audit summary。
- Dashboard 不显示为 live-ready。

## 4. Data & Ops API

| API | Method | 功能 | 能力 | 真实数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/kline` | GET | K 线 | research | DuckDB 优先；mootdx live fallback；历史可走 akshare/baostock/Tencent router | 已实现 | `tests/test_astock_api.py`, `tests/test_astock_data_sources.py` |
| `/api/v1/valuation` | GET | 估值 | research | Tencent 优先，akshare fallback，mootdx 补充 | 已实现 | `tests/test_astock_api.py`, `tests/test_astock_data_sources.py` |
| `/api/v1/orderbook` | GET | 盘口 | research | mootdx / Tencent | 已实现 | `tests/test_astock_data_sources.py` |
| `/api/v1/trade_tape` | GET | 分笔 | research | mootdx / Tencent | 已实现 | `tests/test_astock_data_sources.py` |
| `/api/v1/news` | GET | 新闻 | research | akshare、东方财富、Sina、Tencent | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/news/live` | GET | 实时新闻 | research | 东方财富、Sina、同花顺口径 provider | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/news/stock` | GET | 个股新闻 | research | akshare.stock_news_em / 东方财富 | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/research` | GET | 研报列表 | research | iwencai、akshare、东方财富 | 已实现 | `tests/test_astock_provider_fixtures.py` |
| `/api/v1/research/pdf` | GET | 研报 PDF | research | iwencai、akshare | 已实现 | live guard |
| `/api/v1/research/expectation` | GET | 一致预期 | research | iwencai、akshare、mootdx | 已实现 | provider tests |
| `/api/v1/research/search` | GET | 研报搜索 | research | iwencai、akshare | 已实现 | provider tests |
| `/api/v1/fundamentals` | GET | 基本面 | research | akshare、mootdx | 已实现 | `tests/test_astock_interface_analyst.py` |
| `/api/v1/f10` | GET | F10 | research | mootdx、akshare | 已实现 | `tests/test_astock_interface_analyst.py` |
| `/api/v1/announcements` | GET | 公告 | research | cninfo、mootdx | 已实现 | `tests/test_astock_data_sources.py` |
| `/api/v1/store/stats` | GET | Store stats | research | DuckDB | 已实现 | `tests/test_astock_store.py` |
| `/api/v1/data/refresh/kline` | POST | 刷新 K 线 | research | provider -> DuckDB | 已实现 | `tests/test_astock_store.py`, `tests/test_astock_api.py` |
| `/api/v1/data/refresh/valuation` | POST | 刷新估值 | research | provider -> DuckDB | 已实现 | `tests/test_astock_store.py`, `tests/test_astock_api.py` |
| `/api/v1/data/refresh/all` | POST | 刷新全部 | research | provider -> DuckDB | 已实现 | `tests/test_astock_store.py`, `tests/test_astock_api.py` |
| `/api/v1/cache/status` | GET | 缓存状态 | research | local cache | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/cache/clear` | POST | 清理缓存 | research | local cache | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/data/health` | GET | 数据健康 | research | akshare、Tencent、mootdx、iwencai、EastMoney 探测 | 已实现 | `tests/test_astock_web.py` |

核心请求参数：

- `symbol`：A 股代码，例如 `600519.SH`。
- `start` / `end`：日期。
- `interval`：K 线周期。
- `limit`：返回条数。
- `source`：可选 provider。

目标补充：

- Phase 31：统一返回 `DataQualityTag` 和 `BacktestDataAssumption`。
- Phase 37：刷新任务返回 `TaskRun`。

## 5. TradingView / KLine API

| API | Method | 功能 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/tv/stock-search` | GET | 股票搜索 | research | mootdx stock list | 已实现 | `tests/test_astock_tv_routes.py` |
| `/api/v1/tv/stock-info` | GET | 股票信息 | research | Tencent valuation、mootdx F10 | 已实现 | `tests/test_astock_tv_routes.py` |
| `/api/v1/tv/symbols` | GET | TV symbol resolve | research | stock list / router | 已实现 | `tests/test_astock_tv_routes.py` |
| `/api/v1/tv/history` | GET | TV history datafeed | research | DuckDB、mootdx fallback | 已实现 | `tests/test_astock_tv_routes.py` |

目标补充：

- 返回数据延迟、fallback、复权口径。
- KLine 页面显示 data quality 标签。

## 6. Strategy Lab API

| API | Method | 功能 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/backtest/run` | POST | 运行回测 | research / paper | DuckDB / provider K 线 | 已实现 | `tests/test_astock_backtest.py`, `tests/test_astock_api.py` |
| `/api/v1/backtest/results` | GET | 查询回测结果 | research | store / memory | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/backtest/results` | DELETE | 清理回测结果 | research | store / memory | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/backtest/results/<run_id>` | DELETE | 删除单次结果 | research | store / memory | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/backtest/compare` | GET | 策略对比 | research | 回测结果 | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/backtest/analyze` | POST | 回测分析 | research | 回测结果 | 已实现 | `tests/test_astock_backtest.py` |
| `/api/v1/backtest/optimize` | POST | 参数优化 | research | provider K 线 + optimizer | 已实现 | `tests/test_astock_optimizer.py` |
| `/api/v1/market/strategies` | GET | 策略列表 | research | strategy registry | 已实现 | `tests/test_astock_api.py` |

目标补充：

- Phase 32：统一 `StrategyRegistry`、`BacktestResult`、`OptimizeResult` schema。
- 回测结果必须包含 benchmark、成本模型、数据假设和反偏差状态。

## 7. Market Leaders API

| API | Method | 功能 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/market/summary` | GET | 市场摘要 | research | DuckDB / provider | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/market/screener` | GET | 股票筛选 | research | DuckDB K 线 / 指标计算 | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/market/dragon-tiger` | GET | 龙虎榜 | research | EastMoney，mock 兜底 | 已实现 | `tests/test_astock_api.py`, `tests/test_astock_web.py` |
| `/api/v1/market/sectors` | GET | 板块强弱 | research | EastMoney -> Sina fallback -> mock | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/market/northbound` | GET | 北向资金 | research | EastMoney，mock 兜底 | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/market/blocks` | GET | 个股板块 | research | EastMoney，mock 兜底 | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/market/momentum-rotation` | POST | 动量轮动 | research | EastMoney 龙头池、akshare、DuckDB | 已实现 | `tests/test_astock_web.py`, `tests/test_astock_api.py` |
| `/api/v1/market/momentum` | GET | 动量实时 | research | EastMoney 龙头池、akshare / local kline | 已实现 | `tests/test_astock_web.py` |

目标补充：

- Phase 34：统一 `LeaderPool` schema。
- mock fallback 必须进入 `meta.source=mock` 或页面显著标签。

## 8. AI Research API

| API | Method | 功能 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/ai/analyze` | POST | AI 分析 | research | kline、valuation、news、fundamentals、LLM provider | 已实现基础版 | `tests/test_astock_web.py`, `tests/test_astock_graph_runtime.py` |
| `/api/v1/reports/pptx` | GET | PPT 报告 | research | report payload | 已实现 | `tests/test_astock_ppt.py` |

目标 API：

| API | Method | 功能 | 能力 | Phase |
|---|---|---|---|---|
| `/api/v1/research/tasks` | POST | 创建研究任务 | research | 33 |
| `/api/v1/research/tasks/<task_id>` | GET | 查询研究任务 | research | 33 |
| `/api/v1/research/tasks/<task_id>` | DELETE | 取消/删除研究任务 | research | 33 |
| `/api/v1/research/audit/<task_id>` | GET | 查询模型/prompt/数据快照审计 | research | 33 |

目标补充：

- 返回 model provider、model name、prompt version、input snapshot ids、advisory-only 标记。

## 9. Paper / Trading / QMT API

| API | Method | 功能 | 能力 | 数据源 / 状态源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/paper/cycle` | POST | 模拟盘周期 | paper | PaperTrader + 策略/行情 | 已实现 | `tests/test_astock_paper_trader.py` |
| `/api/v1/paper/state` | GET | 模拟盘状态 | paper | PaperTrader | 已实现 | `tests/test_astock_paper_trader.py` |
| `/api/v1/paper/trades` | GET | 模拟盘交易 | paper | PaperTrader | 已实现 | `tests/test_astock_paper_trader.py` |
| `/api/v1/trade/order` | POST | 下单入口 | paper / managed | PaperTrader / managed bridge | 已实现，需强化 capability | `tests/test_astock_api.py` |
| `/api/v1/trade/quote` | GET | 实时报价 | research / paper | Sina -> EastMoney -> cache | 已实现 | `tests/test_astock_api.py` |
| `/api/v1/trade/state` | GET | 交易状态 | paper | PaperTrader + live quote 估值 | 已实现，非真实账户 | `tests/test_astock_api.py` |
| `/api/v1/qmt/health` | GET | QMT 健康 | managed | QMT bridge / mock-read-only | 已实现 | `tests/test_astock_qmt_bridge.py` |
| `/api/v1/qmt/positions` | GET | QMT 持仓 | managed | QMT bridge / read-only | 已实现 | `tests/test_astock_qmt_bridge.py` |
| `/api/v1/qmt/orders` | GET | QMT 订单 | managed / mock | 当前仍需能力口径收口 | 已实现但需 Phase 30/35 修正 | `tests/test_astock_qmt_execution.py` |

目标补充：

- Phase 30：所有交易 API 返回 capability、risk_status、confirmation_status。
- Phase 35：补 Order / Fill / Position / Reconciliation schema。
- QMT 真实数据不纳入本文真实数据源要求。

## 10. SSE / Ops API

| API | Method | 功能 | 能力 | 数据源 | 当前状态 | 测试 |
|---|---|---|---|---|---|---|
| `/api/v1/sse/paper-progress` | GET | paper 进度流 | paper | event bus | 已实现 | `tests/test_astock_sse.py` |
| `/api/v1/sse/events` | GET | 事件列表 | research / paper | event bus | 已实现 | `tests/test_astock_sse.py` |
| `/api/v1/sse/events` | DELETE | 清理事件 | research / paper | event bus | 已实现 | `tests/test_astock_sse.py` |

目标 API：

| API | Method | 功能 | 能力 | Phase |
|---|---|---|---|---|
| `/api/v1/tasks` | GET | 查询任务列表 | research / paper | 37 |
| `/api/v1/tasks/<task_id>` | GET | 查询任务详情 | research / paper | 37 |
| `/api/v1/audit/events` | GET | 查询审计事件 | research / paper / managed | 37 |
| `/api/v1/audit/events/<event_id>` | GET | 查询审计详情 | research / paper / managed | 37 |

## 11. 验收矩阵

| API 类别 | 必跑测试 | Phase |
|---|---|---|
| Data & Ops | `tests/test_astock_data_sources.py`, `tests/test_astock_api.py`, `tests/test_astock_tv_routes.py` | 31 |
| Strategy Lab | `tests/test_astock_strategies.py`, `tests/test_astock_backtest.py`, `tests/test_astock_optimizer.py`, `tests/test_astock_api.py` | 32 |
| AI Research | `tests/test_astock_graph_runtime.py`, `tests/test_astock_graph_bridge.py`, `tests/test_astock_ppt.py`, `tests/test_astock_web.py` | 33 |
| Market Leaders | `tests/test_astock_web.py`, `tests/test_astock_api.py` | 34 |
| Trading & Execution | `tests/test_astock_paper_trader.py`, `tests/test_astock_execution_risk_gate.py`, `tests/test_astock_qmt_execution.py` | 30/35 |
| Ops & Audit | `tests/test_astock_sse.py`, `tests/test_astock_api.py`, `tests/test_astock_web.py` | 37 |

## 12. 更新规则

- 新增 endpoint 必须同步本文和 `docs/ASTOCK_API_CONTRACTS.md`。
- 数据源变化必须同步 `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`。
- schema 变化必须同步 `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`。
- 页面依赖 API 变化必须同步 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`。
- Hermes 执行任务时必须把 API 变化写入对应 phase 文档。

# A-Stock API 端点参考

> 自动生成于代码（`scripts/gen_api_reference.py`），更新于 2026-07-15。以实际代码为准。

> 共 **131** 个端点（含 HTTP 方法变体，对应 **120** 个唯一路径），覆盖 **28** 个路由模块。


## `routes_admin.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/admin/backend` | Return current backend status. |
| `POST` | `/api/v1/admin/backend` | Switch database backend at runtime. |
| `GET` | `/api/v1/admin/backend/config` | Return current backend configuration (passwords masked). |
| `POST` | `/api/v1/admin/health/sync-ch` | Trigger a ClickHouse sync for the currently active backend. |
| `GET` | `/api/v1/admin/mock-data` | Return the process-wide mock-data switch. |
| `PUT` | `/api/v1/admin/mock-data` | Enable or disable process-wide mock data and persist the setting. |

## `routes_ai_agent.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/ai/analyze` | Run AI agent analysis on one or more stock symbols. |

## `routes_alerts.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/alerts` | Return open / recent alert events. |
| `POST` | `/api/v1/alerts` | Create a direct alert event (not rule-triggered). |
| `POST` | `/api/v1/alerts/<alert_id>/ack` | Mark an alert as acknowledged. |
| `GET` | `/api/v1/alerts/check` | Check all enabled rules against current market data. |
| `GET` | `/api/v1/alerts/rules` | List all alert rules (optionally only enabled ones). |
| `POST` | `/api/v1/alerts/rules` | Create a new alert rule. |
| `PATCH` | `/api/v1/alerts/rules/<rule_id>` | Update fields on an existing alert rule. |
| `DELETE` | `/api/v1/alerts/rules/<rule_id>` | Delete an alert rule (and its events). |

## `routes_analysis.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/analysis/watchlist` | (无描述) |

## `routes_backtest.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/backtest/analyze` | POST /api/v1/backtest/analyze |
| `GET` | `/api/v1/backtest/compare` | Multi-strategy comparison. |
| `GET` | `/api/v1/backtest/history` | Query historical backtest results. |
| `POST` | `/api/v1/backtest/optimize` | POST /api/v1/backtest/optimize |
| `GET` | `/api/v1/backtest/results` | Query historical backtest results. |
| `DELETE` | `/api/v1/backtest/results` | Delete all stored backtest results. |
| `DELETE` | `/api/v1/backtest/results/<run_id>` | Delete a single backtest result by run_id. |
| `POST` | `/api/v1/backtest/run` | Run a single backtest. |
| `POST` | `/api/v1/backtest/walkforward` | Run Walk-Forward Analysis and return results + summary. |

## `routes_daily.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/daily/review` | Aggregate daily market review for major A-share indexes. |

## `routes_dashboard.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/dashboard/overview` | (无描述) |

## `routes_data_cache.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/cache/clear` | (无描述) |
| `GET` | `/api/v1/cache/status` | (无描述) |

## `routes_data_health.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/data/health` | Probe all registered data source adapters. |

## `routes_data_ingest.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/data/lifecycle/intraday` | Preview or explicitly archive old minute K-lines into Parquet. |
| `POST` | `/api/v1/data/maintenance` | Checkpoint and analyze the hot and canonical local DuckDB stores. |
| `POST` | `/api/v1/data/manual/<table_name>` | (无描述) |
| `POST` | `/api/v1/data/refresh/all` | (无描述) |
| `POST` | `/api/v1/data/refresh/kline` | (无描述) |
| `POST` | `/api/v1/data/refresh/valuation` | (无描述) |

## `routes_data_jobs.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/data/jobs` | (无描述) |
| `GET` | `/api/v1/data/jobs/<job_id>` | (无描述) |
| `POST` | `/api/v1/data/jobs/import-database` | (无描述) |
| `POST` | `/api/v1/data/jobs/refresh` | (无描述) |
| `GET` | `/api/v1/data/refresh/options` | Return the server-owned contract for the Data Hub refresh form. |

## `routes_health.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/health` | Return readiness for load balancers and dependent API traffic. |
| `GET` | `/api/v1/health/live` | Return process liveness without touching external dependencies. |
| `GET` | `/api/v1/health/ready` | Return readiness for load balancers and dependent API traffic. |

## `routes_market.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/recap` | Generate a structured daily market recap report. |
| `POST` | `/api/v1/market/recap` | Generate a structured daily market recap report. |
| `GET` | `/api/v1/market/regime` | 实时市场状态分析（4 维度）。 |
| `GET` | `/api/v1/market/strategies` | Return the list of available backtest strategies. |
| `GET` | `/api/v1/market/summary` | Composite market snapshot for a symbol. |

## `routes_market_data.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/calendar` | Return trading days in the requested range. |
| `GET` | `/api/v1/market/blocks` | Concept / industry / region blocks a stock belongs to. |
| `GET` | `/api/v1/market/dragon-tiger` | Fetch daily dragon & tiger board. |
| `GET` | `/api/v1/market/leading-pool` | Get the cached leading stock pool summary (read-only). |
| `POST` | `/api/v1/market/leading-pool/refresh` | Refresh the leading pool; POST keeps this provider write behind auth. |
| `GET` | `/api/v1/market/momentum` | Return live momentum data for leading stocks. |
| `POST` | `/api/v1/market/momentum-rotation` | Run leading stock momentum rotation backtest. |
| `GET` | `/api/v1/market/northbound` | Shanghai / Shenzhen Stock Connect real-time flow. |
| `GET` | `/api/v1/market/overview` | Market summary with real-time indices and sector performance. |
| `GET` | `/api/v1/market/quote` | Research-market quote: delegates to trade quote's live/fetch logic. |
| `GET` | `/api/v1/market/sectors` | Industry sector ranking with unified fallback handling. |

## `routes_market_data_query.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/announcements` | (无描述) |
| `GET` | `/api/v1/market/f10` | (无描述) |
| `GET` | `/api/v1/market/fundamentals` | (无描述) |
| `GET` | `/api/v1/market/kline` | (无描述) |
| `GET` | `/api/v1/market/news` | (无描述) |
| `GET` | `/api/v1/market/news/live` | (无描述) |
| `GET` | `/api/v1/market/news/stock` | (无描述) |
| `GET` | `/api/v1/market/orderbook` | (无描述) |
| `GET` | `/api/v1/market/research` | (无描述) |
| `GET` | `/api/v1/market/research/expectation` | (无描述) |
| `GET` | `/api/v1/market/research/pdf` | (无描述) |
| `GET` | `/api/v1/market/research/search` | (无描述) |
| `GET` | `/api/v1/market/store/stats` | (无描述) |
| `GET` | `/api/v1/market/trade_tape` | (无描述) |
| `GET` | `/api/v1/market/valuation` | (无描述) |

## `routes_notifications.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/notifications/consumer/start` | Start the notification consumer thread. |
| `POST` | `/api/v1/notifications/consumer/stop` | Stop the notification consumer thread. |
| `POST` | `/api/v1/notifications/desktop` | Send a desktop notification (for testing). |
| `POST` | `/api/v1/notifications/dingtalk` | Send a DingTalk webhook notification directly. |
| `GET` | `/api/v1/notifications/dispatchers` | List configured notification channels. |
| `POST` | `/api/v1/notifications/dispatchers` | Register a notification channel. |
| `PUT` | `/api/v1/notifications/dispatchers/<name>` | Update a notification channel. |
| `DELETE` | `/api/v1/notifications/dispatchers/<name>` | Delete a notification channel by name. |
| `POST` | `/api/v1/notifications/email` | Send a test email notification. |
| `GET` | `/api/v1/notifications/events` | Return recent filtered events from the EventBus ring buffer. |
| `POST` | `/api/v1/notifications/test-webhook` | Test a webhook URL by sending a test payload. |

## `routes_ops.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/ops/audit` | List audit events with optional filters. |
| `GET` | `/api/v1/ops/metrics` | Return request counts/latency plus in-process data-job state. |
| `GET` | `/api/v1/ops/scheduler/status` | Return scheduler lifecycle status from EventBus and AuditStore. |
| `GET` | `/api/v1/ops/stats` | Get aggregated ops dashboard statistics. |
| `GET` | `/api/v1/ops/tasks` | List task runs with optional type filter. |
| `GET` | `/api/v1/ops/tasks/<task_id>` | Get a single task by ID. |
| `POST` | `/api/v1/ops/tasks/<task_id>/cancel` | Cancel an existing task. |

## `routes_paper.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/paper/cycle` | (无描述) |
| `GET` | `/api/v1/paper/state` | (无描述) |
| `GET` | `/api/v1/paper/trades` | (无描述) |

## `routes_portfolio.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/portfolio/attribution` | (无描述) |
| `GET` | `/api/v1/portfolio/risk` | (无描述) |

## `routes_qmt.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/qmt/health` | QMT bridge health check. |
| `GET` | `/api/v1/qmt/orders` | QMT account snapshot (read-only, mock only). |
| `GET` | `/api/v1/qmt/positions` | QMT current positions (read-only, mock by default). |

## `routes_reports.py`

| Method | Path | 说明 |
|--------|------|------|
| `PATCH` | `/api/v1/reports/<report_id>/audit` | Add an AI audit result to an archived report. |
| `POST` | `/api/v1/reports/compare` | Compare two archived reports and return a structured diff. |
| `GET` | `/api/v1/reports/list` | Return filterable report archive listing. |
| `GET` | `/api/v1/reports/pptx` | Generate and return a PPTX report for a given symbol. |
| `POST` | `/api/v1/reports/save` | Save a generated report to the archive index. |

## `routes_scheduler.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/sse/scheduler/jobs` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/jobs` | (无描述) |
| `DELETE` | `/api/v1/sse/scheduler/jobs/<job_id>` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/jobs/<job_id>/toggle` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/pause` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/resume` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/start` | (无描述) |
| `GET` | `/api/v1/sse/scheduler/status` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/stop` | (无描述) |

## `routes_screener.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/screener` | Scan stocks by technical conditions. |

## `routes_sse.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/sse/events` | Return all buffered events as a JSON array (non-streaming). |
| `DELETE` | `/api/v1/sse/events` | Clear all buffered events. |
| `GET` | `/api/v1/sse/paper-progress` | SSE streaming endpoint for paper trading progress. |

## `routes_strategy_monitor.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/strategies/status` | Return all registered strategies with metadata. |

## `routes_trade.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/trade/order` | Place a buy or sell order with specified quantity. |
| `GET` | `/api/v1/trade/quote` | GET /api/v1/trade/quote?symbol=600519.SH |
| `GET` | `/api/v1/trade/state` | Return current paper trading state for the trading page. |

## `routes_tv.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/tv/history` | Return OHLCV bars for TradingView. |
| `GET` | `/api/v1/tv/stock-info` | Return A-share stock info: name, exchange, board. |
| `GET` | `/api/v1/tv/stock-search` | Search stocks by code, name, or pinyin. |
| `GET` | `/api/v1/tv/symbols` | Return TradingView symbol info for a given symbol. |

## `routes_watchlist.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/watchlist` | Return the current watchlist symbols. |
| `POST` | `/api/v1/watchlist/add` | Add a symbol to the watchlist. |
| `POST` | `/api/v1/watchlist/batch-analyze` | Submit all watchlist symbols for batch analysis. |
| `POST` | `/api/v1/watchlist/remove` | Remove a symbol from the watchlist. |

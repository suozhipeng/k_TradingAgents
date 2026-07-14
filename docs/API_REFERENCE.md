# A-Stock API 端点参考

> 自动生成于代码，更新于 2026-07-09。以实际代码为准。

> 共 **121** 个端点（含 HTTP 方法变体），覆盖 **28** 个路由模块。


## `routes_admin.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/admin/backend` | (无描述) |
| `POST` | `/api/v1/admin/backend` | (无描述) |
| `GET` | `/api/v1/admin/backend/config` | 后端配置查询 |
| `POST` | `/api/v1/admin/health/sync-ch` | (无描述) |

## `routes_ai_agent.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/ai/analyze` | (无描述) |

## `routes_alerts.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/alerts` | (无描述) |
| `POST` | `/api/v1/alerts` | (无描述) |
| `POST` | `/api/v1/alerts/<alert_id>/ack` | (无描述) |
| `GET` | `/api/v1/alerts/check` | (无描述) |
| `GET` | `/api/v1/alerts/rules` | (无描述) |
| `POST` | `/api/v1/alerts/rules` | (无描述) |
| `DELETE` | `/api/v1/alerts/rules/<rule_id>` | (无描述) |
| `PATCH` | `/api/v1/alerts/rules/<rule_id>` | (无描述) |

## `routes_analysis.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/analysis/watchlist` | (无描述) |

## `routes_backtest.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/backtest/analyze` | 回测详细分析 |
| `GET` | `/api/v1/backtest/compare` | 多策略回测对比 |
| `POST` | `/api/v1/backtest/optimize` | 参数优化 |
| `DELETE` | `/api/v1/backtest/results` | 清理所有回测结果 |
| `GET` | `/api/v1/backtest/results` | 查询历史回测结果 |
| `DELETE` | `/api/v1/backtest/results/<run_id>` | 删除单次回测结果 |
| `POST` | `/api/v1/backtest/run` | 运行单次回测 |
| `POST` | `/api/v1/backtest/walkforward` | 运行 Walk-Forward 分析 |

## `routes_daily.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/daily/review` | (无描述) |

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
| `GET` | `/api/v1/data/health` | 数据源健康检查（各 provider 连通性） |

## `routes_data_ingest.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/data/manual/<table_name>` | (无描述) |
| `POST` | `/api/v1/data/refresh/all` | (无描述) |
| `POST` | `/api/v1/data/refresh/kline` | 刷新 K 线数据 |
| `POST` | `/api/v1/data/refresh/valuation` | 刷新估值数据 |

## `routes_data_jobs.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/data/refresh/options` | Data Hub 表单契约：本地标的、支持周期、模式、估值开关、默认并发、并发上限、任务超时和超时重试策略 |
| `GET` | `/api/v1/data/jobs` | (无描述) |
| `GET` | `/api/v1/data/jobs/<job_id>` | (无描述) |
| `POST` | `/api/v1/data/jobs/import-database` | (无描述) |
| `POST` | `/api/v1/data/jobs/refresh` | 创建刷新任务；`mode=incremental` 由服务端从本地最新 bar 推导刷新起点；支持 `max_concurrency`、`timeout_seconds`、`timeout_retries`；逐项返回 `rows_upserted`、失败 `error.code` 与 `retry_count` |

## `routes_data_query.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/announcements` | (无描述) |
| `GET` | `/api/v1/market/f10` | (无描述) |
| `GET` | `/api/v1/market/fundamentals` | (无描述) |
| `GET` | `/api/v1/market/kline` | (无描述) |
| `GET` | `/api/v1/market/news` | 获取新闻资讯 |
| `GET` | `/api/v1/market/news/live` | (无描述) |
| `GET` | `/api/v1/market/news/stock` | (无描述) |
| `GET` | `/api/v1/market/orderbook` | (无描述) |
| `GET` | `/api/v1/market/research` | (无描述) |
| `GET` | `/api/v1/market/research/expectation` | 获取机构预期 |
| `GET` | `/api/v1/market/research/pdf` | 获取研报 PDF 元数据 |
| `GET` | `/api/v1/market/research/search` | (无描述) |
| `GET` | `/api/v1/market/store/stats` | (无描述) |
| `GET` | `/api/v1/market/trade_tape` | (无描述) |
| `GET` | `/api/v1/market/valuation` | (无描述) |

## `routes_health.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/health` | 轻量健康检查（状态、后端、连接、运行时长） |

## `routes_market.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/recap` | 每日市场复盘报告（指数 + 板块 + 涨跌家数） |
| `POST` | `/api/v1/market/recap` | 每日市场复盘报告（指数 + 板块 + 涨跌家数） |
| `GET` | `/api/v1/market/regime` | 实时市场状态分析（4 维度） |
| `GET` | `/api/v1/market/strategies` | 列出可用回测策略名称 |
| `GET` | `/api/v1/market/summary` | 个股市场摘要（PE/PB/市值/成交量） |

## `routes_market_data.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/calendar` | 交易日历 |
| `GET` | `/api/v1/market/blocks` | (无描述) |
| `GET` | `/api/v1/market/dragon-tiger` | (无描述) |
| `GET` | `/api/v1/market/leading-pool` | (无描述) |
| `GET` | `/api/v1/market/momentum` | 龙头股动量榜；回退分数按代码稳定生成 |
| `POST` | `/api/v1/market/momentum-rotation` | 动量轮动 |
| `GET` | `/api/v1/market/northbound` | (无描述) |
| `GET` | `/api/v1/market/overview` | (无描述) |
| `GET` | `/api/v1/market/quote` | Research-only 行情入口；返回 `source`、`as_of`、`age_seconds`、`is_mock`、`is_stale` |
| `GET` | `/api/v1/market/sectors` | (无描述) |

## `routes_notifications.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/notifications/consumer/start` | 启动通知消费者（需认证） |
| `POST` | `/api/v1/notifications/consumer/stop` | 停止通知消费者（需认证） |
| `POST` | `/api/v1/notifications/desktop` | 发送本机通知测试（需认证） |
| `POST` | `/api/v1/notifications/dingtalk` | 钉钉通知 |
| `GET` | `/api/v1/notifications/dispatchers` | 通知渠道元数据（凭据与 URL 查询参数脱敏） |
| `POST` | `/api/v1/notifications/dispatchers` | 注册通知渠道（需认证，仅允许公网目标） |
| `DELETE` | `/api/v1/notifications/dispatchers/<name>` | 删除通知渠道（需认证） |
| `PUT` | `/api/v1/notifications/dispatchers/<name>` | 更新通知渠道（需认证，仅允许公网目标） |
| `POST` | `/api/v1/notifications/email` | (无描述) |
| `GET` | `/api/v1/notifications/events` | (无描述) |
| `POST` | `/api/v1/notifications/test-webhook` | Webhook 测试 |

## `routes_ops.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/ops/audit` | (无描述) |
| `GET` | `/api/v1/ops/scheduler/status` | 调度器状态 |
| `GET` | `/api/v1/ops/stats` | (无描述) |
| `GET` | `/api/v1/ops/tasks` | (无描述) |
| `GET` | `/api/v1/ops/tasks/<task_id>` | (无描述) |
| `POST` | `/api/v1/ops/tasks/<task_id>/cancel` | (无描述) |

## `routes_paper.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/paper/cycle` | 执行模拟盘周期（需 writer/operator/admin key） |
| `GET` | `/api/v1/paper/state` | 模拟盘统一状态；`positions[]` 含成本价、估值来源和盈亏 |
| `GET` | `/api/v1/paper/trades` | 模拟盘统一成交记录；包含 `side` 与 `quantity` 兼容字段 |

## `routes_portfolio.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/portfolio/attribution` | 组合归因 |
| `GET` | `/api/v1/portfolio/risk` | 组合风险分析 |

## `routes_qmt.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/qmt/health` | (无描述) |
| `GET` | `/api/v1/qmt/orders` | (无描述) |
| `GET` | `/api/v1/qmt/positions` | (无描述) |

## `routes_reports.py`

| Method | Path | 说明 |
|--------|------|------|
| `PATCH` | `/api/v1/reports/<report_id>/audit` | (无描述) |
| `POST` | `/api/v1/reports/compare` | (无描述) |
| `GET` | `/api/v1/reports/list` | (无描述) |
| `GET` | `/api/v1/reports/pptx` | (无描述) |
| `POST` | `/api/v1/reports/save` | (无描述) |

## `routes_scheduler.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/sse/scheduler/jobs` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/jobs` | 添加调度任务 |
| `DELETE` | `/api/v1/sse/scheduler/jobs/<job_id>` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/jobs/<job_id>/toggle` | 切换调度任务 |
| `POST` | `/api/v1/sse/scheduler/pause` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/resume` | (无描述) |
| `POST` | `/api/v1/sse/scheduler/start` | (无描述) |
| `GET` | `/api/v1/sse/scheduler/status` | 调度器状态 |
| `POST` | `/api/v1/sse/scheduler/stop` | (无描述) |

## `routes_screener.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/market/screener` | 选股器 |

## `routes_sse.py`

| Method | Path | 说明 |
|--------|------|------|
| `DELETE` | `/api/v1/sse/events` | (无描述) |
| `GET` | `/api/v1/sse/events` | (无描述) |
| `GET` | `/api/v1/sse/paper-progress` | (无描述) |

## `routes_strategy_monitor.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/strategies/status` | 列出可用回测策略名称 |

## `routes_trade.py`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/trade/order` | 模拟盘下单（需 writer/operator/admin key，与 `/paper/*` 共享状态） |
| `GET` | `/api/v1/trade/quote` | 兼容模式行情入口；默认 Research-only 范围返回 `410 research_only`，请使用 `/api/v1/market/quote` |
| `GET` | `/api/v1/trade/state` | 交易页模拟盘状态；与 `/paper/state` 使用相同 schema |

## `routes_tv.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/tv/history` | (无描述) |
| `GET` | `/api/v1/tv/stock-info` | (无描述) |
| `GET` | `/api/v1/tv/stock-search` | (无描述) |
| `GET` | `/api/v1/tv/symbols` | (无描述) |

## `routes_watchlist.py`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/watchlist` | (无描述) |
| `POST` | `/api/v1/watchlist/add` | (无描述) |
| `POST` | `/api/v1/watchlist/batch-analyze` | 批量分析自选股 |
| `POST` | `/api/v1/watchlist/remove` | (无描述) |

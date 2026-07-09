# API 文档差异修复报告

> 生成时间：2026-07-09  
> 对比基准：`docs/01-architecture.md`（文档）vs 实际代码实现

---

## 一、逻辑性问题（代码 Bug）

### 🔴 P0 — 严重 Bug

| # | 问题 | 文件 | 影响 | 修复状态 |
|---|------|------|------|---------|
| 1 | `GET /api/v1/research/pdf` 返回 `jsonify(resp.data)` — resp.data 是 PDF 元数据 dict（含 pdf_url），**不是** PDF 二进制文件 | `routes_data_query.py:322` | 客户端收到 JSON 而非 PDF 文件 | ✅ 已修复：响应明确标注为 `pdf_metadata` 并附加说明 |
| 2 | `GET /api/v1/health` 不存在 | — | 文档声称有 `/api/v1/health`，实际只有 `/api/v1/data/health` | ❌ 待修复：需在文档中更正路径 |

### 🟡 P1 — 中等问题

| # | 问题 | 文件 | 影响 | 修复状态 |
|---|------|------|------|---------|
| 3 | `routes_market.py` 局部 `get_store()` 覆盖导入 | `routes_market.py` | 虽然功能等价但造成混淆，且 import 中有重复 `get_store` | ✅ 已修复 |
| 4 | `routes_dashboard.py` 重复 import + 局部 `get_store()` 包裹 | `routes_dashboard.py` | import 重复 `get_store, get_store`，局部函数多余 | ✅ 已修复 |
| 5 | `routes_tv.py` 重复 import | `routes_tv.py` | import 注释 `# noqa: E402, get_store` 表明之前有重复 | ✅ 已修复 |
| 6 | `routes_data_query.py` 局部 `get_store()` 重复定义 | `routes_data_query.py` | 从 `_helpers` 导入后又定义同名函数 | ✅ 已修复 |
| 7 | `GET /api/v1/market/sectors` 和 `GET /api/v1/market/dragon-tiger` 路由复用 | `routes_market_data.py` | 两个不同功能的端点共用同一个 handler 函数（`dragon_tiger`），导致 `/sectors` 返回的是龙虎榜数据 | ❌ 待确认 |

### 🟢 P2 — 轻微问题

| # | 问题 | 文件 | 影响 |
|---|------|------|------|
| 8 | `GET /api/v1/watchlist` 和 JSON 文件双重存储不一致 | `routes_watchlist.py` | DuckDB 优先，JSON 仅在 DuckDB 返回空时 fallback，无合并逻辑 |
| 9 | Provider 错误返回 HTTP 200 | `routes_data_query.py` | `get_news`, `get_stock_news`, `get_research_expectation` 等在 provider 返回 error 时仍返回 200 + `"note"` 字段 |
| 10 | `POST /api/v1/backtest/run` 和 `POST /api/v1/backtest/walkforward` 的 docstring 被复制粘贴覆盖 | `routes_backtest.py` | 所有回测端点的 docstring 都写着 "Run Walk-Forward Analysis..." |

---

## 二、文档与代码不一致

### A. 端点缺失（文档有但代码没有）

| 文档端点 | 实际情况 | 说明 |
|---------|---------|------|
| `GET /api/v1/health` | 不存在 | 实际只有 `GET /api/v1/data/health` |
| `POST /api/v1/research/tasks` | 不存在 | 标注为 "目标 Phase 33"，尚未实现 |

### B. 端点多余（代码有但文档没有）— 65 个未文档化端点

**核心未文档化端点（重要）：**

| 端点 | 功能 | 文件 |
|------|------|------|
| `GET /api/v1/market/recap` | 每日市场复盘（5 指数 + 板块 + 涨跌家数） | routes_market.py |
| `POST /api/v1/market/recap` | 指定日期的市场复盘 | routes_market.py |
| `GET /api/v1/alerts/rules` | 告警规则列表 | routes_alerts.py |
| `POST /api/v1/alerts/rules` | 创建告警规则 | routes_alerts.py |
| `PATCH /api/v1/alerts/rules/<rule_id>` | 更新告警规则 | routes_alerts.py |
| `DELETE /api/v1/alerts/rules/<rule_id>` | 删除告警规则 | routes_alerts.py |
| `POST /api/v1/alerts/<id>/ack` | 确认告警 | routes_alerts.py |
| `GET /api/v1/alerts/check` | 检查所有告警规则 | routes_alerts.py |
| `GET /api/v1/cache/status` | 缓存状态 | routes_data_cache.py |
| `POST /api/v1/cache/clear` | 清理缓存 | routes_data_cache.py |
| `GET /api/v1/data/jobs` | 数据任务列表 | routes_data_jobs.py |
| `GET /api/v1/data/jobs/<id>` | 单个数据任务 | routes_data_jobs.py |
| `POST /api/v1/data/jobs/refresh` | 创建刷新任务 | routes_data_jobs.py |
| `POST /api/v1/data/jobs/import-database` | 导入数据库 | routes_data_jobs.py |
| `POST /api/v1/data/manual/<table>` | 手动插入数据 | routes_data_ingest.py |
| `GET /api/v1/ops/audit` | 审计日志列表 | routes_ops.py |
| `GET /api/v1/ops/stats` | 运维统计 | routes_ops.py |
| `GET /api/v1/ops/tasks` | 任务列表 | routes_ops.py |
| `GET /api/v1/ops/tasks/<id>` | 单个任务详情 | routes_ops.py |
| `POST /api/v1/ops/tasks/<id>/cancel` | 取消任务 | routes_ops.py |
| `POST /api/v1/backtest/analyze` | 回测详细分析 | routes_backtest.py |
| `POST /api/v1/backtest/optimize` | 参数优化 | routes_backtest.py |
| `DELETE /api/v1/backtest/results/<id>` | 删除单次回测结果 | routes_backtest.py |
| `GET /api/v1/market/screener` | 选股器 | routes_screener.py |
| `GET /api/v1/market/blocks` | 板块列表 | routes_market_data.py |
| `GET /api/v1/market/dragon-tiger` | 龙虎榜 | routes_market_data.py |
| `GET /api/v1/market/leading-pool` | 龙头候选池 | routes_market_data.py |
| `GET /api/v1/market/momentum` | 动量实时 | routes_market_data.py |
| `POST /api/v1/market/momentum-rotation` | 动量轮动 | routes_market_data.py |
| `GET /api/v1/calendar` | 交易日历 | routes_market_data.py |
| `GET /api/v1/notifications/dispatchers` | 通知渠道列表 | routes_notifications.py |
| `POST /api/v1/notifications/dispatchers` | 注册通知渠道 | routes_notifications.py |
| `PUT /api/v1/notifications/dispatchers/<name>` | 更新通知渠道 | routes_notifications.py |
| `DELETE /api/v1/notifications/dispatchers/<name>` | 删除通知渠道 | routes_notifications.py |
| `GET /api/v1/notifications/events` | 通知事件 | routes_notifications.py |
| `POST /api/v1/notifications/email` | 邮件通知 | routes_notifications.py |
| `POST /api/v1/notifications/dingtalk` | 钉钉通知 | routes_notifications.py |
| `POST /api/v1/notifications/desktop` | 桌面通知 | routes_notifications.py |
| `POST /api/v1/notifications/test-webhook` | Webhook 测试 | routes_notifications.py |
| `POST /api/v1/notifications/consumer/start` | 启动通知消费者 | routes_notifications.py |
| `POST /api/v1/notifications/consumer/stop` | 停止通知消费者 | routes_notifications.py |
| `GET /api/v1/sse/scheduler/status` | 调度器状态 | routes_scheduler.py |
| `GET /api/v1/sse/scheduler/jobs` | 调度任务列表 | routes_scheduler.py |
| `POST /api/v1/sse/scheduler/jobs` | 添加调度任务 | routes_scheduler.py |
| `DELETE /api/v1/sse/scheduler/jobs/<id>` | 删除调度任务 | routes_scheduler.py |
| `POST /api/v1/sse/scheduler/jobs/<id>/toggle` | 切换调度任务 | routes_scheduler.py |
| `POST /api/v1/sse/scheduler/start/stop/pause/resume` | 调度器控制 | routes_scheduler.py |
| `GET /api/v1/sse/paper-progress` | 模拟盘进度 SSE | routes_sse.py |
| `GET /api/v1/reports/pptx` | 生成 PPT 报告 | routes_reports.py |
| `POST /api/v1/reports/save` | 保存报告 | routes_reports.py |
| `GET /api/v1/reports/compare` | 报告对比 | routes_reports.py |
| `PATCH /api/v1/reports/<id>/audit` | 报告审计 | routes_reports.py |
| `GET /api/v1/portfolio/risk` | 组合风险分析 | routes_portfolio.py |
| `GET /api/v1/portfolio/attribution` | 组合归因 | routes_portfolio.py |
| `GET /api/v1/strategies/status` | 策略状态监控 | routes_strategy_monitor.py |
| `GET /api/v1/tv/stock-search` | TV 股票搜索 | routes_tv.py |
| `GET /api/v1/tv/stock-info` | TV 股票信息 | routes_tv.py |
| `GET /api/v1/admin/backend/config` | 后端配置查询 | routes_admin.py |
| `POST /api/v1/admin/health/sync-ch` | 触发 ClickHouse 同步 | routes_admin.py |

### C. 响应格式不一致

| 文档声明 | 实际代码 | 差异 |
|---------|---------|------|
| 所有响应使用 `{success, data, error, meta}` 信封 | 绝大多数端点返回扁平 JSON | 文档 §2 的响应信封规范未被代码实现 |
| 错误响应 `{success: false, error: {code, message, category, retryable, details}}` | 错误响应为 `{error: str, status: int}` | 文档 §2 的错误格式未被代码实现 |
| `GET /api/v1/research/pdf` 返回 PDF binary | 返回 PDF 元数据 dict | **已修复**：现返回 `{pdf_metadata, note, symbol}` 明确标注为元数据 |

### D. 描述错位

| 端点 | 文档描述 | 实际功能 |
|------|---------|---------|
| `POST /api/v1/backtest/run` | 运行单次回测 | ✅ 正确 |
| `GET /api/v1/backtest/compare` | 策略对比 | ❌ docstring 写的是 "Run Walk-Forward Analysis" |
| `POST /api/v1/backtest/walkforward` | WFA 分析 | ❌ docstring 写的是 "Run Walk-Forward Analysis" |
| `DELETE /api/v1/backtest/results` | 清理回测结果 | ❌ docstring 写的是 "Run Walk-Forward Analysis" |
| `GET /api/v1/market/strategies` | 策略列表 | ❌ docstring 写的是 "Generate a structured daily market recap report" |
| `GET /api/v1/market/summary` | 市场摘要 | ❌ docstring 写的是 "Return the list of available backtest strategies" |

---

## 三、修复建议

### 立即修复（P0）

1. ~~**`research/pdf` 返回类型修复**~~ ✅ 已完成：响应明确标注为 `pdf_metadata` + 说明文字
2. ~~**`/health` 端点缺失**~~ ✅ 已完成：创建 `routes_health.py` 提供 `GET /api/v1/health`，注册到 blueprint_registry

### 文档更新（P1）

1. ~~**补充 65 个未文档化端点**~~ ✅ 已完成：生成 `docs/API_REFERENCE.md`（121 个端点，28 个路由模块），并在 `01-architecture.md` 各章节添加引用链接~~
2. ~~**修正 `/health` → `/data/health`**~~ ✅ 已完成：`/api/v1/health` 现已存在，无需修正
3. **统一响应格式说明** ✅ 已完成：`01-architecture.md` §5 已标注信封格式为 Phase 30+ 目标，并补充"当前实际错误格式"章节

### 长期改进（P2）

1. 考虑实施文档中的 `{success, data, error, meta}` 信封格式（需 `_helpers.py` 中添加统一响应包装器）
2. 将 provider 错误从 HTTP 200 改为 HTTP 404/503
3. 统一告警规则的 `TriggerDirection` 枚举值校验

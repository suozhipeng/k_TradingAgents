# TradingAgents AStock Pro — 版本白皮书

> 记录每个版本的架构变更、模块清单和关键决策。对应 `CHANGELOG.md`。

## Unreleased

### 2026-07-17 本地优先分钟线与数据链路收敛

- Web/TradingView K 线查询统一为热库、永久本地库、网络刷新三层；周/月/年线可从永久库日线聚合，避免重复联网。
- 显式 `refresh=1` 支持 `1m`、`5m`、`15m`、`30m`、`60m` 分钟 K 线增量拉取、格式校验、热库 upsert 与永久 DuckDB 同步。
- 多 Flask 应用的同标的刷新 flight 按应用实例隔离；provider 载荷缺少 bar 容器或 OHLC/时间格式非法时返回 `422 invalid_kline_data`，不再向 Web 返回未验证数据。
- 图表端移除重复的本地查询和缓存写入分支，复用市场数据本地优先路径。
- 研究页将周/月/季度走势统计收敛为一次 90 根日线查询；移除无调用方的 `/compare`、`/comparison`、`/performance` 策略历史别名。
- 补充本地正式版操作员验收：有效 LLM/行情凭据、DuckDB 备份恢复、依赖漏洞扫描与单进程部署边界成为实际投入使用前的必检项。

### 2026-07-16 本地入口与数据边界收敛

- 唯一启动器固定为 `scripts/run_astock_api.py`：local-release、单 worker 与 scheduler 禁用不再有可绕过的命令行开关。
- 本地免鉴权改为产品 API allowlist；通知、运维、管理、执行和 SSE/scheduler 端点在该模式统一拒绝。
- `/api/v1/market/kline` 默认只读；显式刷新执行水位增量同步并返回 `data_state`，首次空库与上游故障不再混为一类。服务端错误与永久仓库同步错误均只公开稳定错误码。

### 2026-07-14 路由修复与容错增强

- **数据查询路由规范化**：`routes_data_query.py` 所有端点从 `/api/v1/xxx` 迁移到 `/api/v1/market/xxx`，与市场数据路由体系一致（`/kline` → `/market/kline`、`/valuation` → `/market/valuation`、`/orderbook` → `/market/orderbook`、`/news` → `/market/news`、`/trade_tape` → `/market/trade_tape`、`/research` → `/market/research`、`/fundamentals` → `/market/fundamentals`、`/f10` → `/market/f10`、`/announcements` → `/market/announcements`、`/store/stats` → `/market/store/stats`）。
- **龙虎榜实时上游降级**：`routes_market_data.py` 中 dragon-tiger live 请求异常不再返回 500，改为 HTTP 200 空结果（`source=fallback`，`is_mock=false`），前端可识别真实上游暂不可用。
- **缓存端点上下文修复**：`routes_data_cache.py` 补充 `current_app` 导入，cache status/clear 端点在正确 Flask 应用上下文中执行。
- **旧策略页面重定向修复**：`strategy_bp.py` 中 `/comparison`、`/performance` 等旧入口重定向到 `web.strategy.strategy_hub`。
- **Watch Center `url_for` 修复**：`watch_center_bp.py` 中 `url_for` 蓝图名称从错误的 `web_watch_center` 恢复为正确的 `web.watch_center`。
- **Provider 超时容错**：`routes_data_query.py` 中 live kline fetch 异常日志记录 `exc` 而非 `exc_info=True`，超时场景输出更清晰的警告信息。
- **faulthandler 防卡死**：`pyproject.toml` 新增 `faulthandler_timeout = 90` 与 `faulthandler_exit_on_timeout = true`。
- **并发写入安全**：`KlineLoader` / `ValuationLoader` 拆出 `fetch_response()`（可在线程池中并发执行）与 `write_response()`（确保 DB 写入仅发生在调用方线程），避免 DuckDB 多写竞争。
- **测试更新**：同步更新 `tests/test_astock_api.py`、`tests/test_astock_security_fixes.py` 中所有相关测试用例的路径。

### 之前版本

- 数据刷新并发安全加固：`KlineLoader` / `ValuationLoader` 拆出 `fetch_response()`（可在线程池中并发执行）与 `write_response()`（确保 DB 写入仅发生在调用方线程）；`BatchLoader.load_kline_requests` / `load_all` / `execute` 路径同步改造，`insert_kline` / `insert_valuations` 调用固定由发起线程执行，避免多线程竞争 DuckDB 写入。测试 `tests/test_astock_anti_crawl.py::TestProviderRequestGovernor::test_concurrent_refresh_writes_only_from_calling_thread` 与 `test_concurrent_load_all_writes_valuations_from_calling_thread` 验证了该契约。
- 数据查询路由规范化：`routes_data_query.py` 蓝图更名为 `market_data_query`，所有端点前缀 `/market/`（如 `/kline` → `/market/kline`、`/valuation` → `/market/valuation`、`/orderbook` → `/market/orderbook`、`/news` → `/market/news`、`/trade_tape` → `/market/trade_tape`、`/research` → `/market/research`、`/fundamentals` → `/market/fundamentals`、`/f10` → `/market/f10`、`/announcements` → `/market/announcements`、`/store/stats` → `/market/store/stats`）。
- `routes_data_query.py` — 修复 live kline fetch 异常日志（记录 `exc` 而非 `exc_info=True`），超时场景输出更清晰的警告信息。
- `pyproject.toml` — 新增 `faulthandler_timeout = 90` 与 `faulthandler_exit_on_timeout = true`，防止测试挂死。


- `tradingagents/astock/web/__init__.py` — 修复 React SPA 静态资源服务：`REACT_DIST` 路径修正（增加一层 `.parent` 到达 `webui/dist`）；新增 `/assets/<path>` 和 `/react/<path>` 路由分别服务 React 构建产物中的 JS/CSS 和其他文件；Jinja2 静态文件夹固定为 `STATIC_DIR` 以保证 legacy 资源始终可用；SPA fallback 排除 `/api/*` 路径避免吞没 API 404。
- `tradingagents/astock/web/__init__.py` — 强化 local release 边界：SPA fallback 在 `ASTOCK_LOCAL_RELEASE=true` 时拒绝所有非 API 路由返回 404，确保分析/回测以外页面不可达。
- 数据刷新支持手动设置 1～5 条并发（默认 5）和任务超时；全局网络并发、单 provider 并发、节流与 429 冷却使用同一进程级治理器。
- K 线超时默认最多重试 3 次，估值超时默认最多重试 2 次；退避重试受任务 deadline 限制并在结果中记录实际次数。
- K 线入库兼容常见中英文字段和数值字符串；无法解析日期或 OHLC 的行写入 `data_quarantine`，同批有效行继续入库。任务超时后迟到的 K 线结果不会再写入本地库。
- 2026-07-15 验证：`ASTOCK_TESTING=1 pytest tests/ -q --tb=short` → `1178 passed, 10 skipped`；AStock 专项 → `739 passed, 9 skipped`。
- 数据刷新改为逐个 `symbol:interval` 的单次计划执行：修复大批量任务先串行、后重复并发的重复请求问题，并保留每项各自的增量起点。
- 数据源路由新增按 provider 共享的并发、节流与 429 冷却保护；批量刷新对单项异常返回结构化兼容结果，不再以 `-1` 丢失失败原因。
- 模拟盘状态变更和快照读取由同一实例锁保护，避免调度周期与手动订单并发时损坏内存状态；计划周期将各标的处理置于线程池中，并为单标的处理设置 30 秒超时，超时标的发布 `cycle_error` 而不阻塞其他标的。
- 质量执行器和 `ValidatedStore` 的异步 Store 调用兼容已运行的事件循环：无运行循环时直接执行；有运行循环时由专用线程执行，避免嵌套 `asyncio.run()` 异常。
- 2026-07-14 验证：`env -u PYTHONPATH -u VIRTUAL_ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ASTOCK_TESTING=1 .venv/bin/python -m pytest -q tests/test_production_readiness_fixes.py --tb=short` → `13 passed in 3.28s`。


## Local Release — 2026-07-13（analysis/backtest only）

- 正式 Web 入口固定为 Flask/Jinja2：`.venv/bin/python scripts/run_astock_api.py --port 5860`（启动器始终启用 local-release，不能传 `--local-release`）。
- `ASTOCK_LOCAL_RELEASE=true` 强制启用 research-only、关闭 PaperTradeScheduler，并拒绝交易、模拟盘、QMT、组合、调度和 paper SSE API；执行页面返回 404。
- Jinja2 静态资源恢复由 `tradingagents/astock/web/static/` 提供；未知 Web 路由返回 404，不再返回 React shell。
- 本地启动器默认进入 local-release 并仅绑定 `127.0.0.1`；`--standard` 仅用于遗留开发兼容。local-release 下 `/ops_audit` 返回 404，Settings 隐藏未完成的通知配置。
- React Data Hub 改为消费 `/api/v1/data/refresh/options`；新增 `npm run test:release` 契约检查。React 不属于本地正式发布物。
- 验收：`scripts/verify_local_release.sh` → 155 passed；React 发布契约和生产构建通过。
- 发布门禁：`scripts/verify_local_release.sh` → 155 passed；后续 2026-07-15 全仓离线回归：`ASTOCK_TESTING=1 pytest tests/ -q --tb=short` → `1178 passed, 10 skipped`。使用运行环境注入的有效 DeepSeek key 后，live structured-output 验收已通过；凭据不写入版本库。

## Workspace Snapshot — 2026-07-12（xg_dev）

**React 正式工作台进展**

- P2-R1（`e5087ba`）：`VITE_API_BASE_URL` 环境变量替代硬编码 localhost；Vite dev proxy `/api` → `localhost:5860`；`.env.example` 模板；`HealthCheck` 组件（版本/连接状态）；API 客户端新增 `createRefreshJob`/`listJobs`/`getJob`/`cacheStatus` 等方法
- P2-D1（`6c2a970`）：`DataHub` 组件 — 数据刷新（自选标的/周期/模式/估值）、异步任务列表（实时进度轮询）、数据源健康探测（8 适配器 + DuckDB 状态）、数据库统计看板
- P2-R2（`81aa5de`）：`DashboardPage` 组件 — 正式首页，聚合市场概览/数据新鲜度/决策摘要/自选股/告警/最近回测，1分钟自动轮询
- P2-R3（`437e4ba`）：`ResearchPage` 组件 — 报价/K线/F10/新闻/公告/AI分析 6 tab 闭环，SVG K线迷你图，AI分析触发
- P2-R4（`1f3c7c3`）：`StrategyLab` 组件 — 回测运行(参数表单+结果卡片+SVG权益曲线)/历史结果/MC龙头排行 3 tab
- P2-R5：历史尝试将 Flask 静态文件服务切换为 React 构建产物并启用 SPA fallback；该方案已于 2026-07-13 被本地正式版收敛策略取代，Jinja2 为默认入口
- React 构建产物：52 modules, 266 KB JS, TypeScript 编译通过

**Research-only 边界与行情可信度契约**

- P0-B1（`adbfcb0`）：默认启用 `ASTOCK_RESEARCH_ONLY`；执行页面重定向到 `/dashboard`，执行 API 返回 `410 research_only`，研究 UI 使用 `/api/v1/market/quote`。
- P0-B2（`4f7b20a`）：新增 `DataQualityBanner`，为研究行情相关端点统一注入 `source`、`as_of`、`age_seconds`、`is_mock`、`is_stale`，区分 live、cache/store/fallback/duckdb 与 mock/synthetic 数据。

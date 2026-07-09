# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

## A 股定制模块 — Phase 0–38 交付摘要

> 以下 A 股定制模块的交付记录按 phase 归档，详细变更见各 phase 文档。当前版本 HEAD 为 `xg_dev` 分支。

- **Phase 40** — 2026-07-08：BL-001/BL-002 QMT 能力边界统一、BL-205 决策仪表盘摘要、BL-201 Dashboard 卡片五态、BL-203 结构化每日复盘、BL-204 批量分析入口、Code Quality 静默异常修复、traceability matrix 全面更新（completed）
- **Phase 39** — E2E UAT：端到端用户工作流验收（pass-with-gaps）
- **Phase 38** — Product Navigation Cleanup：7 模块 Sidebar 精简、旧入口 redirect、文档口径回补（completed）
- **Phase 37** — Ops & Audit Center：SSE TaskRun 标准化、Ops Audit 页面、统一审计持久化（completed）
- **Phase 36** — Portfolio Risk & Attribution：Portfolio 页与 schema 落地、深层风险/归因能力未闭环（partial）
- **Phase 35** — Trading Execution Control：schema + trade/QMT/UI 接线已落地、API 契约与真实回报闭环未完成（partial）
- **Phase 34** — Market Leaders Entry：`/market_leaders` 单入口已落地、旧页面兼容访问保留（completed）
- **Phase 33** — AI Research Center：ResearchTask + Audit schema、AI 页面、多标的支持、降级标识、报告对比、advisory-only（completed）
- **Phase 32** — Strategy Lab Consolidation：策略实验室整合 + 参数优化 tab（completed）
- **Phase 31** — Data Quality & Bias Control：幸存者偏差/前瞻偏差检测已修复、页面展示待补齐（partial）
- **Phase 30** — Live Trading Readiness：实盘准入清单与证据（completed）
- **Phase 29** — 专业交易页：TradingView 风格交易控制台、实时报价、订单面板、KLineChart、仓位管理、PaperTrader 桥接（completed）
- **Phase 28** — 动量决策终端 / 动量轮动独立看板 / 龙虎榜 / 北向资金 / 数据健康页面（completed）
- **Phase 27** — 统一数据清洗层 DataCleaner：全路径 NaN→None 清理（completed）
- **Phase 26** — WebUI 全平台重构：Strategy Hub 三位一体、Sidebar 精简、Research v2、数据防爆（completed）
- **Phase 25** — 股票筛选器 + 板块轮动：TradingView 风格筛选面板、ECharts treemap 热力图（completed）
- **Phase 24** — AI Agent 分析页面（completed）
- **Phase 23** — 龙头股动量轮动决策系统：标的池动态获取、动量轮动策略、Streamlit 看板、WebUI 集成（completed）
- **Phase 22** — KLineChart 全功能集成：27 技术指标、17 画线工具、6 周期切换、mootdx 分钟数据（completed）
- **Phase 21** — 测试清噪与全仓回归稳定化：786 passed, 9 skipped, 0 failed（completed）
- **Phase 20** — 策略对比 WebUI：多策略同参数运行、净值曲线叠加（completed）
- **Phase 19** — 绩效分析 WebUI + 数据刷新/缓存管理 + 测试重构全回归 739/739（completed）
- **Phase 18** — 策略扩展 + 参数优化器：3 新策略 + grid search + API + WebUI（completed）
- **Phase 17** — Flask Jinja2 WebUI 10 页面 + PPT 报告生成（completed）
- **Phase 16** — 批量回测 + 市场分析器 + 调度器 + SSE（completed）
- **Phase 15** — Flask REST API + Chart.js + WebUI API 客户端（57 端点）（completed）
- **Phase 14** — 十种回测策略（completed）
- **Phase 13** — WebUI 国际化 + 市场切换（completed）
- **Phase 12** — DuckDB 本地数据库 10 表（completed）
- **Phase 11** — QMT 桥接与受控执行（completed）
- **Phase 10** — 回测与模拟盘（completed）
- **Phase 0–9** — 只读研究与展示链路（completed）

当前代码规模：30 个 WebUI 模板、27 个 API 蓝图、118 条 route decorators（109 唯一路径）、64 个测试文件。

---

### 2026-07-08 — BL-001/BL-002/BL-201/BL-203/BL-204/BL-205 + Code Quality

**BL-001 + BL-002：QMT 能力边界统一**

- `tradingagents/astock/api/routes_qmt.py`：所有 QMT 响应增加 `capability` 标签（`"managed"`）与 `note` 字段（`"mock/read-only — real QMT order/query is P3 deferred"`）
- 模块 docstring、`_get_bridge()`、`_bridge_status()` 显式标注 QMT 为 managed(mock/read-only)

**BL-205：Dashboard 决策仪表盘摘要**

- `tradingagents/astock/api/routes_dashboard.py`：`_get_decision_summary()` 现在正确统计 `research_only`（数据不足或分析失败的标的）
- `tradingagents/astock/api/routes_analysis.py`：`/api/v1/analysis/watchlist` summary 新增 `research_only` 字段
- `tradingagents/astock/web/templates/dashboard/dashboard.html`：`loadGlobalDecisionSummary()` 优先使用后端 `research_only` 而非前端派生计算

**BL-201：Dashboard 首页深化（卡片五态）**

- `tradingagents/astock/web/templates/dashboard/dashboard.html`：`loadAll()` catch 块现在在单个指标卡片上设置 ⚠️ 标记，而非全局替换
- `renderWatchlistMovers()` 在无活跃标的时显示"无活跃标的"而非空白

**BL-203：结构化每日市场复盘**

- `tradingagents/astock/api/routes_daily.py`：完全重写，从 3 索引聚合升级为 7 数据源聚合
  - 五大指数（上证指数/深证成指/创业板指/沪深300/上证50）
  - 板块涨跌排名（前 20）
  - 市场广度（上涨/下跌/涨停/跌停/比例）
  - 北向资金流向（HGT/SGT 最近 5 日）
  - 龙虎榜（买入前五 + 卖出前五）
  - 涨跌幅榜（各前 10）
  - 市场状态分析

**BL-204：自选股批量 AI 分析入口**

- `tradingagents/astock/web/templates/dashboard/dashboard.html`：新增 `runBatchAnalysis()` 函数用于内联批量分析
- "批量分析" 按钮由链接改为 onclick 处理器调用

**Code Quality：Silent exception swallowing 修复**

除 Exception: pass → logger 调用，修复以下文件中的静默异常吞没：
- `backtest_engine/engine.py`：6 处（数据加载、停牌检查、涨跌停、日历、市场状态分析 x2）
- `scheduler/scheduler.py`：3 处（任务移除、任务开关、K线加载）
- `strategy_base/fetch.py`：3 处（baostock 登出、facade fetch x2）
- `strategies/momentum_rotation.py`：1 处（领涨股获取）

**Documentation updates**

- `docs/04-development.md`：BL-201/BL-203/BL-204/FR-22/FR-23/FR-24/FR-25/NFR-04/NFR-05/NFR-07/NFR-09/NFR-11/NFR-14/NFR-16/NFR-17/NFR-19 从 partial 更新为 done，附证据

## A Stock Pro 详细变更

> A Stock Pro 模块的细粒度变更按 SemVer 记录，与核心包版本对齐。

## [0.3.0] — 2026-07-07

**文档口径同步**

- 全功能文档数字校准：API route decorators 118（27 个蓝图，109 个唯一路径）、Web UI 模板 30 个、策略实现 15 个（13 单股 + 2 组合，含 combiners/portfolio）、数据库表 32、索引 28、测试文件 64、LLM 客户端 10、DataFlows 17、Agents 24、Graph 8
- 策略模块拆分：`strategy_base/` 下 14 个文件（base + 10 单股策略 + combiners + portfolio），`execution/` 下另有 momentum_rotation.py
- Web UI 模板从 29 增至 30（新增 strategy_monitor.html）
- API 蓝图从 23 增至 27（新增 routes_daily.py、routes_data_ingest.py、routes_data_cache.py、routes_scheduler.py、routes_strategy_monitor.py 等）

**模块快照**

| 模块 | 文件数 | 说明 |
|------|--------|------|
| llm_clients/ | 10 (核心) | OpenAI/Anthropic/Google/Azure 客户端 |
| dataflows/ | 17 | 全球市场数据管道（Yahoo/AV/Reddit/StockTwits） |
| agents/ | 24 | 多智能体研究系统 |
| graph/ | 8 (核心) | LangGraph 交易图 |
| astock/data_sources/ | 20 (核心) | 7 个 provider adapter + registry + router + 10+ 工具文件 |
| astock/store/ | 8 + models/6 | DuckDB/PG/ClickHouse 三后端 |
| astock/execution/ | 25+ (核心) | 14 strategy_base + momentum_rotation + 回测/模拟/QMT/风控 |
| astock/api/ | 27 蓝图 | 118 route decorators (109 unique paths) |
| astock/web/ | 30 模板 | Flask Jinja2 WebUI |
| astock/schemas/ | 7 | Pydantic 数据模型（API.md §5 已覆盖） |
| astock/quality/ | 3 | 数据质量门控 |
| astock/alert/ | 2 | 预警系统 |
| astock/analysis/ | 2 | 市场分析 |
| astock/reporting/ | 2 | PPT 报告生成 |

**关键数字**

| 指标 | 数量 |
|------|------|
| 数据源 provider | 7 |
| 数据能力 | 22 |
| 策略 | 15 (13 单股 + 2 组合) |
| 数据库表 | 32 (DuckDB/PG) + 12 (CH OLAP) |
| 索引 | 28 |
| ORM 模型 | 32 |
| API route decorators | 118 (27 蓝图, 109 唯一路径) |
| Web 模板 | 30 |
| 测试文件 | 64 |

---

## [0.2.5] — 2026-07-05

**Bug 修复：路由冲突与策略映射**

- 修复 `routes_market_data.py` 中 `/market/summary` 与 `routes_market.py` 的路由冲突（前者改为 `/market/overview`，提供独立于 symbol 的宽泛市场概览）
- 修复 `backtest_engine.py` 中 `MomentumRotation` 误入单标的 `run()` 策略映射（移除映射，传入时给出清晰错误引导用户使用 `run_portfolio()`）
- 其余 10 个单标的策略回归通过

## [0.2.4] — 2026-07-04

**文档体系精简**

- 移除 Hermes 协作文件（hermes-skills.md, hermes-workflow.md, hermes/）
- 移除 verification_provenance/（JSON 验证记录已随代码管理）
- 合并 privacy.md → compliance.md §11
- 合并 ops-metrics.md → deployment.md §8
- 精简 PRD.md：移除重复的 ASTOCK_REQUIREMENTS 合并残留（1075 → 266 行）
- 修正全功能文档数字：数据能力 22、API 端点 88、Web UI 27 页、索引 27、测试 62
- 补充 sina_sectors.py 到数据源工具表
- 归档 phase-web-* 合规验收文件至 _archived/web-evidence/
- 清理 _archived/ 中已合并的 ASTOCK_*.md 旧文件（19 个）

## [0.2.3] — 2026-06-28

**数据库模块 v1.0 — 三后端架构**

- DuckDB (本地 OLAP) / PostgreSQL (生产 OLTP) / ClickHouse (生产 OLAP)
- 32 表完整 schema，含迁移版本管理、审计日志、API 密钥、数据质量规则和隔离区
- 迁移引擎：DuckDB 内联迁移 + PostgreSQL `MigrationRunner`
- DataJobManager：异步作业管理，支持重试/优先级/持久化
- 部署脚本：`scripts/astock_pg_tool.py` + `scripts/astock_sync_ch.py`

**文档体系重建**

- 新增 `full_function_documentation.md`（全功能文档）
- 新增 `database_module_whitepaper.md`（数据库白皮书）
- 新增 `04-development.md`（合并 PRD + 需求 + 技术需求）
- 旧 `ASTOCK_*.md` 归档至 `_archived/`
- Docker Compose 部署支持（app + postgres + clickhouse + pgadmin）

## [0.1.0] — 2026-06-27 及之前

**Phase 0-29 交付**

- Phase 0-28：Provider 路由、研究链、回测、模拟盘、QMT 桥接、DuckDB、WebUI
- Phase 29：专业交易页（TradingView 风格控制台）
- 12 种策略实现
- Flask REST API 基础框架
- KLineChart 集成
- 动量轮动、筛选器、板块热力图

**Phase 30-39 启动**

- Phase 30：Live Trading Readiness 准入清单
- Phase 31-38：数据质量、策略实验室、AI 研究中心、市场龙头、交易执行、组合风控、运维审计、导航清理
- Phase 39：E2E UAT（planned）
- Web-G0 ~ Web-P7：Web 页面合规验收（已完成，归档至 `_archived/web-evidence/`）

---

## [0.3.0] — 2026-07-06

### Added

- **Backtest unification (facade)** — `tradingagents/astock/execution/backtest_engine/facade.py` bridges modules-style `PipelineParams` to the execution engine. Supported strategies run via the execution engine; modules-only strategies fall back to the legacy modules engine. CLI `backtest` command delegates to the facade.
- **Version from pyproject.toml** — `/api/v1/health` now reads version from `pyproject.toml` (falls back to `package_version`), eliminating the hardcoded `0.2.5` drift.

### Changed

- **Entrance convergence** — `scripts/run_astock_api.py` now adds repo root to `sys.path` and respects `--no-web` via `ASTOCK_ENABLE_WEB_UI` env var. `--scheduler` help text updated to clarify that `create_app()` auto-starts the scheduler.
- **DuckDB auto-create directory** — `AStockStore.connect()` now creates the parent directory if it doesn't exist, preventing `Cannot open file` errors on first run.
- **Port defaults unified** — `run_webui.py` and `streamlit_app.py` now default to port 5001 (matching `cli/main.py` and `run.py`). `streamlit_app.py` reads `ASTOCK_API_BASE_URL` env var instead of hardcoding the Flask API address.
- **WebUI blueprint gated** — `create_app()` respects `ASTOCK_ENABLE_WEB_UI` config to conditionally register the web blueprint.

### Fixed

- **Facade no longer silently swallows execution errors** — removed the `try/except Exception` fallback that masked real execution engine failures.
- **Facade `modules` import decoupled from top-level** — `from modules.backtest_engine import ...` moved to lazy `_legacy_backtest_exports()` so importing `tradingagents.astock.execution` no longer requires `modules` to be importable.
- **Health endpoint version drift** — `/api/v1/health` now returns `0.3.0` (from `pyproject.toml`) instead of stale `0.2.5`.
- **Streamlit hardcoded Flask URL** — `streamlit_app.py` now reads port and API base from environment variables (`MOMENTUM_PORT`, `PORT`, `ASTOCK_API_BASE_URL`).

### Testing

- Full regression: `1074 passed, 15 skipped, 7 warnings, 120 subtests passed` (`.venv/bin/python -m pytest -q`)
- Facade-specific tests: `tests/test_astock_backtest_facade.py` — 4 tests covering execution path, modules fallback, CLI delegation, and modules public entry.

---

## [0.2.5] — 2026-05-11

### Added

- **Grounded Sentiment Analyst.** The renamed `sentiment_analyst` now reads
  real Yahoo News, StockTwits, and Reddit data before generating its report,
  replacing the prior flow that could fabricate social posts under prompt
  pressure. (#557, #607)
- **MiniMax provider** with the full M2.x catalog (M2.7 / M2.5 / M2.1 / M2
  plus highspeed variants, 204K context). Dual-region: Global
  (`MINIMAX_API_KEY`) and China (`MINIMAX_CN_API_KEY`).
- **Dual-region Qwen and GLM** with separate keys per region — international
  (`DASHSCOPE_API_KEY`, `ZHIPU_API_KEY`) and China (`DASHSCOPE_CN_API_KEY`,
  `ZHIPU_CN_API_KEY`), selectable via a secondary region prompt. (#758)
- **`TRADINGAGENTS_*` env-var configurability for `DEFAULT_CONFIG`.** Override
  `llm_provider`, deep/quick model IDs, `backend_url`, `output_language`,
  debate-round counts, checkpoint flag, and benchmark ticker via `.env` with
  type-aware coercion (string / int / bool). (#602)
- **Interactive API-key detection in the CLI.** When the selected provider's
  key is missing, the CLI prompts for it and persists the value to `.env`
  so the analysis run continues without restart.
- **Remote Ollama support.** `OLLAMA_BASE_URL` points the CLI and the
  programmatic client at a remote `ollama-serve`. The CLI surfaces the
  resolved endpoint and warns on common malformed inputs. Adds a
  `"Custom model ID"` option for models pulled via `ollama pull`. (#648, #768)
- **Configurable news-fetch parameters** in `DEFAULT_CONFIG` — per-ticker
  article limit, macro headline limit, lookback window, and macro search
  queries. (#606, #683)
- **Configurable alpha benchmark** for non-US tickers. Replaces hardcoded
  SPY with regional indices for `.NS` (^NSEI), `.T` (^N225), `.HK` (^HSI),
  `.L` (^FTSE), `.TO` (^GSPTSE), `.AX` (^AXJO), `.BO` (^BSESN); explicit
  `benchmark_ticker` override available. Eliminates FX drift dominating
  alpha for non-USD listings. (#628, #684)
- **Multi-language output covers every user-facing agent** — researchers,
  risk debators, research manager, and trader, ending the previous
  partial-localization reports. (#575)
- **Model catalog refresh.** OpenAI GPT-5.5 frontier, Anthropic Claude Opus
  4.7, Gemini 3.1 Flash-Lite GA, xAI Grok 4.20, Qwen 3.6 line. Versioned IDs
  only; auto-shifting aliases moved to the `"Custom model ID"` option.

### Changed

- **Sentiment Analyst** is now consistently named across the CLI dropdown,
  status panel, and final reports (previously the backend was renamed but
  the CLI still said "Social Analyst"). The `AnalystType.SOCIAL = "social"`
  wire value is kept for saved-config back-compat.

### Fixed

- **Structured output works on DeepSeek V4 / reasoner and MiniMax M2.x.**
  Those providers reject `tool_choice` per their tool-calling docs; the
  binding flow now skips it automatically via a capability table.
- **`pip install .` installations pick up the project `.env`** when running
  the CLI as a console script. (#747)
- **Reports save end-to-end** — streamed chunks were previously dropped from
  `complete_report.md`. (#719, #736)
- **Ticker prompt preserves exchange suffixes** (`.SH`, `.SZ`, `.SS`, `.HK`,
  `.T`, etc.) for A-share, HK, Tokyo, and other non-US flows. (#770)
- **Docker permission errors** no longer block first-run write to
  `~/.tradingagents/`. (#519, #627, #672, #771)
- **Config state no longer leaks between runs** when sub-dicts are mutated;
  `set_config` partial updates preserve sibling defaults. (#788)
- **`max_recur_limit` config actually applies** — previously read but not
  forwarded to the propagator. (#764)
- **Missing-API-key error** names the exact env var to set. (#680)
- **Quieter startup** — suppressed the noisy upstream
  `LangChainPendingDeprecationWarning` from langgraph-checkpoint; will be
  removed once that package ships its fix.

### Security

- **Ticker path-traversal validation** at every filesystem-path site (cache,
  checkpoint database, results) so a malicious ticker cannot escape its
  intended directory. (#618)

## [0.2.4] — 2026-04-25

### Added

- **Structured-output decision agents.** Research Manager, Trader, and Portfolio
  Manager now use `llm.with_structured_output(Schema)` on their primary call
  and return typed Pydantic instances. Each provider's native structured-output
  mode is used (`json_schema` for OpenAI / xAI, `response_schema` for Gemini,
  tool-use for Anthropic, function-calling for OpenAI-compatible providers).
  Render helpers preserve the existing markdown shape so memory log, CLI
  display, and saved reports keep working unchanged. (#434)
- **LangGraph checkpoint resume** — opt-in via `--checkpoint`. State is saved
  after each node so crashed or interrupted runs resume from the last
  successful step. Per-ticker SQLite databases under
  `~/.tradingagents/cache/checkpoints/`. `--clear-checkpoints` resets them. (#594)
- **Persistent decision log** replacing the per-agent BM25 memory. Decisions
  are stored automatically at the end of `propagate()`; the next same-ticker
  run resolves prior pending entries with realised return, alpha vs SPY, and
  a one-paragraph reflection. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
  Optional `memory_log_max_entries` config caps resolved entries; pending
  entries are never pruned. (#578, #563, #564, #579)
- **DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), and Azure OpenAI**
  providers, plus dynamic OpenRouter model selection.
- **Docker support** — multi-stage build with separate dev and runtime images.
- **`scripts/smoke_structured_output.py`** — diagnostic that exercises the
  three structured-output agents against any provider so contributors can
  verify their setup with one command.
- **5-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell) used
  consistently by Research Manager, Portfolio Manager, signal processor, and
  the memory log; Trader keeps 3-tier (Buy / Hold / Sell) since transaction
  direction is naturally ternary.
- **Pytest fixtures** — lazy LLM client imports plus placeholder API keys so
  the test suite runs cleanly without credentials. (#588)

### Changed

- **`backend_url` default is now `None`** rather than the OpenAI URL. Each
  provider client falls back to its native default. The previous default
  leaked the OpenAI URL into non-OpenAI clients (e.g. Gemini), producing
  malformed request URLs for Python users who switched providers without
  overriding `backend_url`. The CLI flow is unaffected.
- All file I/O passes explicit `encoding="utf-8"` so Windows users no longer
  hit `UnicodeEncodeError` with the cp1252 default. (#543, #550, #576)
- Cache and log directories moved to `~/.tradingagents/` to resolve Docker
  permission issues. (#519)
- `SignalProcessor` reads the rating from the Portfolio Manager's rendered
  markdown via a deterministic heuristic — no extra LLM call.
- OpenAI structured-output calls default to `method="function_calling"` to
  avoid noisy `PydanticSerializationUnexpectedValue` warnings emitted by
  langchain-openai's Responses-API parse path. Same typed result, no warnings.

### Fixed

- Empty memory no longer triggers fabricated past-lessons in agent prompts;
  the memory-log redesign makes this structurally impossible since only the
  Portfolio Manager consults memory and only when entries exist. (#572)
- Tool-call logging processes every chunk message, not just the last one, and
  memory score normalization handles empty score arrays. (#534, #531)

### Removed

- `FinancialSituationMemory` (the per-agent BM25 system) and the dead
  `reflect_and_remember()` plumbing; subsumed by the persistent decision log.
- Hardcoded Google endpoint that caused 404 when `langchain-google-genai`
  changed its API path. (#493, #496)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

- [@claytonbrown](https://github.com/claytonbrown) — checkpoint resume (#594), test fixtures (#588), design feedback on cost tracking (#582) and structured validation (#583)
- [@Bcardo](https://github.com/Bcardo) — memory-log redesign (#579), empty-memory hallucination report (#572), encoding fix proposal (#570)
- [@voidborne-d](https://github.com/voidborne-d) — memory persistence design (#564), portfolio manager state fix (#503)
- [@mannubaveja007](https://github.com/mannubaveja007) — structured-output feature request (#434)
- [@kelder66](https://github.com/kelder66) — RAM-only memory issue (#563)
- [@Gujiassh](https://github.com/Gujiassh) — tool-call logging fix (#534), test stub PR (#533)
- [@iuyup](https://github.com/iuyup) — memory score normalization fix (#531)
- [@kaihg](https://github.com/kaihg) — Google base_url fix (#496)
- [@32ryh98yfe](https://github.com/32ryh98yfe) — Gemini 404 report (#493)
- [@uppb](https://github.com/uppb) — OpenRouter dynamic model selection (#482)
- [@guoz14](https://github.com/guoz14) — OpenRouter limited-model report (#337)
- [@samchenku](https://github.com/samchenku) — indicator name normalization (#490)
- [@JasonOA888](https://github.com/JasonOA888) — y_finance pandas import fix (#488)
- [@tiffanychum](https://github.com/tiffanychum) — stale import cleanup (#499)
- [@zaizou](https://github.com/zaizou) — Docker permission issue (#519)
- [@Stosman123](https://github.com/Stosman123), [@mauropuga](https://github.com/mauropuga), [@hotwind2015](https://github.com/hotwind2015) — Windows encoding bug reports (#543, #550, #576)
- [@nnishad](https://github.com/nnishad), [@atharvajoshi01](https://github.com/atharvajoshi01) — encoding fix proposals (#568, #549)

## [0.2.3] — 2026-03-29

### Added

- **Multi-language output** for analyst reports and final decisions, with a
  CLI selector. Internal agent debate stays in English for reasoning quality. (#472)
- **GPT-5.4 family models** in the default catalog, with deep/quick model split.
- **Unified model catalog** as a single source of truth for CLI options and
  provider validation.

### Changed

- `base_url` is forwarded to Google and Anthropic clients so corporate proxies
  work consistently across providers. (#427)
- Standardised the Google `api_key` parameter to the unified `api_key` form.

### Fixed

- Backtesting fetchers no longer leak look-ahead data when `curr_date` is in
  the middle of a fetched window. (#475)
- Invalid indicator names from the LLM are caught at the tool boundary instead
  of crashing the run. (#429)
- yfinance news fetchers respect the same exponential-backoff retry as price
  fetchers. (#445)

### Contributors

- [@ahmedk20](https://github.com/ahmedk20) — multi-language output (#472)
- [@CadeYu](https://github.com/CadeYu) — model catalog typing (#464)
- [@javierdejesusda](https://github.com/javierdejesusda) — unified Google API key parameter (#453)
- [@voidborne-d](https://github.com/voidborne-d) — yfinance news retry (#445)
- [@kostakost2](https://github.com/kostakost2) — look-ahead bias report (#475)
- [@lu-zhengda](https://github.com/lu-zhengda) — proxy/base_url support request (#427)
- [@VamsiKrishna2021](https://github.com/VamsiKrishna2021) — invalid indicator crash report (#429)

## [0.2.2] — 2026-03-22

### Added

- **Five-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell)
  introduced for the Portfolio Manager.
- **Anthropic effort level** support for Claude models.
- **OpenAI Responses API** path for native OpenAI models.

### Changed

- `risk_manager` renamed to `portfolio_manager` to match the role description
  shown in the CLI display.
- Exchange-qualified tickers (e.g. `7203.T`, `BRK.B`) preserved across all
  agent prompts and tool calls.
- Process-level UTF-8 default attempted for cross-platform consistency
  (note: this approach did not actually take effect; replaced in v0.2.4 with
  explicit per-call `encoding="utf-8"` arguments).

### Fixed

- yfinance rate-limit errors are retried with exponential backoff. (#426)
- HTTP client SSL customisation is supported for environments that need
  custom certificate bundles. (#379)
- Report-section writes handle list-of-string content gracefully.

### Contributors

- [@CadeYu](https://github.com/CadeYu) — exchange-qualified ticker preservation (#413)
- [@yang1002378395-cmyk](https://github.com/yang1002378395-cmyk) — HTTP client SSL customisation (#379)

## [0.2.1] — 2026-03-15

### Security

- Patched `langchain-core` vulnerability (LangGrinch). (#335)
- Removed `chainlit` dependency affected by CVE-2026-22218.

### Added

- `pyproject.toml` build-system configuration; the project now installs via
  modern packaging tooling.

### Removed

- `setup.py` — dependencies consolidated to `pyproject.toml`.

### Fixed

- Risk manager reads the correct fundamental report source. (#341)
- All `open()` calls receive an explicit UTF-8 encoding (initial pass).
- `get_indicators` tool handles comma-separated indicator names from the LLM. (#368)
- `Propagation` initialises every debate-state field so risk debaters never
  see missing keys.
- Stock data parsing tolerates malformed CSVs and NaN values.
- Conditional debate logic respects the configured round count. (#361)

### Contributors

- [@RinZ27](https://github.com/RinZ27) — `langchain-core` security patch (#335)
- [@Ljx-007](https://github.com/Ljx-007) — risk manager fundamental-report fix (#341)
- [@makk9](https://github.com/makk9) — debate-rounds config issue (#361)

## [0.2.0] — 2026-02-04

This is the largest release since the initial public version. The framework
moved from single-provider to a multi-provider architecture and grew several
production-ready surfaces.

### Added

- **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, OpenRouter,
  Ollama) via a factory pattern, with provider-specific thinking configurations.
- **Alpha Vantage** integration as a configurable primary data provider, with
  yfinance as a community-stability fallback.
- **Footer statistics** in the CLI: real-time tracking of LLM calls, tool
  calls, and token usage via LangChain callbacks.
- **Post-analysis report saving** — the framework writes per-section markdown
  files (analyst reports, debate transcripts, final decision) when a run
  completes.
- **Announcements panel** — fetches updates from `api.tauric.ai/v1/announcements`
  for the CLI welcome screen.
- **Tool fallbacks** so a single vendor outage does not stop the pipeline.

### Changed

- Risky / Safe risk debaters renamed to **Aggressive / Conservative** for
  consistency with the displayed agent labels.
- Default data vendor switched to balance reliability and quota across
  community deployments.
- Ollama and OpenRouter model lists updated; default endpoints clarified.

### Fixed

- Analyst status tracking and message deduplication in the live display.
- Infinite-loop guard in the agent loop; reflection and logging hardened.
- Various data-vendor implementation bugs and tool-signature mismatches.

### Contributors

This release is the first with substantial outside contributions; many community
PRs from late 2025 also landed here.

- [@luohy15](https://github.com/luohy15) — Alpha Vantage data-vendor integration (#235)
- [@EdwardoSunny](https://github.com/EdwardoSunny) — yfinance fetching optimisations (#245)
- [@Mirza-Samad-Ahmed-Baig](https://github.com/Mirza-Samad-Ahmed-Baig) — infinite-loop guard, reflection, and logging fixes (#89)
- [@ZeroAct](https://github.com/ZeroAct) — saved results path support (#29)
- [@Zhongyi-Lu](https://github.com/Zhongyi-Lu) — `.env` gitignore (#49)
- [@csoboy](https://github.com/csoboy) — local Ollama setup (#53)
- [@chauhang](https://github.com/chauhang) — initial Docker support attempt (#47, later reverted; the merged Docker support shipped in v0.2.4)

## [0.1.1] — 2025-06-07

### Removed

- Static site assets that had been bundled with v0.1.0; the public site now
  lives separately.

## [0.1.0] — 2025-06-05

### Added

- **Initial public release** of the TradingAgents multi-agent trading
  framework: market / sentiment / news / fundamentals analysts; bull and bear
  researchers; trader; aggressive, conservative, and neutral risk debaters;
  portfolio manager. LangGraph orchestration, yfinance data, per-agent
  BM25 memory, single-provider OpenAI integration, interactive CLI.

[0.2.4]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/TauricResearch/TradingAgents/releases/tag/v0.1.0

# STACK

## Python 版本
- `pyproject.toml` 指定：`requires-python = ">=3.12"`
- Docker/容器相关默认镜像未在 `docker-compose.yml` 明示 Python 小版本；`terminal.docker_image` 属于 Hermes 配置，不属于本项目，故这里不引用。
- 若生产部署要求固定到 `3.10.x / 3.11.x`，当前仓库内未看到锁定信息，**需人工确认**。

## 依赖来源
- **主依赖来源**：`pyproject.toml`
- **requirements.txt**：仅包含 `.`，表示以当前项目包方式安装，本身不列出真实第三方依赖。

## 主要依赖
### LLM / Agent 编排
- `langchain-core>=0.3.81`
- `langchain-openai>=0.3.23`
- `langchain-anthropic>=0.3.15`
- `langchain-experimental>=0.3.4`
- `langgraph>=0.4.8`
- `langgraph-checkpoint-sqlite>=2.0.0`

### 金融 / 数据处理
- `yfinance>=1.4.1`
- `stockstats>=0.6.5`
- `pandas>=2.3.0`
- `backtrader>=1.9.78.123`
- `requests>=2.32.4`
- `pytz>=2025.2`
- `parsel>=1.10.0`

### CLI / 交互
- `typer>=0.21.0`
- `questionary>=2.1.0`
- `rich>=14.0.0`
- `tqdm>=4.67.1`

### 其他
- `redis>=6.2.0`（代码中未在本次分析范围内看到核心调用链入口，可能用于扩展/未来功能，**需人工确认**）
- `typing-extensions>=4.14.0`
- `setuptools>=80.9.0`

## LLM 相关组件
### Provider 抽象层
目录：`tradingagents/llm_clients/`
- `factory.py`：统一入口，按 provider 构造客户端
- `openai_client.py`
- `anthropic_client.py`
- `google_client.py`：残留代码文件，当前 provider 已暂时屏蔽
- `azure_client.py`
- `api_key_env.py`：provider → 环境变量映射
- `model_catalog.py`：CLI 模型选单
- `capabilities.py` / `validators.py`：能力判定与模型校验

### 已支持 Provider（由 `factory.py` 和 `api_key_env.py` 可见）
- OpenAI
- Anthropic
- Azure OpenAI
- xAI
- DeepSeek
- Qwen / Qwen-CN
- GLM / GLM-CN
- MiniMax / MiniMax-CN
- OpenRouter
- Ollama

### 当前暂时屏蔽的 Provider
- Google Gemini
  - 原因：`langchain-google-genai` 需要较新的 `httpx`，与 A 股 provider 栈中的 `mootdx 0.11.7` 约束冲突

## 数据源相关组件
### 市场与基本面数据
目录：`tradingagents/dataflows/`
- `y_finance.py`：Yahoo Finance 数据
- `yfinance_news.py`：Yahoo Finance 新闻
- `alpha_vantage*.py`：Alpha Vantage 行情/指标/新闻/基本面
- `interface.py`：数据源路由与 fallback
- `market_data_validator.py`：市场数据校验
- `symbol_utils.py`：ticker / symbol 处理

### 舆情与社区数据
- `reddit.py`：Reddit 抓取
- `stocktwits.py`：StockTwits 抓取

### 默认数据供应商策略
`default_config.py` 默认：
- `core_stock_apis`: `yfinance`
- `technical_indicators`: `yfinance`
- `fundamental_data`: `yfinance`
- `news_data`: `yfinance`

并允许：
- 分类级别 `data_vendors`
- 工具级别 `tool_vendors`
- 自动 fallback（`interface.py`）

## CLI 相关组件
目录：`cli/`
- `main.py`：Typer CLI 主入口
- `models.py`：CLI 枚举（分析师类型、资产类型）
- `config.py`：CLI 远端公告配置
- `utils.py`：选择器、辅助函数、保存报告等
- `stats_handler.py`：LLM / 工具调用统计
- `announcements.py`：启动公告获取
- `static/welcome.txt`：欢迎文本资源

### CLI 脚本入口
`pyproject.toml`
- `tradingagents = "cli.main:app"`

## Docker 相关组件
### `docker-compose.yml`
服务：
- `tradingagents`
  - `build: .`
  - 加载 `.env`
  - 挂载持久卷到 `/home/appuser/.tradingagents`
- `ollama`
  - `image: ollama/ollama:latest`
  - profile: `ollama`
- `tradingagents-ollama`
  - `LLM_PROVIDER=ollama`
  - 依赖 `ollama`
  - profile: `ollama`

### Docker 能力结论
- 支持默认容器运行
- 支持通过 `ollama` profile 走本地/自托管模型
- 未看到真实交易网关、券商 API、订单执行容器，当前更像“研究/决策生成框架”，不是完整交易执行系统

## A 股扩展栈（Phase 0–11 交付后）

### A 股可选依赖
`pyproject.toml` 中声明了两组可选依赖，基础安装不包含：

| 组 | 依赖 | 用途 |
|---|---|---|
| `astock-providers` | `akshare>=1.16.0` | A 股行情/新闻/基本面数据 |
| `astock-providers` | `mootdx>=0.11.7` | 通达信数据协议 |
| `astock-providers` | `pywencai>=0.12.0` | 问财（iwencai）语义查询 |
| `ui` | `streamlit>=1.37.0` | 运行时 viewer 后端 |

安装方式：
```bash
pip install tradingagents[astock-providers]  # A 股五层 provider
pip install tradingagents[astock-providers,ui]  # A 股 + viewer
```

### A 股数据源层
路径：`tradingagents/astock/data_sources/`

| 模块 | 职责 |
|---|---|
| `router.py` | `AStockDataRouter` / `AStockDataFacade`：五层能力路由、主源/备源/淘汰源策略 |
| `adapters.py` | 6 个 Adapter：`AkshareAdapter`、`MootdxAdapter`、`TencentFinanceAdapter`、`IwencaiAdapter`、`CninfoAdapter`、`QMTAdapter` |
| `cache.py` | `FileAStockCache` / `InMemoryAStockCache`：缓存与去重 |
| `errors.py` | 统一错误语义：`AStockNoDataError`、`AStockSourceUnavailableError`、`AStockSchemaError` |
| `schema.py` | `AStockRequest` / `AStockResponse`：统一请求/响应契约 |
| `symbols.py` | `normalize_astock_symbol`、`split_astock_symbol`：A 股 symbol 标准化 |

### A 股统一接口与 Analyst
| 模块 | 路径 | 职责 |
|---|---|---|
| 统一接口 | `tradingagents/astock/interface.py` | `AStockInterface` + `AStockSectionBundle`：将五层 provider 能力收敛成结构化 section |
| 工具 | `tradingagents/astock/tools.py` | `build_astock_tools`：构建 A 股专用 LangChain 工具集 |
| Analyst | `tradingagents/astock/analyst.py` | `AStockAnalyst` + 创建工厂 |
| Blueprint | `tradingagents/astock/blueprint.py` | `ASTOCK_BLUEPRINT`：18 个能力点的声明式定义 |

### A 股 Research Runtime & Advisory Chain
| 模块 | 路径 | 职责 |
|---|---|---|
| Runtime | `tradingagents/astock/runtime.py` | `AStockGraphRuntime` + `BridgeLLM` + `run_astock_research_bridge` |
| Profile | `tradingagents/astock/runtime_profile.py` | `RuntimeProfile`：`deterministic_verification` / `live_research` 隔离策略 |
| Phase 9 Schema | `tradingagents/astock/phase9_schemas.py` | 四个 advisory 合约：`ResearchConclusion` → `TraderProposal` → `RiskDecision` → `PortfolioDecision` |
| 验证溯源 | `tradingagents/astock/verification_provenance.py` | `VerificationProvenance`：live provider 验证的日期/commit/环境追踪 |

### A 股执行层（Phase 10–11）
路径：`tradingagents/astock/execution/`

| 模块 | 职责 |
|---|---|
| `backtest_engine.py` | `BacktestEngine`：历史数据策略回放、周期调仓、费率模拟、多策略对比 |
| `paper_trader.py` | `PaperTrader`：虚拟券商 + 真实费率、定时调度自动调仓 |
| `strategy_base.py` | `StrategyBase` + `MovingAverageTrendStrategy`：策略定义基类与均线趋势示例 |
| `qmt_bridge.py` | `QmtSource`：主系统 ↔ Python 3.6.8 QMT 环境的 HTTP :58609 桥接 |
| `qmt_execution.py` | `QmtExecution`：safety/auto 模式切换、人工确认门、ATR 实时止损 |
| `risk_gate.py` | `RiskGate`：ATR 动态止损、safety mode 确认门、组合风控约束 |
| `fee_model.py` | 费率建模 |
| `metrics.py` | 回测/模拟盘指标计算 |

### A 股核心数据流
```text
AStockDataRouter
  -> AStockInterface
  -> AStockAnalyst
  -> researchers (Bull / Bear / Research Manager)
  -> Phase 9 Advisory Chain
  |    (ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision)
  -> AStockGraphReport
  -> { CLI | Streamlit read-only viewer | WebUI (Jinja2 / React) }
  -> { BacktestEngine | PaperTrader | QmtExecution (managed) }
  -> { DuckDB Store | EventBus (SSE) | ReportGenerator (PPTX) }
```

所有 A 股执行输出保持 `decision_scope=research_only`、`actionable=false`、`execution_signal=ResearchOnly`，除非 safety mode 下人工确认。

### A 股安全边界
| 机制 | 说明 |
|---|---|
| Safety mode（默认） | 每次执行操作需人工确认（`confirmed=True`） |
| Auto mode | 用户显式通过配置或 CLI 参数开启 |
| ATR 止损层 | 实时计算 ATR 止损线，触发时自动拒绝下单 |
| QMT 降级 | QMT 桥接不可用时自动走模拟盘路径 |
| `actionable=false` | 所有输出保持非可执行标记，直到人工确认 |

### A 股扩展栈（Phase 12–38 交付后）

#### DuckDB 本地数据库（Phase 12）
| 模块 | 路径 | 职责 |
|---|---|---|
| Store | `tradingagents/astock/store/` | `AStockStore` + 10 张表（kline_bars, valuations, order_book_snapshots 等） |
| Loader | `tradingagents/astock/store/loader.py` | `KlineLoader` / `ValuationLoader` / `BatchLoader` |
| CLI 工具 | `scripts/astock_db_tool.py` | list-tables / stats / export / import / query / vacuum |

#### Flask REST API（Phase 15）
| 模块 | 路径 | 职责 |
|---|---|---|
| Factory | `tradingagents/astock/api/__init__.py` | `create_app()` + CORS + 14 blueprints 注册 |
| Data CRUD | `routes_data.py` | kline / valuation / orderbook / news / research / announcements |
| Backtest | `routes_backtest.py` | 运行回测 / 查询结果 / 多策略对比 |
| Paper Trading | `routes_paper.py` | 模拟盘状态 / 交易记录 / 单次调仓 |
| Market | `routes_market.py` | 市场概览 / 策略列表 |
| QMT | `routes_qmt.py` | QMT 健康检查 / 持仓 / 委托 |
| SSE | `routes_sse.py` | 事件流推送 |
| Reports | `routes_reports.py` | 报告归档 |
| Dashboard | `routes_dashboard.py` | Dashboard 数据 |
| Screener | `routes_screener.py` | 股票筛选 |
| Market Data | `routes_market_data.py` | 龙虎榜 / 板块 / 北向资金 / 动量轮动 |
| Data Health | `routes_data_health.py` | 数据健康检查 |
| Trade | `routes_trade.py` | 交易委托 / 报价 |
| TV Chart | `routes_tv.py` | TradingView 兼容 datafeed |

#### Jinja2 WebUI（Phase 17+）
| 模块 | 路径 | 职责 |
|---|---|---|
| Blueprint | `tradingagents/astock/web/__init__.py` | 6 个页面 blueprint；22 个非共享页面模板 + `base.html` / macros |
| 页面 | `templates/` | dashboard / daily / research / ai_agent / strategy_hub / strategies / backtest / strategy_monitor / watchlist / screener / market_leaders / monitor / kc_chart / reports / ops_audit / data_health / settings；执行类模板仅兼容保留，旧盯盘 URL 以 302 归并到 Market Leaders |

#### 策略与优化（Phase 14, 18, 20）
| 模块 | 路径 | 职责 |
|---|---|---|
| 策略基类 | `tradingagents/astock/execution/strategy_base.py` | 10 种策略（2 牛 / 2 震荡 / 2 熊 + MACD / 布林带 / 网格） |
| 注册表 | `execution/strategy_registry.py` | 策略注册与查询 |
| 优化器 | `execution/optimizer.py` | `StrategyOptimizer` grid search |
| 批量回测 | `execution/batch_backtest.py` | `BatchBacktestRunner` |
| 动量轮动 | `execution/momentum_rotation.py` | 龙头股动量轮动策略 |

#### 执行层增强（Phase 16+）
| 模块 | 路径 | 职责 |
|---|---|---|
| Kill Switch | `execution/kill_switch.py` | 全局紧急停止 |
| Scheduler | `execution/scheduler.py` | `PaperTradeScheduler` 定时调度 |
| EventBus | `execution/event_bus.py` | 内存环形缓冲区 SSE 推送 |
| Leader Pool | `execution/leader_pool.py` | 龙头股候选池 |
| Risk Gate | `execution/risk_gate.py` | ATR 止损 + 跟踪止盈 |

#### 数据质量与清洗（Phase 27, 31）
| 模块 | 路径 | 职责 |
|---|---|---|
| Cleaner | `tradingagents/astock/data_sources/cleaner.py` | `DataCleaner` 全路径 NaN→None |
| Quality | `data_sources/quality.py` | `DataQualityTag` / `FreshnessInfo` |
| Calendar | `data_sources/calendar.py` | 交易日历工具 |
| Eastmoney | `data_sources/eastmoney.py` | 东方财富数据（龙虎榜 / 行业对比 / 港股通） |
| Sina Sectors | `data_sources/sina_sectors.py` | 新浪板块数据 |
| Adjustment | `data_sources/adjustment.py` | 复权因子 |
| Suspension | `data_sources/suspension.py` | 停牌 / 涨跌停 |

#### 分析与报告（Phase 17, 19）
| 模块 | 路径 | 职责 |
|---|---|---|
| Market Analyzer | `tradingagents/astock/analysis/` | 4 维度加权市场体制分析 |
| Report Generator | `tradingagents/astock/reporting/` | PPTX 报告生成（5 页 dark theme） |

#### Phase 32-37 Schemas
| 模块 | 路径 | 职责 |
|---|---|---|
| Trading Execution | `astock/schemas/trading_execution.py` | Order / Fill / Position / Reconciliation |
| Portfolio | `astock/schemas/portfolio.py` | Portfolio / RiskExposure / Attribution |
| Research Task | `astock/schemas/research_task.py` | ResearchTask / ResearchAudit |
| Research Context | `astock/schemas/research_context.py` | DataSourceMeta / StockInfoData / MarketSummaryData |
| Optimization | `astock/schemas/optimization.py` | OptimizeResult |
| Ops Audit | `astock/schemas/ops_audit.py` | TaskType / TaskRun / AuditEvent |
| Report Archive | `astock/schemas/report_archive.py` | ReportFormat / ReportItem / ReportArchive |

#### React/TS 实验前端（Phase 26+）
| 模块 | 路径 | 职责 |
|---|---|---|
| App | `webui/src/App.tsx` | 非发布开发前端；用于组件和 API 契约开发，不是本地正式版入口 |
| Modules | `webui/src/data/modules.json` | 30 个模块静态记录 |
| API Client | `webui/src/hooks/useApi.ts` | Flask REST API 客户端；Data Hub 从服务端读取刷新选项 |
| Types | `webui/src/types.ts` | ModuleType / ModuleRecord / AStockGraphReport |

#### 测试基础设施
| 模块 | 路径 | 职责 |
|---|---|---|
| Conftest | `tests/conftest.py` | unit/integration/smoke markers + `_dummy_api_keys` fixture |
| Fixtures | `tests/fixtures/astock_providers/` | 15 个 JSON 测试样本 |
| 测试文件 | `tests/` | ~67 个测试文件，~13,709 行 |

## 总结
这是一个：
- **Python 3.12+**
- 以 **LangGraph + LangChain** 为核心
- 通过 **多类 LLM Provider + 多数据源路由** 完成
- 带 **交互式 CLI** 与 **Docker/Ollama 运行方式**
- A 股扩展层包含：
  - **五层数据路由**（行情/研报/新闻/基础数据/公告）
  - **统一接口**与 AStockAnalyst
  - **Research-only runtime** + Phase 9 advisory chain
  - **回测/模拟盘/QMT 桥接**执行层
  - **DuckDB 本地数据库**（10 表）
  - **Flask REST API**（57 端点 / 14 模块）
  - **Jinja2 WebUI**（22 个非共享页面模板；兼容 URL 使用重定向而非重复页面）
  - **React/TS 实验前端**（6 标签页）
  - **10 种回测策略** + 参数优化器
  - **统一数据清洗层** + 数据质量标签
  - **龙头股动量轮动**系统
  - **KLineChart**（27 指标 + 17 画线工具）
  - **AI Research Center** + Portfolio + Ops Audit
- 输出"分析报告 + 投资建议 + 风控讨论 + 最终决策 + 可选执行路径"的
**多 Agent 金融研究/交易决策框架**（A 股标的研究 → advisory → 受控执行完整闭环）。

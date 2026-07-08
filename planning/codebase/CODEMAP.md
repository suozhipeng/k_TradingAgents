# CODEMAP

## 入口调用链

### 链路 1：脚本入口
`main.py`
```text
main.py
  -> TradingAgentsGraph(debug=True, config=config)
  -> ta.propagate("NVDA", "2024-05-10")
  -> TradingAgentsGraph._run_graph()
  -> graph.invoke()/graph.stream()
  -> process_signal(final_trade_decision)
```

### 链路 2：CLI 主入口
`pyproject.toml` -> `cli.main:app`

`tradingagents analyze`
```text
cli.main:app
  -> analyze()
  -> run_analysis(checkpoint=...)
  -> get_user_selections()
  -> TradingAgentsGraph(...)
  -> graph.resolve_instrument_context(...)
  -> graph.propagator.create_initial_state(...)
  -> graph.propagator.get_graph_args(...)
  -> graph.graph.stream(init_agent_state, **args)
  -> merge final_state
  -> graph.process_signal(final_state["final_trade_decision"])
  -> 保存 report / log / JSON
```

### 链路 3：A 股 research-only 入口（Phase 0–9）

```text
TradingAgentsGraph.propagate("600519.SH", date)
  -> is_astock_symbol()
  -> AStockGraphRuntime.run()
  -> AStockAnalyst
  -> Bull Researcher
  -> Bear Researcher
  -> Research Manager
  -> Phase 9 Advisory Chain
  |   (ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision)
  -> { no_exec } research-only:
  |     AStockGraphReport.to_legacy_state()
  |     execution_signal = ResearchOnly
  |-> { execution } Phase 10/11:
        -> BacktestEngine | PaperTrader | QmtExecution (managed)
        -> risk_gate (ATR stop, safety mode)
        -> execution_signal = ResearchOnly (default)
```

CLI 对 A 股标的生成 `AStockGraphReport` 并保存 `complete_report.md` 与
`astock_report.json`。Streamlit viewer 使用同一 schema。

Phase 9 advisory chain 合约输出始终携带 `actionable=false` 和
`execution_signal=ResearchOnly`。Phase 10 回测/模拟盘和 Phase 11
QMT 桥接可从 advisory chain 接收信号，但默认 safety mode 下
仍需人工确认后才执行。

当前链路完整流转（已验证端到端 live pipeline）：

```text
AStockDataRouter
  -> AStockInterface
  -> AStockAnalyst
  -> Bull/Bear Researcher
  -> Research Manager
  -> Advisory Chain (4 contracts)
  -> { CLI | Streamlit | BacktestEngine | PaperTrader | QmtExecution }
  -> AStockGraphReport -> 报告保存
```

## 核心类 / 函数

### 1. 图总控
#### `tradingagents.graph.trading_graph.TradingAgentsGraph`
职责：
- 初始化配置、目录、LLM、tool nodes、graph components
- 构造 LangGraph workflow
- 管理 checkpoint
- 注入 instrument identity / past memory
- 运行图并输出最终决策

关键方法：
- `__init__()`
- `_get_provider_kwargs()`
- `_create_tool_nodes()`
- `resolve_instrument_context()`
- `propagate()`
- `_run_graph()`
- `_log_state()`
- `process_signal()`
- `_resolve_pending_entries()`

### 2. 图装配
#### `tradingagents.graph.setup.GraphSetup`
职责：
- 创建所有 agent node / tool node
- 定义 StateGraph 节点与边
- 决定流程拓扑

关键方法：
- `setup_graph(selected_analysts)`

### 3. 条件跳转
#### `tradingagents.graph.conditional_logic.ConditionalLogic`
职责：
- 判断 analyst 是否继续调工具
- 判断 bull/bear debate 是否继续
- 判断 risk debate 是否继续

关键方法：
- `should_continue_market`
- `should_continue_social`
- `should_continue_news`
- `should_continue_fundamentals`
- `should_continue_debate`
- `should_continue_risk_analysis`

### 4. 状态传播
#### `tradingagents.graph.propagation.Propagator`
职责：
- 初始化 `AgentState`
- 注入 ticker/date/past_context/instrument_context
- 设置 recursion_limit / stream_mode / callbacks

关键方法：
- `create_initial_state()`
- `get_graph_args()`

### 5. 执行计划
#### `tradingagents.graph.analyst_execution`
职责：
- 维护 analyst key 与节点名映射
- 构建 analyst 执行计划
- 记录 analyst wall time

关键对象：
- `AnalystNodeSpec`
- `AnalystExecutionPlan`
- `ANALYST_NODE_SPECS`
- `build_analyst_execution_plan()`
- `AnalystWallTimeTracker`

### 6. 状态模型
#### `tradingagents.agents.utils.agent_states`
关键类型：
- `AgentState`
- `InvestDebateState`
- `RiskDebateState`

职责：
- 定义全局共享状态字段
- 决定所有节点之间如何交换数据

## 关键 Agent 工厂

### Analyst
- `create_market_analyst()`
- `create_sentiment_analyst()`
- `create_news_analyst()`
- `create_fundamentals_analyst()`

### Research
- `create_bull_researcher()`
- `create_bear_researcher()`
- `create_research_manager()`

### Trading / Risk / PM
- `create_trader()`
- `create_aggressive_debator()`
- `create_conservative_debator()`
- `create_neutral_debator()`
- `create_portfolio_manager()`

## 关键结构化输出组件

### `tradingagents.agents.schemas`
用途：
- 用 Pydantic 固化关键输出格式
- 再渲染回 Markdown 供下游与落盘使用

关键 schema：
- `ResearchPlan`
- `TraderProposal`
- `PortfolioDecision`
- `SentimentReport`

关键 render 函数：
- `render_research_plan()`
- `render_trader_proposal()`
- `render_pm_decision()`
- `render_sentiment_report()`（定义在后半段，分析时未完整展开，但文件明确存在）

## LLM 依赖关系

### 调用路径
```text
TradingAgentsGraph
  -> create_llm_client(provider, model, base_url, **kwargs)
  -> provider-specific client
  -> get_llm()
  -> agent node uses llm.invoke / llm.bind_tools / structured output
```

### 模块关系
- `llm_clients/factory.py`：路由入口
- `llm_clients/openai_client.py`：OpenAI-compatible providers
- `llm_clients/anthropic_client.py`
- `llm_clients/google_client.py`：代码文件仍在，但当前仓库已暂时屏蔽 Gemini provider
- `llm_clients/azure_client.py`
- `llm_clients/api_key_env.py`：环境变量映射

## 数据模块依赖关系

### agent_utils → tool 封装
`tradingagents.agents.utils.agent_utils`
- 统一导出工具函数：
  - `get_stock_data`
  - `get_indicators`
  - `get_fundamentals`
  - `get_balance_sheet`
  - `get_cashflow`
  - `get_income_statement`
  - `get_news`
  - `get_global_news`
  - `get_insider_transactions`
  - `get_verified_market_snapshot`
- 负责 instrument context / language instruction / message cleanup

### dataflows/interface.py`
职责：
- 方法名 → vendor 实现映射
- category/tool 级路由
- fallback 机制
- `NO_DATA_AVAILABLE` 统一哨兵返回

### 供应商实现
- Yahoo Finance：`y_finance.py` / `yfinance_news.py`
- Alpha Vantage：`alpha_vantage*.py`
- 社区数据：`reddit.py` / `stocktwits.py`

## CLI 依赖关系

### `cli/main.py`
依赖：
- `TradingAgentsGraph`
- `analyst_execution.py`
- `DEFAULT_CONFIG`
- `cli.models`
- `cli.utils`
- `cli.announcements`
- `cli.stats_handler`

功能链：
```text
用户输入
  -> 组装 config
  -> 构造 graph
  -> stream chunks
  -> 分类 message/tool calls
  -> 更新状态面板
  -> 保存 markdown/json/log
```

## 模块之间依赖总览
```text
cli/main.py
  -> tradingagents.graph.*
  -> tradingagents.default_config
  -> cli/utils.py / models.py / stats_handler.py

tradingagents.graph.trading_graph
  -> tradingagents.llm_clients.*
  -> tradingagents.agents.*
  -> tradingagents.dataflows.*
  -> graph/setup.py / propagation.py / conditional_logic.py / reflection.py / signal_processing.py / checkpointer.py

tradingagents.agents.*
  -> tradingagents.agents.utils.*
  -> tradingagents.agents.schemas
  -> tradingagents.dataflows.* (through tool wrappers or direct prefetch)

tradingagents.agents.utils.agent_utils
  -> tradingagents.dataflows.*
  -> yfinance (identity resolution)

tradingagents.dataflows.interface
  -> yfinance provider modules
  -> alpha_vantage provider modules
```

## 代码地图结论
最关键的“读代码主轴”建议顺序：
1. `main.py`
2. `cli/main.py`
3. `tradingagents/graph/trading_graph.py`
4. `tradingagents/graph/setup.py`
5. `tradingagents/graph/conditional_logic.py`
6. `tradingagents/agents/utils/agent_states.py`
7. `tradingagents/agents/{analysts,researchers,risk_mgmt,managers,trader}`
8. `tradingagents/agents/schemas.py`
9. `tradingagents/dataflows/interface.py`
10. `tradingagents/llm_clients/factory.py`

这样能最快把“入口 → 图 → 状态 → agent → 数据/模型适配”串起来。

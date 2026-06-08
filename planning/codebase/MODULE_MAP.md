# TradingAgents Module Map

> 生成范围：`README.md`、`cli/`、`tradingagents/`。
> 约束：只读分析业务代码；未运行真实交易；未调用外部金融数据 API。
> WebUI 数据源：`webui-data/modules.json` → 同步副本 `webui/src/data/modules.json`。

## Agent 执行主流程

```text
  Data Source
  → Analysts
  → Researchers
  → Trader
  → Risk Managers
  → Portfolio Manager
```

## 模块清单

| 模块 | 路径 | 类型 | 说明 | 主要风险 |
|---|---|---|---|---|
| README 架构与使用说明 | `README.md` | config | 项目级文档，描述 TradingAgents 多 Agent 金融研究框架、角色分工、CLI/包使用方式、API key、checkpoint、持久化与复现性限制。 | README 中包含示例运行代码，实际运行会调用 LLM/外部数据源；文档描述与源码细节可能存在滞后，需人工确认 |
| CLI 交互入口 | `cli/main.py` | cli | Typer/Questionary/Rich 命令行入口，采集 ticker、日期、分析师、LLM provider/model、研究深度、语言、checkpoint 等参数，并以 Rich Live 展示执行进度与报告。 | 执行 analyze 会触发真实 LLM 与外部数据源调用，本阶段不得运行；CLI 展示字段与 AgentState/report 字段强耦合；公告拉取包含外部网络调用，需避免在静态阶段执行 |
| CLI 配置、模型与统计辅助 | `cli/config.py / cli/models.py / cli/utils.py / cli/stats_handler.py` | cli | 封装 CLI 常量、分析师/资产枚举、UI 辅助函数与 LangChain 回调统计，用于把交互选择转换为图运行配置并展示运行指标。 | provider/model 名称与 llm_clients catalog 不一致时会运行失败；部分 UI 行为和统计字段需人工确认；公告配置含外部 URL，WebUI 不应静态加载时访问 |
| 默认运行配置 | `tradingagents/default_config.py` | config | 集中定义默认 LLM provider/model、路径、memory、checkpoint、输出语言、辩论轮次、递归限制、分析师并发、新闻抓取参数、数据 vendor 和 benchmark map，并支持 TRADINGAGENTS_* 环境变量覆盖。 | 路径或 API key 配置错误会影响全链路；默认数据源偏研究用途，非交易级数据；环境变量类型转换失败可能导致启动失败 |
| TradingAgentsGraph 总控编排 | `tradingagents/graph/trading_graph.py` | config | 核心编排类，初始化 LLM client、ToolNode、条件逻辑、GraphSetup、Propagator、Reflector、SignalProcessor、memory log 和 checkpoint，并通过 propagate/_run_graph 运行 LangGraph。 | 运行会调用 LLM 与外部行情/新闻数据，本阶段仅静态分析；会写 results/memory/checkpoint 等运行产物，WebUI 不应直接触发；节点名/状态字段字符串耦合 |
| LangGraph 流程构建与条件逻辑 | `tradingagents/graph/setup.py / conditional_logic.py / analyst_execution.py / propagation.py` | config | 构建 StateGraph 节点与边，按 selected_analysts 执行分析师工具循环，再进入多空研究辩论、研究经理、交易员、三方风险辩论、组合经理；ConditionalLogic 控制工具调用和辩论轮次，Propagator 初始化状态和递归限制。 | 节点名为字符串协议，重命名风险高；分析师并发配置的实际运行语义需人工确认；辩论轮次边界依赖 count 字段 |
| Checkpoint / Reflection / Signal 支撑 | `tradingagents/graph/checkpointer.py / reflection.py / signal_processing.py` | config | 提供 per-ticker SQLite checkpoint resume、历史决策反思、以及最终文本信号到核心交易动作的处理。 | checkpoint 会写入本地 SQLite，WebUI 静态阶段不得触发；反思会调用 LLM，结果不确定；信号解析规则需随 PortfolioDecision 输出同步 |
| AgentState 状态模型 | `tradingagents/agents/utils/agent_states.py` | config | 定义多 Agent 共享 TypedDict 状态，包括标的、资产类型、instrument_context、日期、消息、四类分析报告、投资辩论、交易计划、风险辩论、最终决策和 past_context。 | 字段名被图、Agent、日志和 CLI 渲染复用，重构需全局同步；TypedDict 不保证运行期完整校验，部分字段语义需人工确认 |
| Agent 工具门面与标的上下文 | `tradingagents/agents/utils/agent_utils.py` | dataflow | 聚合核心股票、技术指标、基本面、新闻与市场数据校验工具，提供 instrument identity/context 构建和消息清理节点。 | resolve_instrument_identity 可能访问 yfinance，静态阶段不得执行；标的身份解析失败时会 fail-open，需人工复核；工具门面是多个分析师共用入口 |
| Market / Technical Analyst | `tradingagents/agents/analysts/market_analyst.py` | analyst | 市场/技术分析师节点，基于行情与技术指标工具生成 market_report，并强调价格/指标需由工具数据支撑。 | 技术分析依赖行情数据质量；LLM 可能误解指标，需人工复核；不同市场 ticker 后缀和 benchmark 口径可能不一致 |
| Sentiment Analyst（Social 兼容键） | `tradingagents/agents/analysts/sentiment_analyst.py / social_media_analyst.py` | analyst | 情绪分析师，整合新闻、StockTwits、Reddit 等信号生成 sentiment_report。 | social / news / forum 信号噪声高且覆盖不均；外部源限流或不可用时结果不稳定；结构化输出失败路径需人工确认 |
| News Analyst | `tradingagents/agents/analysts/news_analyst.py` | analyst | 新闻分析师节点，调用公司新闻、全球宏观新闻和内部交易工具，评估事件与宏观影响并生成 news_report。 | 新闻源覆盖、时效性、限流和去重质量不稳定；LLM 对新闻影响的解释需人工复核；global_news_queries 的市场适配性需人工确认 |
| Fundamentals Analyst | `tradingagents/agents/analysts/fundamentals_analyst.py` | analyst | 基本面分析师节点，调用公司概况、资产负债表、现金流和利润表等工具，生成 fundamentals_report。 | 非美股/加密资产基本面覆盖需人工确认；财务字段口径和币种可能不一致；数据缺失时 LLM 不应编造 |
| Bull Researcher | `tradingagents/agents/researchers/bull_researcher.py` | researcher | 多头研究员，读取分析师报告和当前 investment_debate_state，提出看多论据并追加到 bull_history/history。 | LLM 可能放大单侧乐观观点；辩论终止依赖 count 与 current_response 前缀；轮次配置影响观点充分性 |
| Bear Researcher | `tradingagents/agents/researchers/bear_researcher.py` | researcher | 空头研究员，读取分析师报告、多头历史和辩论状态，提出风险/看空论据并追加到 bear_history/history。 | LLM 可能放大单侧悲观观点；current_response 前缀作为路由依据较脆弱；debate_state 字段完整语义需人工确认 |
| Research Manager | `tradingagents/agents/managers/research_manager.py` | researcher | 研究经理，汇总分析师报告和多空辩论，使用 ResearchPlan 结构化输出生成 investment_plan/judge_decision。 | 结构化输出在不同 provider 下可能失败并降级；ResearchPlan 字段变更会影响下游 Trader；需人工确认 schema 与 UI 展示一致性 |
| Trader Agent | `tradingagents/agents/trader/trader.py` | trader | 交易员 Agent，基于 investment_plan、分析师报告和 past_context 生成 TraderProposal/trader_investment_plan。 | 输出含交易建议色彩，不能用于自动实盘下单；entry/target/stop/position 等字段需合规与人工复核；历史 past_context 可能引入偏差 |
| Risk Management Team | `tradingagents/agents/risk_mgmt/*.py` | risk | 激进、保守、中性三类风险辩论节点，围绕 trader_investment_plan 形成 risk_debate_state，按 ConditionalLogic 循环后交给 Portfolio Manager。 | 风控讨论不等同真实账户风控；三方循环顺序与终止条件依赖 latest_speaker/count；风险偏好映射到真实仓位需人工确认 |
| Portfolio Manager | `tradingagents/agents/managers/portfolio_manager.py` | risk | 组合经理，汇总风险辩论、交易计划与历史 context，使用 PortfolioDecision 结构化输出生成 final_trade_decision。 | 最终输出可能是 Buy/Hold/Sell 等建议，不构成投资建议；结构化决策解析需人工复核；历史 memory context 可能影响判断 |
| Dataflow Interface 与 Vendor 路由 | `tradingagents/dataflows/interface.py / config.py` | dataflow | 数据访问门面，按 core_stock_apis、technical_indicators、fundamental_data、news_data 分类路由到 yfinance 或 alpha_vantage，并提供 fallback、限流和无数据处理。 | 外部 API 限流、网络失败、缺失和 vendor 口径不一致；fallback 可能掩盖 primary vendor 问题；静态 WebUI 不得调用这些接口 |
| Yahoo Finance Dataflows | `tradingagents/dataflows/y_finance.py / yfinance_news.py / stockstats_utils.py` | dataflow | Yahoo Finance 行情、公司信息、财报、内部交易和新闻适配；stockstats_utils 支撑技术指标计算。 | Yahoo 数据非交易级，不保证实时性/完整性；多市场 ticker 后缀和公司身份解析需人工确认；历史/当前新闻的时间一致性限制见 README |
| StockTwits Dataflow | `tradingagents/dataflows/stocktwits.py` | dataflow | StockTwits 社媒消息抓取与标准化适配，用于情绪分析节点的短期市场情绪输入。 | 覆盖面与采样偏差较高；外部平台速率限制或内容变化会影响结果；不应被 WebUI 误认为交易执行接口 |
| Reddit Dataflow | `tradingagents/dataflows/reddit.py` | dataflow | Reddit 帖子与讨论抓取适配，用于补充情绪分析与社区观点输入。 | 话题噪声与机器人内容较高；限流与分页导致样本不完整；不应被 WebUI 误认为交易执行接口 |
| Alpha Vantage Dataflows | `tradingagents/dataflows/alpha_vantage*.py` | dataflow | Alpha Vantage 股票、技术指标、新闻、全球新闻、基本面、财报和内部交易适配/备用路径。 | API key、限流、付费层级和 region 可用性影响结果；与 Yahoo Finance 口径可能不一致；无 key 时 fallback 行为需人工确认 |
| Symbol 与市场数据校验 | `tradingagents/dataflows/symbol_utils.py / market_data_validator.py / utils.py` | dataflow | 提供 ticker 安全路径组件、市场 symbol 解析/无数据异常、以及市场数据快照校验，防止路径穿越和价格/指标幻觉。 | 校验覆盖范围需人工确认；ticker 标准化可能影响非美市场/加密资产；路径安全规则变更需与日志/checkpoint 同步 |
| LLM Client Factory 与 Model Catalog | `tradingagents/llm_clients/*.py` | config | 统一构建 OpenAI、Anthropic、Google/Gemini、Azure、OpenRouter/Ollama/OpenAI-compatible、DeepSeek、Qwen、GLM、MiniMax、xAI 等 LLM 客户端，并维护模型能力、API key 环境变量和校验逻辑。 | provider/API key/base_url 配置错误会导致运行失败；模型结构化输出和工具调用能力差异影响 Agent；不同 provider 的 reasoning/temperature 语义不一致 |
| Structured Output Schemas | `tradingagents/agents/schemas.py / agents/utils/structured.py / rating.py` | config | Pydantic schema 与渲染/降级工具，定义并格式化 SentimentReport、ResearchPlan、TraderProposal、PortfolioDecision 等结构化输出和五档 rating。 | schema 变更会影响多个 Agent 和 UI 展示；部分 provider 不稳定支持结构化输出；降级解析准确性需人工确认 |
| Memory Log 持久化 | `tradingagents/agents/utils/memory.py` | config | 维护历史交易决策日志，支持 pending outcome、同标的历史上下文、跨标的 lessons，并向 Trader/Portfolio Manager 注入 past_context。 | 会写用户 home 下持久化文件，本阶段不得运行；历史记忆可能引入偏差；收益回填依赖 yfinance 价格数据和 benchmark map |

## 数据与状态流

1. CLI 或包调用入口提供 `ticker`、`trade_date`、分析师列表、LLM provider/model 和运行配置。
2. `TradingAgentsGraph` 初始化 LLM、工具节点、条件逻辑、图结构与 checkpoint/logging。
3. Analyst 节点通过工具节点读取数据源并写入 `market_report`、`sentiment_report`、`news_report`、`fundamentals_report`。
4. Bull/Bear Researcher 读取分析师报告并写入 `investment_debate_state`。
5. Research Manager 汇总辩论生成 `investment_plan`。
6. Trader 生成 `trader_investment_plan`。
7. Risk Management Team 写入 `risk_debate_state`。
8. Portfolio Manager 输出 `final_trade_decision`。

## 重点覆盖说明

- `analysts`：市场/技术、情绪/社媒、新闻、基本面。
- `researchers`：Bull / Bear / Research Manager。
- `trader`：交易员 Agent。
- `risk managers`：激进 / 中性 / 保守风险辩论与组合经理。
- `dataflows`：Yahoo Finance、Alpha Vantage、StockTwits、Reddit、接口门面与校验。
- `graph`：由 `tradingagents/graph/*` 的 config 项覆盖，尤其是 `trading_graph.py`、`setup.py`、`conditional_logic.py`、`analyst_execution.py`。
- `cli`：交互入口与配置/统计辅助。
- `config`：默认配置、LLM client factory、schema、checkpoint / reflection / signal 支撑。

## 需人工确认

- 分析师并发与 tool loop 的真实运行边界。
- 不同市场 ticker 的 Yahoo / Alpha Vantage 口径差异。
- 结构化 schema 在不同 LLM provider 下的失败降级路径。
- checkpoint resume 与 memory/reflection 的边界行为。

## WebUI 使用说明

- 静态文件：`webui/src/data/modules.json`
- WebUI 不直接 import 或执行 TradingAgents 业务代码。
- WebUI 只读展示模块树、详情、风险与 Agent Flow。

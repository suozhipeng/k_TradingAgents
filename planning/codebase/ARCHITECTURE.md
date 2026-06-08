# ARCHITECTURE

## 总体架构
本项目是一个基于 **LangGraph 状态图** 的多 Agent 金融研究与决策流水线。

核心对象：`tradingagents.graph.trading_graph.TradingAgentsGraph`

它将系统拆成五个阶段：
1. 分析师阶段（Analyst Team）
2. 多空研究辩论阶段（Research Team）
3. 交易方案阶段（Trader）
4. 风险辩论阶段（Risk Management Team）
5. 最终组合决策阶段（Portfolio Manager）

## 多 Agent 角色划分

### Analyst Team
负责生成基础研究报告：
- `Market Analyst`
  - 关注价格、OHLCV、技术指标、验证快照
- `Sentiment Analyst`
  - 关注新闻、StockTwits、Reddit 的多源情绪
- `News Analyst`
  - 关注新闻、全球宏观新闻、insider transaction
- `Fundamentals Analyst`
  - 关注财务与基本面数据

### Research Team
- `Bull Researcher`
  - 基于四类分析报告构建看多论证
- `Bear Researcher`
  - 基于四类分析报告构建看空论证
- `Research Manager`
  - 汇总 bull/bear 辩论，输出结构化 `ResearchPlan`

### Trader
- `Trader`
  - 将 `ResearchPlan` 转为交易提案 `TraderProposal`
  - 包含 action / reasoning / entry / stop_loss / sizing

### Risk Management Team
- `Aggressive Analyst`
  - 强调高收益/高风险机会
- `Conservative Analyst`
  - 强调回撤、保守配置、风险暴露
- `Neutral Analyst`
  - 试图平衡两边观点

### Portfolio Manager
- `Portfolio Manager`
  - 综合风险辩论、研究计划、交易提案、历史教训
  - 输出最终结构化 `PortfolioDecision`

## 调用关系

### 图级顺序（来自 `graph/setup.py`）
```text
START
  -> [Selected Analysts in sequence]
  -> Bull Researcher
  <-> Bear Researcher   (按轮次往返)
  -> Research Manager
  -> Trader
  -> Aggressive Analyst
  -> Conservative Analyst
  -> Neutral Analyst
  -> ... (风险辩论按轮次循环)
  -> Portfolio Manager
  -> END
```

### Analyst 阶段调用关系
每个 analyst 都遵循相同模式：
```text
Analyst Node
  -> 若 LLM 发起 tool_calls
      -> ToolNode
      -> 回到同一个 Analyst Node
  -> 若无 tool_calls
      -> Msg Clear Node
      -> 下一个 Analyst
```

对应条件逻辑见：
- `ConditionalLogic.should_continue_market`
- `should_continue_social`
- `should_continue_news`
- `should_continue_fundamentals`

### 研究辩论调用关系
```text
Bull Researcher
  -> Bear Researcher 或 Research Manager
Bear Researcher
  -> Bull Researcher 或 Research Manager
```
停止条件：
- `investment_debate_state.count >= 2 * max_debate_rounds`
- 到达上限后进入 `Research Manager`

### 风险辩论调用关系
```text
Aggressive Analyst
  -> Conservative Analyst 或 Portfolio Manager
Conservative Analyst
  -> Neutral Analyst 或 Portfolio Manager
Neutral Analyst
  -> Aggressive Analyst 或 Portfolio Manager
```
停止条件：
- `risk_debate_state.count >= 3 * max_risk_discuss_rounds`
- 到达上限后进入 `Portfolio Manager`

## 数据流

## 1. 输入数据
运行输入：
- ticker
- trade_date
- asset_type（stock / crypto）
- provider / model / language / rounds 等配置

初始化状态由 `Propagator.create_initial_state()` 构造，放入：
- `company_of_interest`
- `asset_type`
- `trade_date`
- `instrument_context`
- `past_context`
- 各类 report / debate state 初值

## 2. 外部数据进入方式
### Analyst 工具链
- Market Analyst：`get_stock_data` / `get_indicators` / `get_verified_market_snapshot`
- News Analyst：`get_news` / `get_global_news` / `get_insider_transactions`
- Fundamentals Analyst：`get_fundamentals` / `get_balance_sheet` / `get_cashflow` / `get_income_statement`
- Sentiment Analyst：预抓取 `Yahoo Finance news + StockTwits + Reddit`

### 数据适配层
`dataflows/interface.py` 负责：
- category/tool → vendor 路由
- `yfinance` / `alpha_vantage` fallback
- `NO_DATA_AVAILABLE` 哨兵返回

## 3. 中间产物
分析阶段输出：
- `market_report`
- `sentiment_report`
- `news_report`
- `fundamentals_report`

研究辩论阶段输出：
- `investment_debate_state`
- `investment_plan`

交易阶段输出：
- `trader_investment_plan`

风险辩论阶段输出：
- `risk_debate_state`

最终输出：
- `final_trade_decision`
- 由 `SignalProcessor.process_signal()` 解析为最终 rating

## 决策流

### 第一层：事实采集与专题分析
四类 analyst 各自产生专题报告。

### 第二层：看多 / 看空对抗
Bull / Bear Researcher 基于专题报告辩论，Research Manager 裁决并形成中间投资计划。

### 第三层：交易动作设计
Trader 将“投资计划”翻译成更接近执行层的交易建议（买/卖/持有、入场价、止损、仓位）。

### 第四层：风险偏好冲突
三位风险角色围绕 trader proposal 进行再辩论。

### 第五层：最终组合裁决
Portfolio Manager 汇总：
- risk debate history
- research plan
- trader proposal
- memory/past_context

并输出最终 5 档评级：
- Buy
- Overweight
- Hold
- Underweight
- Sell

## 记忆与反思层
并非主图节点，但会影响后续运行：
- 启动时：`TradingMemoryLog.get_past_context(company_name)` 注入历史经验
- 下次同 ticker 运行前：`_resolve_pending_entries()` 计算过去决策收益、生成 reflection
- Portfolio Manager prompt 中可使用 `past_context`

这意味着系统具备“延迟反馈型经验回注”能力，但不是在线学习模型，而是**文本记忆增强**。

## 架构特点总结

### 优点
- Agent 职责划分清晰
- 图编排透明，便于插拔新节点
- 数据源与模型 provider 已抽象
- 结构化输出覆盖关键决策节点
- 支持 checkpoint / resume

### 局限
- 决策仍是 LLM 文本推理主导
- 没有真实订单执行/风控引擎闭环
- 数据源多依赖公网与第三方服务
- analyst 仍基本按顺序执行，不是真并行执行图

## 面向 A 股改造的架构启示
如果改造成“A 股辅助看盘系统”，建议保留：
- LangGraph 编排层
- Analyst / Research / Risk / PM 多角色结构

需要替换/新增：
- A 股数据源适配层
- 行业/题材/资金流/涨停板特化分析师
- 中文资讯/公告/研报数据流
- 面向“看盘辅助”而非“交易执行建议”的输出 schema
# A 股 Web 工作台竞品能力对齐与重构 TODO

| 状态：待审核 | 版本：v0.1 | 日期：2026-06-27 |

本文是下一阶段严格执行前的需求冻结稿。它只定义目标、边界、阶段和验收标准，不表示任何功能已经完成。

目标是同时解决三个问题：

1. 补齐 `daily_stock_analysis` 与 `aiagents-stock` 的核心用户可见能力。
2. 保留并突出本项目已有的 TradingAgents-Astock 重型能力：多智能体投研、回测、策略优化、模拟盘、风控归因、审计和受控执行。
3. 重构当前 Web 工作台，使它从“功能页面堆叠”变成“每日可用的 A 股投研交易工作台”。

## 1. 产品定位

### 1.1 新定位

TradingAgents-Astock Web 工作台定位为：

> 面向 A 股的本地化 AI 投研交易工作台，覆盖每日自动分析、实时盯盘、AI 多智能体研判、策略回测、模拟盘、风控归因、审计与受控执行。

### 1.2 不再采用的定位

以下方向不作为主定位：

- 只做每日荐股报告。
- 只做 Streamlit 盯盘页面。
- 只做 TradingView 风格交易终端。
- 只做自动实盘交易工具。
- 继续横向堆页面但不打通用户路径。

### 1.3 差异化

与 `daily_stock_analysis` 对比，本项目必须补齐其每日分析、推送、报告归档和工作台体验，但差异化在于：

- 分析结果进入结构化 advisory chain，而不是只停留在文本报告。
- 报告、回测、风控、模拟盘和审计可以串联。
- 所有交易相关输出默认保持 `research_only` / `actionable=false`，避免把 AI 文本直接变成实盘指令。

与 `aiagents-stock` 对比，本项目必须补齐其实时盯盘、主力资金、板块轮动、龙虎榜、持仓监控、告警和 QMT/miniQMT 入口，但差异化在于：

- 不把自动交易作为默认卖点。
- QMT/miniQMT 只进入受控执行路径，必须经过风控和人工确认。
- 重点建设数据质量、回测反偏差、组合风险、审计和可验证验收。

## 2. 参考项目能力边界

### 2.0 重点参考项目分层

本轮调研后，后续 Web 工作台和产品主线优先参考以下 8 个项目。它们不是照抄对象，而是分别提供产品入口、工作流、架构、数据层、量化研究、交易执行和模型治理参考。

| 项目 | 主要优势 | 本项目吸收方式 |
|---|---|---|
| `daily_stock_analysis` | 每日自动分析、决策仪表盘、报告归档、多渠道推送、低门槛部署 | 作为 Web-P2 的每日分析、任务进度、报告归档和推送闭环标杆 |
| `aiagents-stock` | A 股实时盯盘、主力资金、龙虎榜、北向资金、板块轮动、告警、miniQMT 入口 | 作为 Web-P3 的盯盘中心、告警、持仓监控和受控执行入口标杆 |
| `OpenBB` | 面向分析师、量化和 AI Agent 的金融数据平台 | 作为 Data & Ops 的数据 provider、统一工具层、Agent-ready 数据接口参考 |
| `microsoft/qlib` | AI-oriented Quant 投研平台，覆盖数据、模型、实验、回测到生产研究流程 | 作为 Strategy Lab 的实验管理、数据集、模型/策略研究和结果可复现参考 |
| `vn.py` | 国内量化交易框架，事件驱动、交易接口、网关和实盘工程经验丰富 | 作为 Trading & Execution 的事件模型、委托/成交/撤单状态和 broker gateway 参考 |
| `FinGPT` | 金融大模型、金融 NLP、训练/评测/治理资料 | 作为 AI Research Center 的金融 LLM、prompt/模型治理和报告可信度参考 |
| `AgentQuant` | AI Agent 将股票列表转为可回测策略，强调无代码策略生成和验证 | 作为 AI 研究到 Strategy Lab 的桥梁：AI 结论必须进入回测验证而非直接交易 |
| `WyckoffTradingAgent` | A 股量价分析 Agent、screener、CLI/MCP 工具 | 作为盯盘中心和选股器中的量价/筹码/形态分析参考 |

### 2.1 daily_stock_analysis 需要对齐的能力

参考项目当前公开 README 中的关键能力包括：

- A 股、港股、美股、ETF 等多市场自选股智能分析。
- 每日自动分析并推送决策仪表盘。
- 企业微信、飞书、Telegram、Discord、Slack、邮件推送。
- Web / 桌面工作台。
- 手动分析、任务进度、历史报告、完整 Markdown、回测、持仓、配置管理、浅色 / 深色主题。
- Agent 策略问股，多轮追问，多种内置策略。
- 图片、CSV/Excel、剪贴板导入。
- 股票代码、名称、拼音、别名补全。
- GitHub Actions、Docker、本地定时任务、FastAPI 服务部署。
- 多数据源聚合：行情、K 线、技术指标、资金流、筹码、新闻、公告和基本面。

本项目的对齐原则：

- P0 先覆盖 A 股，不在第一轮追求全市场同等能力。
- P0 必须有每日分析、报告归档、任务状态和推送配置入口。
- 多市场扩展进入 P2，避免拖慢 A 股主路径。

### 2.2 aiagents-stock 需要对齐的能力

参考项目当前公开 README 中的关键能力包括：

- Streamlit + DeepSeek 的 A 股智能股票分析。
- 多 AI 智能体股票团队分析。
- 实时行情、K 线、技术指标。
- 主力选股、批量分析、历史记录。
- 龙虎榜、主力资金、板块轮动、北向资金。
- 宏观周期、宏观数据、行业映射和优质标的筛选。
- 低估值、高股息、小市值、净利增长、低价股等策略选股。
- 策略监控、卖出提醒、定时扫描。
- AI 盯盘、实时监测、按交易时段启动。
- DeepSeek AI 决策、持仓管理、邮件/Webhook 通知。
- miniQMT 实盘/模拟交易入口，T+1 规则适配。

本项目的对齐原则：

- P0/P1 补齐实时盯盘、板块/龙头/资金线索、持仓告警和 AI 批量分析。
- 策略选股要接入本项目 Strategy Lab，不复制零散策略页面。
- miniQMT/QMT 入口必须归入 Trading & Execution，默认禁用自动实盘。

### 2.3 其他高热度项目的参考边界

以下项目不直接作为竞品功能矩阵，但作为工程实现参考：

| 项目 | 参考方向 | 不直接照搬的原因 |
|---|---|---|
| `TauricResearch/TradingAgents` | 原始多智能体投研底座 | 本项目已基于该底座扩展，不重复定义 |
| `FinRL` | 强化学习交易研究 | P0/P1 不做 RL 交易主线，避免扩大范围 |
| `backtrader` / `backtesting.py` / `vectorbt` | 回测 API、指标、结果呈现、批量策略评估 | 本项目已有 backtrader 相关能力，优先统一现有 Strategy Lab |
| `QuantConnect/Lean` / `NautilusTrader` | 生产级回测/实盘统一、事件驱动执行 | 只吸收状态模型和执行严谨性，不在本阶段重写引擎 |
| `akshare` / `tushare` / `yfinance` | 数据源能力和边界 | 作为 provider，不作为产品形态参考 |
| `CrewAI` / `AutoGen` / `LangGraph` | Agent 编排模式 | 本项目保留 TradingAgents/LangGraph 主链，不换框架 |

## 3. 当前 Web 工作台主要问题

### 3.1 信息架构问题

- `/dashboard` 更像系统指标页，不像用户每日打开的工作台。
- `/` 默认进入交易页，用户还没完成分析、盯盘、报告、告警判断就被推到下单界面。
- 顶层导航同时暴露交易、策略、研究、市场龙头、数据健康、运维审计，主次不清。
- `market_leaders` 使用 iframe 聚合旧页面，体验像临时拼装。
- 旧入口、兼容入口和新版入口混在一起，用户不知道哪个是主路径。

### 3.2 视觉与交互问题

- 页面风格混杂：TradingView 深色终端、iframe 聚合页、旧页面、独立页面样式各不相同。
- 大量页面使用局部 inline style，难以统一维护。
- 卡片密度、字号、间距、按钮样式、状态标签缺少统一规范。
- 首页缺少“下一步动作”，用户看到指标后不知道该分析、回测、盯盘还是生成报告。
- 空态、错误态、降级态、缓存态、mock/paper/managed 标签不统一。

### 3.3 产品感知问题

- 用户第一屏感知不到每日分析、报告推送、自选股、告警这些高频价值。
- 已有重型能力很多，但没有被串成一条路径。
- AI 研究、策略实验室、组合风控、模拟盘、审计之间缺少工作流连接。

## 4. 目标信息架构

### 4.1 顶层模块

Web 工作台最终收敛为以下顶层模块：

| 模块 | 目标 | 默认能力等级 |
|---|---|---|
| 今日工作台 | 每日市场、自选股、AI 任务、报告、告警和数据健康总入口 | research |
| 盯盘中心 | 实时行情、板块、龙头、资金、龙虎榜、北向、条件告警 | research |
| AI 研究 | 单股、多股、主题、行业、持仓组合的多智能体研究 | research |
| 策略实验室 | 选股、回测、优化、对比、walk-forward、反偏差检查 | research / paper |
| 组合与风控 | 持仓、VaR、集中度、归因、压力测试、风险拦截 | paper / managed |
| 交易执行 | 模拟盘、QMT/miniQMT、人工确认、订单审计 | paper / managed |
| 系统与配置 | 数据源、模型、推送、任务调度、审计、健康检查 | ops |

### 4.2 首页第一屏必须回答的问题

新的 `/dashboard` 必须回答：

1. 今天市场怎么样？
2. 我的自选股和持仓有没有异动？
3. AI 今天建议重点看哪些标的或主题？
4. 哪些报告已经生成，哪些还在排队或失败？
5. 有没有风险、告警或数据异常？
6. 下一步可以做什么：分析、回测、盯盘、生成报告、配置推送、进入模拟盘？

### 4.3 默认入口

- `/dashboard` 是产品默认入口。
- `/` 可以 302 到 `/dashboard`，或保留交易页但必须从顶层入口降级为二级入口。
- `trading.html` 不再作为新用户第一屏。
- 旧入口保留兼容，但必须显示迁移提示，并在后续 phase 逐步下线或转为内部 tab。

## 5. 竞品能力对齐矩阵

### 5.1 daily_stock_analysis 对齐矩阵

| 编号 | 能力 | 目标状态 | 优先级 | 归属模块 | 验收标准 |
|---|---|---|---|---|---|
| DSA-01 | 每日自动市场复盘 | 新增或整合 | P0 | 今日工作台 / AI 研究 | 可按交易日生成市场复盘，含指数、涨跌家数、板块、风险摘要 |
| DSA-02 | 自选股批量分析 | 新增或整合 | P0 | 今日工作台 / AI 研究 | 用户可维护 watchlist，并批量生成 AI 摘要和评分 |
| DSA-03 | 决策仪表盘摘要 | 新增 | P0 | 今日工作台 | 首页展示买入/观望/卖出或 research-only 等级摘要，但不得直接标成可执行指令 |
| DSA-04 | 历史报告归档 | 整合 | P0 | AI 研究 / 报告中心 | 报告有 symbol、日期、模型、数据快照、状态和查看入口 |
| DSA-05 | 任务进度 | 新增 | P0 | 今日工作台 / 系统 | 分析任务有 queued/running/succeeded/failed/cancelled 状态 |
| DSA-06 | 推送配置 | 新增 | P1 | 系统与配置 | 支持至少一种本地可验证通道；其他通道可先配置占位但标注未验证 |
| DSA-07 | 定时任务 | 新增 | P1 | 系统与配置 | 支持本地 cron/APScheduler 触发每日分析；GitHub Actions 作为后续部署方案 |
| DSA-08 | Web 工作台任务页 | 重构 | P0 | 今日工作台 | 首页可手动触发、查看进度、查看最近报告 |
| DSA-09 | 完整 Markdown 报告 | 整合 | P0 | 报告中心 | Web 可查看完整 Markdown，支持 JSON 下载 |
| DSA-10 | 多轮问股 | 后置 | P2 | AI 研究 | 支持围绕单个 symbol 的上下文追问和报告引用 |
| DSA-11 | 图片/CSV/Excel 导入 | 后置 | P2 | 今日工作台 / AI 研究 | 支持导入 watchlist 或持仓，导入失败有可读错误 |
| DSA-12 | 代码/名称/拼音补全 | 增强 | P1 | 全局搜索 | 全局搜索和输入框统一补全 |
| DSA-13 | 多市场同等支持 | 后置 | P2 | 数据 / AI 研究 | A 股稳定后扩展港股/美股；不得影响 A 股主路径 |

### 5.2 aiagents-stock 对齐矩阵

| 编号 | 能力 | 目标状态 | 优先级 | 归属模块 | 验收标准 |
|---|---|---|---|---|---|
| AIS-01 | 实时盯盘 | 整合 | P0 | 盯盘中心 | 自选股列表展示实时/缓存状态、涨跌幅、成交额、更新时间 |
| AIS-02 | AI 盯盘摘要 | 新增 | P1 | 盯盘中心 / AI 研究 | 对异动股票生成短摘要，标注数据来源和模型 |
| AIS-03 | 主力资金 | 整合或新增 | P1 | 盯盘中心 | 显示资金流入/流出、来源、刷新时间和降级态 |
| AIS-04 | 龙虎榜 | 整合 | P1 | 盯盘中心 | 不再作为孤立旧入口，进入盯盘中心 tab |
| AIS-05 | 北向资金 | 整合 | P1 | 盯盘中心 | 不再作为孤立旧入口，进入盯盘中心 tab |
| AIS-06 | 板块轮动 | 整合 | P0 | 盯盘中心 / 策略实验室 | 首页有板块强弱摘要，详细页有轮动/回测入口 |
| AIS-07 | 主力选股批量分析 | 新增或整合 | P1 | AI 研究 / 策略实验室 | 可对候选池批量分析，保存历史记录 |
| AIS-08 | 策略监控 | 新增 | P1 | 策略实验室 / 盯盘中心 | 策略信号可加入监控，生成告警，不直接下单 |
| AIS-09 | 持仓监控 | 整合 | P0 | 今日工作台 / 组合与风控 | 首页展示持仓风险、盈亏、集中度和告警 |
| AIS-10 | 条件告警 | 新增 | P1 | 盯盘中心 / 系统 | 支持价格、涨跌幅、成交量、策略信号、风控告警 |
| AIS-11 | 宏观分析 | 后置 | P2 | AI 研究 | 宏观数据、政策、行业映射进入主题研究，不抢 P0 |
| AIS-12 | DeepSeek/本地模型配置 | 整合 | P1 | 系统与配置 | 模型配置可见，研究任务记录模型和 prompt 版本 |
| AIS-13 | miniQMT/QMT 入口 | 整合 | P1 | 交易执行 | 默认 managed/paper，必须人工确认；自动实盘为显式高级开关 |
| AIS-14 | T+1 规则适配 | 强化 | P1 | 交易执行 / 策略实验室 | 回测、模拟盘、受控执行路径均标注 T+1 约束 |

### 5.3 本项目现有重型能力矩阵

| 编号 | 能力 | 保留方式 | 优先级 | 归属模块 | 验收标准 |
|---|---|---|---|---|---|
| TA-01 | TradingAgents 多智能体研究链 | 保留并作为 AI 研究核心 | P0 | AI 研究 | 页面显示 researcher/trader/risk/portfolio 分层结果 |
| TA-02 | advisory chain | 强化 | P0 | AI 研究 / 风控 | ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision 可追溯 |
| TA-03 | `research_only` 安全边界 | 强制 | P0 | 全局 | 所有 AI 输出默认 `actionable=false` |
| TA-04 | 回测引擎 | 整合 | P0 | 策略实验室 | 今日工作台可进入最近回测和一键回测 |
| TA-05 | 参数优化 | 保留 | P1 | 策略实验室 | 结果可与报告和策略监控关联 |
| TA-06 | Walk-forward / 反偏差 | 突出 | P1 | 策略实验室 | 回测结果显示数据质量、样本外和偏差检查 |
| TA-07 | 模拟盘 | 整合 | P0 | 组合与风控 / 交易执行 | 首页显示 paper 状态，不伪装为真实账户 |
| TA-08 | QMT 受控执行 | 限制开放 | P1 | 交易执行 | QMT 不可用时 disabled 或降级 paper；实盘必须确认 |
| TA-09 | 组合 VaR / 集中度 / 归因 | 突出 | P0 | 组合与风控 | 首页显示关键风险摘要，详细页显示归因 |
| TA-10 | 审计中心 | 串联 | P1 | 系统与配置 / 交易执行 | AI 报告、风控、交易确认、订单回报有审计记录 |
| TA-11 | 数据健康 | 提升 | P0 | 今日工作台 / 系统 | 首页显示 provider 健康、缓存、降级和 stale 状态 |
| TA-12 | API 契约和测试基线 | 保留 | P0 | 全局 | 每个 phase 必须更新测试和文档证据 |

### 5.4 八个重点参考项目落地矩阵

| 编号 | 参考项目 | 可吸收能力 | 落地模块 | Phase | 验收标准 |
|---|---|---|---|---|---|
| REF-01 | `daily_stock_analysis` | 每日自动分析、报告归档、推送摘要、任务状态 | 今日工作台 / AI 研究 / 系统配置 | Web-P2 | 手动或定时触发后，首页可看到任务、报告、失败原因和推送状态 |
| REF-02 | `aiagents-stock` | A 股盯盘、主力资金、龙虎榜、北向、告警、miniQMT 入口 | 盯盘中心 / 交易执行 | Web-P3 / Web-P6 | 盯盘中心不再 iframe 拼装；告警不直接下单；QMT/miniQMT 默认 managed/paper |
| REF-03 | `OpenBB` | Agent-ready 金融数据工具层、数据源统一抽象 | Data & Ops / API | Web-P3 起 | dashboard/AI/策略调用同一数据接口，输出 source、updated_at、stale、degraded |
| REF-04 | `microsoft/qlib` | 数据集、实验、模型/策略结果可复现 | Strategy Lab | Web-P5 | 回测和优化结果包含数据快照、参数、模型/策略版本和实验记录 |
| REF-05 | `vn.py` | 事件驱动交易状态、gateway、委托/成交/撤单模型 | Trading & Execution | Web-P6 | paper/managed 执行统一订单生命周期，QMT 不可用时状态明确 |
| REF-06 | `FinGPT` | 金融 LLM 治理、金融语料/任务、模型评测 | AI Research Center | Web-P4 | AI 任务记录模型、prompt 版本、输入数据、引用和 advisory 标记 |
| REF-07 | `AgentQuant` | AI 生成/筛选策略后进入回测验证 | AI 研究 / Strategy Lab | Web-P4 / Web-P5 | AI 结论能转为策略候选或回测任务，但不能直接转真实订单 |
| REF-08 | `WyckoffTradingAgent` | A 股量价分析、screener、CLI/MCP 风格工具 | 盯盘中心 / 选股器 | Web-P3 / Web-P5 | 选股和盯盘加入量价/形态/筹码类信号，并保留数据来源和解释 |

## 6. 新工作流设计

### 6.1 每日投研工作流

```text
交易日触发 / 手动触发
  -> 更新市场和自选股数据
  -> 生成市场复盘
  -> 批量分析自选股/持仓
  -> 生成 daily decision dashboard
  -> 归档 Markdown/JSON 报告
  -> 推送摘要
  -> 首页展示任务状态、报告、告警和下一步操作
```

验收标准：

- 用户无需进入多个页面即可知道今日分析是否完成。
- 失败任务显示失败原因、失败阶段和重试入口。
- 报告必须能从首页、报告中心、symbol 页面三处进入。

### 6.2 盯盘和告警工作流

```text
自选股 / 持仓 / 策略候选池
  -> 实时行情和板块资金刷新
  -> 条件规则或策略信号触发
  -> 生成告警
  -> 可选生成 AI 异动摘要
  -> 写入告警历史和审计
  -> 首页和盯盘中心展示
```

验收标准：

- 告警不直接下单。
- 告警必须包含触发条件、数据来源、触发时间和处理状态。
- AI 异动摘要必须标注 `research_only`。

### 6.3 AI 研究到策略验证工作流

```text
AI 研究结论
  -> 提取观察点和风险点
  -> 选择策略或生成候选策略参数
  -> 运行回测/优化/walk-forward
  -> 输出风险和反偏差检查
  -> 进入报告归档
  -> 可选加入模拟盘观察
```

验收标准：

- AI 结论不能直接进入真实下单。
- 回测结果必须展示数据区间、成本模型、滑点、T+1、停牌/涨跌停假设。
- 策略结果可以引用到报告，但必须保留数据快照。

### 6.4 模拟盘到受控执行工作流

```text
研究或策略信号
  -> 风控预检查
  -> 模拟盘下单或 managed 执行申请
  -> 人工确认
  -> QMT/miniQMT 适配层
  -> 订单/成交/撤单/拒单状态
  -> 审计记录
  -> 组合风险更新
```

验收标准：

- 默认只进入 paper。
- managed 执行必须展示确认人、确认时间、风控结果和审计 ID。
- 自动实盘必须默认关闭，并在文档和 UI 中标注风险。

## 7. Phase 拆解

### Web-P0 首页重构：今日 A 股投研工作台

目标：

- 重做 `/dashboard`，让它成为每日工作台。
- 第一屏聚合市场、自选股、持仓、AI 任务、报告、告警和数据健康。
- 把交易入口后置为二级动作。

范围：

- `tradingagents/astock/web/templates/dashboard.html`
- `tradingagents/astock/web/templates/base.html`
- `tradingagents/astock/web/__init__.py`
- 可能新增 dashboard API adapter，但不大规模改后端。

必须包含：

- 今日市场摘要。
- 自选股/持仓摘要。
- 今日 AI 分析任务状态。
- 最新报告列表。
- 告警事件列表。
- 龙头/板块/资金线索摘要。
- 数据源健康摘要。
- 下一步操作区：开始分析、批量分析、查看报告、进入盯盘、运行回测、配置推送。

不做：

- 不做真实自动交易。
- 不做多市场全量扩展。
- 不重写所有页面。

验收：

- `/dashboard` 在无真实数据时有可用 empty state。
- API 失败时显示 degraded/error state，不白屏。
- 首页不使用 iframe。
- 桌面 1366px、1440px、1920px 下无明显遮挡或横向溢出。
- 移动窄屏可纵向阅读核心卡片。

### Web-P1 竞品能力对齐矩阵落地

目标：

- 把本文矩阵转换为 repo 内可追踪 backlog。
- 每个 DSA/AIS/TA 编号明确当前实现状态、目标 phase、测试入口。

范围：

- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
- `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`
- `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`

验收：

- 每个 P0/P1 能力均有归属模块。
- 每个能力都有验收标准。
- 不把未完成能力写成已完成。

### Web-P2 每日分析、报告归档和推送闭环

目标：

- 对齐 `daily_stock_analysis` 的核心用户入口。
- 让用户每天可以自动或手动生成分析，并看到任务和报告。

范围：

- Daily analysis task model。
- Watchlist batch analysis。
- Report archive。
- Notification settings。
- Scheduler or local task runner。

必须包含：

- watchlist 管理或读取入口。
- 批量分析任务。
- 市场复盘任务。
- 报告归档列表。
- 至少一种推送通道的端到端验证，其他通道可先作为配置占位。

验收：

- 手动触发一次每日分析可以完成任务记录、报告记录和首页展示。
- 推送失败不影响报告归档。
- 报告中包含模型、数据来源、生成时间和 advisory 标记。

### Web-P3 盯盘中心、持仓监控和告警

目标：

- 对齐 `aiagents-stock` 的高频实用工作流。
- 把实时盯盘、板块、资金、龙虎榜、北向、持仓和告警收敛到一个模块。

范围：

- 新建或重构 `/watchlist` / `/monitor` / `/market_leaders`。
- 移除 iframe 聚合方式。
- 整合旧页面：`dragon_tiger`、`northbound`、`sectors`、`momentum_dashboard`、`momentum_rotation`。

必须包含：

- 自选股实时行情表。
- 持仓摘要。
- 板块强弱。
- 龙头候选。
- 龙虎榜和北向资金 tab。
- 告警规则列表。
- 告警历史。

验收：

- 旧入口有兼容跳转或明确 deprecation。
- 告警具备触发条件、数据来源、状态和处理动作。
- 页面显示数据更新时间和缓存/降级状态。

### Web-P4 AI Research Center 整合

目标：

- 把单股、多股、主题、行业、持仓研究统一到 AI 研究中心。
- 接入 TradingAgents 多智能体结构化结果。

范围：

- `research.html`
- `ai_agent.html`
- `reports.html`
- AI research API / task store

必须包含：

- 单股研究。
- 批量研究。
- 主题研究。
- 报告对比。
- advisory chain 展示。
- 模型、prompt、输入数据快照和引用来源。

验收：

- 输出默认 `research_only` 和 `actionable=false`。
- 可从报告跳回原始输入和数据快照。
- 模型失败、provider 降级、无新闻/公告时都有状态展示。

### Web-P5 Strategy Lab 与回测验证整合

目标：

- 把策略选股、回测、优化、对比、walk-forward、反偏差检查统一成 Strategy Lab。

范围：

- `strategy_hub.html`
- `strategies.html`
- `backtest.html`
- 相关 API 和测试

必须包含：

- 策略 registry。
- 参数 schema。
- 一键回测。
- 优化和对比。
- walk-forward。
- 反偏差检查。
- 策略监控入口。

验收：

- 每个策略显示适用场景、参数、数据假设、风险。
- 回测结果显示成本、滑点、T+1、停牌/涨跌停假设。
- 策略信号可加入监控，但不能直接实盘下单。

### Web-P6 组合、风控、模拟盘和受控执行整合

目标：

- 把组合风险、模拟盘、QMT/miniQMT、风控和审计连成闭环。

范围：

- `portfolio.html`
- `risk.html`
- `paper.html`
- `qmt.html`
- `trading.html`
- `ops_audit.html`

必须包含：

- 组合净值。
- 持仓风险。
- VaR、集中度、归因、压力测试。
- 模拟盘订单。
- managed 执行确认。
- QMT/miniQMT 状态。
- 审计记录。

验收：

- paper、managed、live-ready 标签清晰区分。
- QMT/miniQMT 不可用时不允许伪装成功。
- managed 执行必须人工确认。
- 订单、风控和审计 ID 可以互相追溯。

### Web-P7 视觉系统和页面验收收口

目标：

- 统一 Web 工作台视觉和交互规范。
- 补齐页面验收清单和截图证据。

范围：

- `base.html`
- 全局 CSS tokens。
- 核心页面模板。
- `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`

必须包含：

- 统一颜色、字号、间距、按钮、表格、状态标签。
- 统一 loading / empty / degraded / error / stale 状态组件。
- 统一能力标签：research / paper / managed / live-ready / mock / degraded。
- 页面级截图或说明证据。

验收：

- 核心页面在桌面和窄屏无明显重叠。
- 不再新增 iframe 聚合页作为主实现。
- 不再新增大量局部 inline style，除非是一次性数据宽度或动态状态。

## 8. P0 最小可交付版本

如果需要先快速验证方向，P0 最小版本只做以下内容：

1. `/dashboard` 重做为今日工作台。
2. 首页显示：
   - 市场摘要。
   - 自选股/持仓摘要。
   - AI 任务状态。
   - 最新报告。
   - 告警摘要。
   - 龙头/板块摘要。
   - 数据健康。
3. 首页所有卡片都有 loading、empty、error/degraded 状态。
4. 顶层导航改为：
   - 今日
   - 盯盘
   - AI 研究
   - 策略
   - 组合风控
   - 交易执行
   - 系统
5. `/` 默认进入 `/dashboard`。
6. 交易执行入口后置，但不删除现有交易页面。
7. 更新文档和页面验收清单。

P0 不要求：

- 推送全通道完成。
- 自动任务调度完成。
- 旧页面全部重写。
- 多市场完成。
- miniQMT/QMT 实盘闭环完成。

## 9. 数据和 API 需求

### 9.1 Dashboard 聚合 API

建议新增或增强：

`GET /api/v1/dashboard/today`

返回建议结构：

```json
{
  "trade_date": "2026-06-27",
  "market": {
    "status": "closed",
    "indices": [],
    "breadth": {},
    "sectors": [],
    "updated_at": "..."
  },
  "watchlist": {
    "count": 0,
    "movers": [],
    "alerts": []
  },
  "portfolio": {
    "mode": "paper",
    "total_value": null,
    "pnl": null,
    "risk_flags": []
  },
  "ai_tasks": {
    "summary": {},
    "items": []
  },
  "reports": {
    "latest": []
  },
  "alerts": {
    "open": [],
    "recent": []
  },
  "data_health": {
    "providers": [],
    "degraded": false,
    "stale": false
  }
}
```

要求：

- 字段缺失时前端必须有空态。
- 外部数据源不可用时不能导致首页 500。
- `source`、`updated_at`、`stale`、`degraded` 必须尽量可见。

### 9.2 Task API

建议新增：

- `GET /api/v1/tasks`
- `POST /api/v1/tasks/daily-analysis`
- `POST /api/v1/tasks/watchlist-analysis`
- `GET /api/v1/tasks/<task_id>`
- `POST /api/v1/tasks/<task_id>/cancel`

任务状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `partial`

### 9.3 Report API

建议统一：

- `GET /api/v1/reports`
- `GET /api/v1/reports/<report_id>`
- `GET /api/v1/reports/<report_id>/markdown`
- `GET /api/v1/reports/<report_id>/json`

报告必备字段：

- `report_id`
- `symbol` 或 `scope`
- `trade_date`
- `report_type`
- `model`
- `prompt_version`
- `data_snapshot_id`
- `advisory_scope`
- `actionable`
- `created_at`
- `status`

### 9.4 Alert API

建议新增：

- `GET /api/v1/alerts`
- `POST /api/v1/alerts/rules`
- `PATCH /api/v1/alerts/<alert_id>`
- `POST /api/v1/alerts/<alert_id>/ack`

告警必备字段：

- `alert_id`
- `rule_id`
- `symbol`
- `trigger_type`
- `trigger_value`
- `source`
- `severity`
- `status`
- `created_at`
- `acknowledged_at`

## 10. UI 验收标准

### 10.1 每页通用验收

每个核心页面必须覆盖：

- loading 状态。
- empty 状态。
- error 状态。
- degraded 状态。
- stale/cache 状态。
- 权限或能力禁用状态。
- `research` / `paper` / `managed` / `live-ready` 标签。

### 10.2 首页验收

首页验收必须满足：

- 3 秒内出现页面骨架。
- 任意一个数据块失败，不影响其他数据块显示。
- 用户可以在第一屏看到今日任务、报告、告警和下一步入口。
- 没有 iframe。
- 没有无意义的大面积空白。
- 没有把 paper/mock 数据误标为真实实盘。

### 10.3 设计约束

- 不做营销落地页。
- 不新增大面积装饰性渐变背景。
- 不把卡片套卡片。
- 工具型页面保持高信息密度，但必须有清晰分组。
- 按钮文本不能溢出。
- 表格窄屏必须横向滚动或转摘要卡片。
- 顶层导航不超过 7 个主入口。
- 旧入口不能继续作为主导航。

## 11. 测试要求

### 11.1 自动化测试

每个 phase 至少包含：

- Flask route smoke test。
- API fallback test。
- 模板渲染 test。
- 关键 JSON schema test。
- 不可用 provider 的 degraded path test。

建议命令：

```bash
python3 -m pytest tests/test_astock_web.py -q
python3 -m pytest tests/test_astock_blueprint.py -q
python3 -m pytest tests/test_astock_webui_page_acceptance.py -q
```

如果新增 API：

```bash
python3 -m pytest tests/test_astock_api_contracts.py -q
```

实际测试文件名以实现时仓库状态为准。

### 11.2 浏览器验收

Web-P0 起必须做浏览器验收：

- `/dashboard`
- `/monitor` 或 `/market_leaders`
- `/research`
- `/strategy_hub`
- `/portfolio`
- `/trading`

视口：

- 1366 x 768
- 1440 x 900
- 1920 x 1080
- 390 x 844

检查：

- 首屏是否可读。
- 文字是否溢出。
- 卡片是否重叠。
- 图表是否空白。
- 错误态是否可见。
- 导航是否能回到今日工作台。

## 12. 文档同步要求

每个 phase 完成时必须同步：

- `docs/ASTOCK_CURRENT_STATUS.md`
- `docs/ASTOCK_BACKLOG.md`
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
- `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`
- `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`
- `docs/ASTOCK_BACKEND_API_REFERENCE.md`（如新增或修改 API）
- `docs/ASTOCK_API_CONTRACTS.md`（如新增或修改 contract）
- `docs/phases/phase-XX-*.md`

如果新增推送、任务调度、模型配置或执行能力，还必须同步：

- `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`
- `docs/ASTOCK_MODEL_GOVERNANCE.md`
- `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`
- `docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`

## 13. 风险和禁止项

### 13.1 风险

- 竞品能力太多，容易再次变成功能堆叠。
- 每日分析、盯盘、回测、执行若不分层，会造成用户误以为 AI 可以直接交易。
- 外部数据源不稳定会拖垮首页体验。
- QMT/miniQMT 能力容易被误标为 live-ready。
- Streamlit、Flask Jinja2、React 三套入口并行会继续拉低产品一致性。

### 13.2 禁止项

- 禁止把 AI 研究结论直接标成实盘买卖指令。
- 禁止默认开启自动实盘交易。
- 禁止把 paper/mock 数据伪装成真实账户或真实成交。
- 禁止继续用 iframe 拼装核心主页面。
- 禁止新增未归属到顶层信息架构的平级入口。
- 禁止只改颜色和样式后宣布 Web 工作台重构完成。
- 禁止在没有 empty/error/degraded 状态时交付页面。

## 14. 审核清单

执行前需要确认：

- [ ] 是否同意 `/dashboard` 成为默认首页。
- [ ] 是否同意 `/` 从交易页改为跳转或弱化入口。
- [ ] 是否同意 P0 只做 A 股，不做全市场同等能力。
- [ ] 是否同意推送通道 P1 先做至少一种端到端验证。
- [ ] 是否同意 QMT/miniQMT 默认只作为 managed/paper 能力，不默认自动实盘。
- [ ] 是否同意旧页面逐步迁移，不能长期作为主入口。
- [ ] 是否同意每个 phase 必须补文档、测试和页面验收证据。

## 15. 建议执行顺序

推荐严格按以下顺序执行：

1. Web-P0：今日工作台首页重构。
2. Web-P1：竞品能力矩阵进入 backlog/traceability。
3. Web-P2：每日分析、报告归档、推送闭环。
4. Web-P3：盯盘中心、持仓监控、告警。
5. Web-P4：AI Research Center 整合。
6. Web-P5：Strategy Lab 和回测验证整合。
7. Web-P6：组合、风控、模拟盘、受控执行整合。
8. Web-P7：视觉系统和页面验收收口。

任何阶段如果测试、页面验收或文档同步未完成，不进入下一阶段。

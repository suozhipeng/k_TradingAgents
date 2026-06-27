# A 股定制模块术语表

本文档统一定义 TradingAgents-Astock 中使用的专业术语，供产品、开发和用户参考。

## 1. 核心概念

| 术语 | 英文 | 定义 |
|---|---|---|
| 研究模式 | research | 系统处于只读分析状态，不执行任何交易动作 |
| 模拟盘 | paper | 虚拟资金、虚拟成交的试跑模式，不涉及真实账户 |
| 受控执行 | managed | 需要风控门和人工确认后方可执行的交易模式 |
| 实盘就绪 | live-ready | 已通过实盘准入 checklist 的真实执行能力 |
| 占位数据 | mock | 演示或测试用的模拟数据，不得用于实盘 |
| 降级 | degraded | 部分数据源或功能不可用时的降级运行状态 |

## 2. 数据相关

| 术语 | 英文 | 定义 |
|---|---|---|
| 数据源 | data source | 提供行情、财务、新闻等数据的第三方服务 |
| Provider | provider | 具体数据源实现（如 mootdx、akshare、Tencent） |
| 主源 | primary | 首选数据源，优先使用 |
| 备源 | fallback | 主源失败时自动切换的备用数据源 |
| 数据新鲜度 | freshness | 数据从生成到当前的时间差 |
| 数据质量 | data quality | 数据的完整性、准确性和时效性综合评估 |
| 数据快照 | data snapshot | 某一时刻的数据状态副本，用于可复现分析 |
| 血缘 | lineage | 数据来源、转换和使用的完整追溯链 |
| 复权 | adjustment | 股票除权除息后的价格调整（前复权/后复权/不复权） |
| 停复牌 | suspension/resumption | 股票暂停或恢复交易的状态 |
| 涨跌停 | limit_up/down | A 股单日价格波动上限（±10% 或 ±20%） |
| ST/退市 | ST/delisting | 特别处理和退出市场的证券状态 |

## 3. 研究与分析

| 术语 | 英文 | 定义 |
|---|---|---|
| 五层数据 | five-layer data | 行情层、研报层、新闻层、基础数据层、公告层 |
| 研究链 | research chain | AStockAnalyst → Bull/Bear Researcher → Research Manager 的分析流程 |
| advisory 链 | advisory chain | ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision 的结构化决策链 |
| advisory-only | advisory-only | AI 输出仅为研究参考，不直接触发真实交易 |
| 多空辩论 | bull/bear debate | Bull Researcher 和 Bear Researcher 的对抗式分析 |
| 研究结论 | ResearchConclusion | 研究链输出的结构化结论 |
| 交易提案 | TraderProposal | 基于研究结论的交易建议 |
| 风控决策 | RiskDecision | 风险评估和风控建议 |
| 组合决策 | PortfolioDecision | 最终的投资组合建议 |
| 幻觉 | hallucination | AI 生成不准确或虚构内容的现象 |
| Prompt | prompt | 发送给 LLM 的指令模板 |

## 4. 回测与策略

| 术语 | 英文 | 定义 |
|---|---|---|
| 回测 | backtest | 使用历史数据验证策略表现 |
| 策略注册表 | strategy registry | 统一管理所有策略元数据的注册中心 |
| 参数优化 | parameter optimization | 通过 grid search 等方法寻找最优策略参数 |
| 复合评分 | composite score | `0.35*Sharpe + 0.30*Return - 0.25*Drawdown + 0.10*TradeFrequency` |
| Survivorship bias | 幸存者偏差 | 只使用当前存在的股票数据进行回测导致的偏差 |
| Look-ahead bias | 前瞻偏差 | 回测中使用了当时不可知的未来信息 |
| 未来函数 | look-ahead function | 在回测中引用了未来数据的代码逻辑 |
| 样本外 | out-of-sample | 未用于参数优化的测试数据区间 |
| Walk-forward | walk-forward | 滚动窗口式的回测验证方法 |
| 成本模型 | cost model | 佣金、印花税、滑点等交易成本的模拟 |
| Benchmark | benchmark | 回测对比的基准（如沪深300） |

## 5. 交易与执行

| 术语 | 英文 | 定义 |
|---|---|---|
| 订单生命周期 | order lifecycle | 订单从创建到最终状态的全过程 |
| 部分成交 | partial fill | 订单只成交了部分数量的情况 |
| 拒单 | rejected | 订单被券商或风控系统拒绝 |
| 撤单 | cancellation | 用户主动撤销未成交订单 |
| Reconciliation | 对账 | 本地订单状态与券商回报的比对 |
| Kill switch | 紧急停机 | 一键阻断所有后续交易的安全机制 |
| 风控门 | risk gate | 下单前执行的风险检查关卡 |
| ATR 止损 | ATR stop-loss | 基于平均真实波幅的动态止损 |
| 人工确认 | manual confirmation | 交易执行前需要用户显式确认的步骤 |
| QMT | QMT | 迅投量化交易平台，用于 A 股券商接口桥接 |

## 6. 系统与运维

| 术语 | 英文 | 定义 |
|---|---|---|
| DuckDB | DuckDB | 本地嵌入式列式数据库，用于数据存储 |
| Cache | 缓存 | 内存或磁盘缓存，加速数据访问 |
| SSE | SSE | Server-Sent Events，服务端推送实时事件 |
| TaskRun | 任务运行 | 数据刷新、回测、AI 研究等任务的执行记录 |
| AuditEvent | 审计事件 | 关键操作的审计追踪记录 |
| Runtime Profile | 运行时配置 | 控制系统运行模式的配置集 |
| Deterministic Verification | 确定性验证 | 使用 BridgeLLM 的离线验证模式 |
| Live Research | 实时研究 | 使用真实 LLM 的研究模式 |
| Capability | 能力等级 | 标注 API/页面能力的标签（research/paper/managed/live-ready） |
| Envelope | 响应信封 | API 响应的标准包装结构（success/data/error/meta） |

## 7. 文档与治理

| 术语 | 英文 | 定义 |
|---|---|---|
| Phase | 阶段 | 一次迭代的交付单元，有明确的 scope 和验收标准 |
| ADR | Architecture Decision Record | 架构决策记录 |
| Traceability Matrix | 需求追踪矩阵 | 需求 ID 到模块/API/测试/Phase 的映射表 |
| Risk Register | 风险登记表 | 项目风险的登记和跟踪表 |
| Scope Register | 范围登记表 | 纳入/暂不纳入范围的登记 |
| ECC | Embedded Continuous Checking | 嵌入式持续检查机制 |
| Hermes | Hermes | 任务调度器和 phase owner |
| DeepSeek | DeepSeek | 代码实现引擎 |
| Codex | Codex | 独立 review gate |

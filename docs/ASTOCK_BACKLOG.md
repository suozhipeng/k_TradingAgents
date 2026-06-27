# TradingAgents-Astock 待开发 Backlog

## 1. 文档目标

本文档整理当前仓库后续最值得推进的需求项，按优先级划分为：

- P0：必须尽快收口
- P1：高价值增强
- P2：后续优化

更完整的金融产品优化路线图见 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`。Backlog 负责记录执行队列，路线图负责说明为什么做、先做什么、每个模块如何达到金融产品可用口径。

需求到模块、测试和 phase 的映射见 `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`。产品指标、运行指标、告警和 Ops 要求见 `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`。

生产级交付还必须同步以下文档：

- API 契约：`docs/ASTOCK_API_CONTRACTS.md`
- 项目风险登记表：`docs/ASTOCK_PROJECT_RISK_REGISTER.md`
- 架构决策记录 ADR：`docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`
- 数据字典与血缘：`docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`
- 数据迁移与升级手册：`docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`
- 数据源授权与使用边界：`docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md`
- AI 模型治理：`docs/ASTOCK_MODEL_GOVERNANCE.md`
- 实盘运行手册：`docs/ASTOCK_LIVE_TRADING_RUNBOOK.md`
- 核心功能部署与环境：`docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`
- 测试与验收计划：`docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`
- 发布与变更管理：`docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`
- 风险披露与合规边界：`docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`
- WebUI 产品规范：`docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`
- WebUI 页面级验收清单：`docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`
- 文档范围登记：`docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`

## 2. P0

### BL-000 建立实盘准入清单

现状：

- 当前系统已经能支撑投研分析、回测、模拟盘和 QMT 受控执行
- 但专业金融系统的实盘生产闭环仍缺账户/订单/成交 reconciliation、审计、kill switch、数据质量和组合级风控门槛

目标：

- 建立 `Live Trading Readiness` checklist
- 明确哪些能力属于 `research`、`paper`、`managed`、`live-ready`
- 把实盘准入条件写入状态文档、技术文档和 phase 归档

完成标准：

- 有账户资产、持仓、委托、成交、撤单、拒单、部分成交、券商回报的状态模型要求
- 有 kill switch、最大亏损、最大仓位、最大单笔金额、交易时段、手工确认的硬约束
- 有审计要求：数据快照、AI prompt、模型版本、人工确认、订单回报全链路可追溯
- 文档明确当前系统“可实盘辅助分析”，但“不等于完整自动实盘生产系统”

### BL-001 统一 QMT 能力边界

现状：

- QMT 在执行层已存在
- QMT 在 blueprint/provider 口径里仍保留 placeholder 语义

目标：

- 统一 QMT 在 provider、execution、API、状态文档中的能力定义

完成标准：

- blueprint / status / phase / code 口径一致
- 不再同时出现“已完成执行”和“provider 仍占位”冲突

### BL-002 修正 `qmt/orders` 的 mock 语义

现状：

- `/api/v1/qmt/orders` 返回的是 mock/read-only 响应

目标：

- 接真实 QMT 订单/委托查询，或明确改名为 mock endpoint

完成标准：

- endpoint 语义与返回内容一致
- 文档不再误导为真实订单模块

### BL-003 修正 trade quote / trade state 的能力口径

现状：

- `trade/quote` 使用 EastMoney push2 实时报价 + Sina 降级 + 60s 缓存 — ✅ **已真实**
- `trade/state` 使用 PaperTrader 状态 + 实时报价估值 — ✅ **明确为 Paper Trading 路径**

目标：

- ✅ 已达成 — trade/quote 是实时数据（EastMoney → Sina → 缓存三级降级）
- trade/state 属于 Paper Trading，非实盘，文档已写明

完成标准：

- endpoint 语义与返回内容一致 — ✅ trade/quote 返回实时数据
- 用户不会把 mock 报价误认为真实交易报价 — ✅ trade/quote 已标注 source: "live"|"cache"；trade/state 通过 PaperTrader 路径

### BL-004 为专业交易页建立正式归档

现状：

- `trading.html`、`routes_trade.py`、相关测试已进入代码
- 已建立独立 phase 归档 `docs/phases/phase-29-trading-page.md`

目标：

- ✅ 已达成 — 有 scope、测试、风险说明、commit SHA

完成标准：

- 有 scope — ✅ `phase-29-trading-page.md`
- 有测试 — ✅ WebUI + API 切片 150 passed
- 有风险说明 — ✅ 实时报价依赖/缓存/持久化
- 有 commit SHA — ✅ `268d326`, `87e5b73`, `1960c65` 等

### BL-200 Web-G0 需求冻结 — 更新 backlog / traceability / product-spec / checklist 文档

| 状态 | 备注 |
|------|------|
| ✅ done | Web-G0 phase 文档已创建，backlog/traceability/spec/checklist 均已更新 |

现状：
- Web 工作台竞品对齐矩阵已确定 P0/P1/P2 分组，但尚未写入 backlog 和 traceability
- 默认入口、能力标签和安全边界需要正式冻结，避免开发中反复改方向

目标：
- 将 DSA / AIS / TA / REF / TDX 矩阵映射到需求 ID，写入 backlog 和 traceability
- 固定 `/dashboard` 为默认首页
- 明确 QMT/miniQMT 默认不是自动实盘
- 明确 TDX 行情链路归属 Data & Ops，不归属 Trading & Execution

完成标准：
- 每个 P0/P1 能力都有需求 ID、模块、phase、验收证据位置
- 文档状态不把 planned 写成 done

### BL-201 Web-P0 首页重构 — dashboard 作为每日工作台

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard.html 已有 7 个区域骨架，但非所有卡片实现五态；Web-P0 需深化完成 |

现状：
- `/dashboard` 更像系统指标页，不像用户每日打开的工作台
- 当前首页缺少市场摘要、自选股/持仓、任务、报告、告警和数据健康聚合

目标：
- 重做 `/dashboard`，第一屏聚合市场、自选股、持仓、AI 任务、报告、告警和数据健康
- 交易入口后置为二级动作

完成标准：
- 首页有市场、自选股/持仓、任务、报告、告警、龙头/板块摘要、数据健康七个区域
- 所有卡片支持 loading、empty、error/degraded 状态
- 首页不使用 iframe
- 桌面 1366px、1440px、1920px 下无遮挡或横向溢出

### BL-202 默认入口变更 — `/` 重定向到 `/dashboard`

| 状态 | 备注 |
|------|------|
| ✅ done | `/` 已 302 → `/dashboard`，在 `web/__init__.py:119` 实现 |

现状：
- `/` 默认进入交易页，用户还没完成分析、盯盘就被推到下单界面

目标：
- `/` 改为 302 到 `/dashboard`
- `trading.html` 不再作为新用户第一屏

完成标准：
- `/dashboard` 是产品默认入口
- 旧入口保留兼容，但显示迁移提示

### BL-203 DSA-01 每日市场复盘 — 按交易日生成市场回顾

| 状态 | 备注 |
|------|------|
| 🔶 partial | 市场摘要 API (market/summary) + dashboard 指数卡片已存在，但缺少结构化交易日回顾报告 |

现状：
- 无每日市场复盘能力
- 用户需要手动查看指数、涨跌家数和板块

目标：
- 可按交易日生成市场复盘，含指数、涨跌家数、板块强弱和风险摘要

完成标准：
- 复盘包含主要指数涨跌幅、涨跌家数比、板块强弱排序和风险标注
- 复盘结果可归档为报告

### BL-204 DSA-02 自选股批量分析 — 维护 watchlist 并批量生成 AI 摘要

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 有自选股异动卡片，PaperTrader 维护 watchlist，但缺少批量 AI 分析入口 |

现状：
- 自选股管理不完整，缺少批量 AI 分析入口

目标：
- 用户可维护 watchlist，并批量生成 AI 摘要和评分

完成标准：
- 有 watchlist 管理或读取入口
- 批量分析任务可触发、查看进度和结果

### BL-205 DSA-03 决策仪表盘摘要 — 首页展示 buy/hold/sell/research-only 摘要

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 展示汇总数据卡片（跟踪股票数/回测数/模拟盘净值/持仓数），但缺少 buy/hold/sell/research-only 决策摘要 |

现状：
- 首页缺少决策摘要，用户不知道 AI 对自选股/持仓的整体判断

目标：
- 首页展示买入/观望/卖出或 research-only 等级摘要
- 不得直接标成可执行指令

完成标准：
- 摘要明确标注 `research_only` / `actionable=false`
- 不把 AI 摘要伪装为买卖建议

### BL-206 DSA-04 历史报告归档 — 按 symbol、日期、模型、数据快照归档

| 状态 | 备注 |
|------|------|
| 🔶 partial | `/reports` 页面 + `/api/v1/reports/pptx` 端点存在，但报告缺少 symbol/模型/数据快照等结构化字段 |

现状：
- 报告保存不完整，缺少 symbol、模型、数据快照等结构化字段

目标：
- 报告有 symbol、日期、模型、数据快照、状态和查看入口

完成标准：
- 报告可从首页、报告中心、symbol 页面三处访问
- 报告包含 model、prompt_version、data_snapshot_id、advisory_scope、actionable、status 字段

### BL-207 DSA-05 任务进度 — queued/running/succeeded/failed/cancelled

| 状态 | 备注 |
|------|------|
| 🔶 partial | `/api/v1/ops/tasks` 端点 + ops_audit.html 任务中心存在，但 dashboard 任务卡片缺少完整状态机展示 |

现状：
- 分析任务缺少状态展示，用户不知道任务是否完成

目标：
- 分析任务有 queued/running/succeeded/failed/cancelled 状态

完成标准：
- 首页展示任务状态、进度和最近完成报告
- 失败任务显示失败原因和重试入口

### BL-208 AIS-01 实时盯盘 — 自选股实时/缓存状态、涨跌幅、成交额、更新时间

| 状态 | 备注 |
|------|------|
| 🔶 partial | `/market_leaders` 页面整合了龙头/龙虎榜/北向/板块 iframe tab，但缺少统一自选股实时状态表 |

现状：
- 自选股实时行情分散，缺少统一盯盘入口

目标：
- 自选股列表展示实时/缓存状态、涨跌幅、成交额、更新时间

完成标准：
- 页面显示数据更新时间和缓存/降级状态
- 数据源不可用时显示 degraded 状态，不白屏

### BL-209 AIS-06 板块轮动 — 首页板块强弱摘要，轮动/回测入口

| 状态 | 备注 |
|------|------|
| 🔶 partial | market/sectors API + dashboard 热门板块 TOP3 卡片存在，但缺少板块轮动详细视图 |

现状：
- 板块强弱分析分散在旧页面，首页缺少入口

目标：
- 首页展示板块强弱摘要，有详细轮动/回测入口

完成标准：
- 首页板块摘要包含板块名称、涨跌幅和强弱标识
- 可跳转到详细板块轮动和回测页面

### BL-210 AIS-09 持仓监控 — 首页持仓风险、盈亏、集中度、告警

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 显示持仓数量 + 模拟盘净值，portfolio 页面显示完整组合数据，但缺少告警集成 |

现状：
- 持仓风险信息分散，首页缺少摘要

目标：
- 首页展示持仓风险、P&L、集中度和告警

完成标准：
- 摘要包含总市值、盈亏、集中度指标和风险标识
- 明确标注 paper/managed 能力等级

### BL-211 TA-01 AI 研究链展示 — researcher/trader/risk/portfolio 分层结果

| 状态 | 备注 |
|------|------|
| 🔶 partial | research.html + ai_agent.html 存在，但缺少 researcher/trader/risk/portfolio 分层链路展示 |

现状：
- TradingAgents 多智能体研究链结果分散，缺少统一展示

目标：
- 页面显示 researcher/trader/risk/portfolio 分层结果

完成标准：
- 研究链各层结果可追溯
- ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision 路径可见

### BL-212 TA-03 research_only 安全边界 — 所有 AI 输出默认 actionable=false

| 状态 | 备注 |
|------|------|
| 📋 planned | 所有 AI 输出默认 actionable=false 未全局实现，需 Web-P0 阶段落地 |

现状：
- AI 输出缺少统一的安全边界标记

目标：
- 所有 AI 输出默认 `actionable=false`，不直接触发交易

完成标准：
- 每个 AI 输出页面或报告标注 `research_only` 和 `actionable=false`
- 用户不会误以为 AI 可直接实盘交易

### BL-213 TA-04 回测引擎入口 — 首页显示最近回测和一键回测

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 有回测快捷入口 + 最近回测列表，backtest/run + backtest/optimize API 均已存在 |

现状：
- 回测能力已存在但首页缺少快捷入口

目标：
- 今日工作台可进入最近回测和一键回测

完成标准：
- 首页有最近回测列表和运行新回测按钮
- 回测结果显示成本、滑点、T+1、停牌/涨跌停假设

### BL-214 TA-07 模拟盘状态 — 首页显示 paper status，不伪装为真实账户

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 展示 paper_total_value + paper_positions，paper.html 页面存在，但能力等级标注需加强 |

现状：
- 首页可能把 paper/mock 数据误标为真实实盘

目标：
- 首页显示 paper 状态，不伪装为真实账户

完成标准：
- 模拟盘页面和入口统一标注 paper/managed
- 不把 paper 数据标为 live-ready

### BL-215 TA-09 组合 VaR/集中度/归因 — 首页风险摘要

| 状态 | 备注 |
|------|------|
| 🔶 partial | portfolio.html + `/api/v1/portfolio/risk` + `/api/v1/portfolio/attribution` 已实现（Phase 36），但首页摘要需强化 |

现状：
- 组合级风险指标缺少首页入口

目标：
- 首页显示关键风险摘要（VaR、集中度、归因）

完成标准：
- 摘要包含 VaR、最大回撤、集中度等核心指标
- 详细页显示完整归因

### BL-216 TA-11 数据健康 — 首页 provider 健康、缓存、降级、stale 状态

| 状态 | 备注 |
|------|------|
| 🔶 partial | data_health.html + `/api/v1/data/health` API 已存在，dashboard 有数据健康摘要卡片 |

现状：
- 数据源健康信息分散，用户不知道哪些 provider 正常

目标：
- 首页显示 provider 健康、缓存、降级和 stale 状态

完成标准：
- 数据健康摘要包含各 provider 状态、缓存 age、degraded 标识
- 外部数据源不可用时首页不 500

## 3. P1

### BL-100 Strategy Lab 模块整合

现状：

- 策略、回测、批量回测、优化、绩效、策略对比、动量轮动均已有实现
- 当前能力分散在 execution、API、WebUI 和独立动量入口中
- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` 已固化策略生命周期、注册点、复合评分和常见陷阱

目标：

- 将策略模块和回测能力统一到一个 Strategy Lab 产品/工程边界
- 统一策略注册、参数 schema、结果 schema、成本模型、风控约束和绩效归因

完成标准：

- 有 `phase-32-strategy-lab-consolidation.md` 归档
- 所有策略均可通过统一 registry 描述参数和适用场景
- 单标的策略符合 `StrategyBase -> generate_signals` 规范
- 动量轮动等组合策略明确使用 Standalone 模式或 StrategyBase 兼容模式
- `_STRATEGY_REGISTRY`、`AVAILABLE_STRATEGIES` 和包级导出不再各自漂移
- Backtest / Optimize / Compare / Performance / Momentum Rotation 在产品侧属于同一模块
- 旧入口有明确兼容策略或迁移计划

### BL-100A AI Research Center 模块整合

现状：

- AI Agent 页面、A 股 research runtime、报告中心、研究页面均已存在
- AI 分析的上下文、prompt、模型、引用、报告归档和人工确认状态尚未统一

目标：

- 将 AI Agent、A 股研究报告、新闻/公告/研报解读、策略解释整合为 AI Research Center
- 保持所有 AI 输出默认 advisory，不直接触发真实交易

完成标准：

- 有 `phase-33-ai-research-center.md` 归档
- AI 任务记录模型、prompt、输入数据快照、引用来源、生成时间和人工确认状态
- AI Research Center 可以调用行情、财务、公告、新闻、研报、策略结果和持仓风险作为上下文
- 报告中心统一管理 Markdown/JSON/PPT/Web report

### BL-100B 龙头相关单入口

现状：

- `/market_leaders` 单入口与顶层 sidebar 入口已经存在
- 龙头动量总览、动量轮动、龙虎榜、北向资金、板块页面仍保留独立兼容入口
- 产品入口已初步收敛，但页面内部 tab 收口与旧入口下线策略尚未完全闭环

目标：

- 顶层最多保留一个龙头相关入口
- 在该入口内部用顶部 tab 切换不同子板块

完成标准：

- 有 `phase-34-market-leaders-entry.md` 归档
- 顶层导航只出现一个 `Market Leaders` / `龙头决策` 入口
- 内部 tab 至少覆盖：动量总览、轮动回测、板块强弱、资金线索、候选池
- 旧的 `momentum_dashboard`、`momentum_rotation`、`dragon_tiger`、`northbound`、`sectors` 有兼容跳转或明确降级策略

### BL-101 明确专业交易页的产品定位

候选定位：

- paper trading 控制台
- 受控执行控制台
- 研究辅助交易页

目标：

- ✅ 已达成 — 三种模式共存（Paper / 实盘 / 研究），通过模式切换器统一入口
- phase-29-trading-page.md 已更新多模式定位描述
- trading.html 已添加模式切换器 UI

### BL-102 完善 QMT fundamentals 替代策略

现状：
- ✅ 已解决 — 基本面数据永远走非 QMT provider（akshare/Tencent/EastMoney/cninfo）
- router.py 中 fundamentals 路由已配置为 akshare/Tencent 优先
- QMT 仅提供交易执行接口，不处理基本面查询

目标：
- ✅ 已达成 — 基本面不走 QMT 的降级策略已在生产路径中生效

### BL-103 收敛 phase 归档一致性

现状：

- ✅ 已达成 — Phase 0-29 均已有 `docs/phases/phase-*.md` 归档文件
- ✅ Phase 13/15/16/17 已补最小归档
- ✅ Phase 18/19/20 已接入 `docs/phases/README.md` 链接
- ✅ Phase 20 提交 SHA 已从 `pending` 修正为 `d128dc9`

目标：

- phase 文档统一补齐 commit SHA、测试与风险 — ✅ 当前已闭环

### BL-104 收紧 mock 与 real 的状态标识

目标：

- 在 API、页面、状态文档里显式标注 mock / paper / real / managed

### BL-105 数据质量与回测反偏差

关联 Phase：Phase 31

目标：

- 建立交易日历、停复牌、涨跌停、复权、除权除息、ST、退市和 survivorship bias 的处理要求
- 明确回测禁止 look-ahead bias 和未来函数
- 为行情、财务、公告、新闻、研报建立数据质量分级和 provenance 记录

### BL-300 DSA-06 推送通知配置 — 至少一种通道端到端可验证

| 状态 | 备注 |
|------|------|
| 📋 planned | 无通知系统，settings.html 无推送配置入口，需新建 notification 模块 |

现状：
- 推送能力未实现，缺少配置入口

目标：
- 支持至少一种本地可验证通道（如邮件/Webhook）
- 其他通道可先配置占位但标注未验证

完成标准：
- 推送配置页面可见
- 至少一种通道端到端可触发、可验证
- 推送失败不影响报告归档

### BL-301 DSA-07 定时任务 — 本地 cron/APScheduler 每日分析

| 状态 | 备注 |
|------|------|
| 🔶 partial | PaperTradeScheduler (execution/scheduler.py) 已实现，但仅用于模拟盘交易周期，无通用分析任务调度 |

现状：
- 无定时触发能力，分析需手动启动

目标：
- 支持本地 cron/APScheduler 触发每日分析

完成标准：
- 定时任务可配置触发时间和分析范围
- GitHub Actions 作为后续部署方案

### BL-302 DSA-12 代码/名称/拼音补全 — 全局搜索

| 状态 | 备注 |
|------|------|
| 📋 planned | 搜索框无智能补全功能，需实现自动补全模块 |

现状：
- 搜索框缺少智能补全

目标：
- 全局搜索和输入框支持股票代码、名称、拼音统一补全

完成标准：
- 输入时展示匹配候选列表
- 选择后跳转到对应 symbol 页面

### BL-303 AIS-02 AI 盯盘摘要 — 对异动股票生成短摘要

| 状态 | 备注 |
|------|------|
| 📋 planned | 无异常股票 AI 摘要功能 |

现状：
- 异动股票无 AI 自动摘要

目标：
- 对异动股票生成短摘要，标注数据来源和模型

完成标准：
- 摘要标注 `research_only`
- 包含模型和数据来源信息

### BL-304 AIS-03 主力资金 — 显示资金流入/流出、来源、刷新时间

| 状态 | 备注 |
|------|------|
| 🔶 partial | northbound API (北向资金) 存在，但无统一的主力资金流入/流出组件 |

现状：
- 主力资金信息分散，缺少统一组件

目标：
- 显示资金流入/流出、来源、刷新时间和降级态

完成标准：
- 页面显示数据来源、更新时间和降级标识
- 数据源不可用时显示 degraded

### BL-305 AIS-04 龙虎榜 — 整合入盯盘中心

| 状态 | 备注 |
|------|------|
| 🔶 partial | dragon-tiger API + legacy dragon_tiger.html 存在，已集成到 market_leaders iframe tab |

现状：
- 龙虎榜作为孤立旧入口存在

目标：
- 不再作为孤立旧入口，进入盯盘中心 tab

完成标准：
- 旧入口有兼容跳转或 deprecation 提示
- 盯盘中心内部 tab 可查看龙虎榜

### BL-306 AIS-05 北向资金 — 整合入盯盘中心

| 状态 | 备注 |
|------|------|
| 🔶 partial | northbound API + legacy northbound.html 存在，已集成到 market_leaders iframe tab |

现状：
- 北向资金作为孤立旧入口存在

目标：
- 不再作为孤立旧入口，进入盯盘中心 tab

完成标准：
- 旧入口有兼容跳转或 deprecation 提示
- 盯盘中心内部 tab 可查看北向资金

### BL-307 AIS-07 主力选股批量分析 — 候选池批量 AI 分析

| 状态 | 备注 |
|------|------|
| 📋 planned | 无候选池批量分析入口 |

现状：
- 主力选股批量分析缺少入口和记录

目标：
- 可对候选池批量分析，保存历史记录

完成标准：
- 批量分析任务可触发和查看结果
- 历史记录可回溯

### BL-308 AIS-08 策略监控 — 策略信号生成告警，不直接下单

| 状态 | 备注 |
|------|------|
| 📋 planned | 策略信号与告警系统未连接 |

现状：
- 策略信号与告警系统未连接

目标：
- 策略信号可加入监控，生成告警，不直接下单

完成标准：
- 告警包含触发条件、数据来源、触发时间
- 不直接触发真实交易

### BL-309 AIS-10 条件告警 — 价格/涨跌幅/成交量/策略/风控告警

| 状态 | 备注 |
|------|------|
| 📋 planned | `/api/v1/alerts` endpoint 不存在，无任何告警系统 |

现状：
- 条件告警规则未实现

目标：
- 支持价格、涨跌幅、成交量、策略信号、风控告警规则

完成标准：
- 告警规则可创建、启用、禁用
- 告警事件有触发条件、数据来源、状态和处理动作

### BL-310 AIS-12 模型配置 — 模型可见，研究记录模型和 prompt 版本

| 状态 | 备注 |
|------|------|
| 🔶 partial | settings.html 有模型/数据源选择器，但研究记录缺少 model/prompt_version |

现状：
- 模型配置不透明，研究记录缺少模型和 prompt 版本

目标：
- 模型配置在系统页面可见
- 研究任务记录模型名称和 prompt 版本

完成标准：
- 系统设置页可查看和选择模型
- 报告和研究记录包含 model 和 prompt_version 字段

### BL-311 AIS-13 miniQMT/QMT 入口 — 默认 managed/paper，人工确认

| 状态 | 备注 |
|------|------|
| 🔶 partial | qmt.html + QMT routes 存在，但缺少 managed/paper 能力等级标注 |

现状：
- QMT/miniQMT 能力容易被误标为 live-ready

目标：
- 默认 managed/paper，必须人工确认
- 自动实盘为显式高级开关

完成标准：
- 入口标注 managed/paper 能力等级
- 自动实盘默认关闭
- managed 执行必须展示确认人、确认时间、风控结果

### BL-312 AIS-14 T+1 规则适配 — 回测/模拟盘/受控执行均标注 T+1

| 状态 | 备注 |
|------|------|
| 📋 planned | T+1 约束未在回测/模拟盘/受控执行路径中显式标注 |

现状：
- T+1 约束未在所有路径中显式标注

目标：
- 回测、模拟盘、受控执行路径均标注 T+1 约束

完成标准：
- 回测结果展示 T+1 假设
- 模拟盘和受控执行页面标注 T+1

### BL-313 TA-05 参数优化 — 结果关联报告和策略监控

| 状态 | 备注 |
|------|------|
| 🔶 partial | backtest/optimize API 已存在，但优化结果未与报告关联 |

现状：
- 参数优化结果孤立，未与报告和监控关联

目标：
- 参数优化结果可与报告和策略监控关联

完成标准：
- 优化结果可引用到报告
- 优化参数可进入策略监控

### BL-314 TA-06 Walk-forward/反偏差检查 — 数据显示数据质量、OOS、偏差

| 状态 | 备注 |
|------|------|
| 📋 planned | 回测结果缺少数据质量/OOS/偏差检查 |

现状：
- 回测结果缺少数据质量、样本外和偏差检查

目标：
- 回测结果显示数据质量、样本外（OOS）和偏差检查

完成标准：
- 回测报告包含数据区间、质量标签、样本外标识
- 有 survivorship bias / look-ahead bias 检查说明

### BL-315 TA-08 QMT 受控执行 — 不可用时 disabled 或降级 paper

| 状态 | 备注 |
|------|------|
| 🔶 partial | QMT routes + risk gate 已接线，但 QMT 不可用时 disabled/paper 降级未实现 |

现状：
- QMT 不可用时状态不清晰

目标：
- QMT 不可用时 disabled 或降级 paper；实盘必须确认

完成标准：
- QMT 不可用时不允许伪装成功
- 页面显示 QMT 状态和能力等级

### BL-316 TA-10 审计中心 — AI/报告/风控/交易确认/订单回报有审计记录

| 状态 | 备注 |
|------|------|
| 🔶 partial | AuditStore + ops/tasks + ops/audit + ops/stats API + ops_audit.html 已存在（Phase 37） |

现状：
- 审计记录分散，缺少统一查看入口

目标：
- AI 报告、风控、交易确认、订单回报有审计记录

完成标准：
- 审计记录包含 event_type、actor、payload_hash、created_at
- 订单、风控和审计 ID 可以互相追溯

## 4. P2

### BL-201 补更清晰的模块需求追踪矩阵

目标：

- ✅ 已达成 — 已建立 `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
- 后续 phase 需要持续维护该矩阵

### BL-202 继续清理文档漂移

现状：
- ✅ 已修复 — 统一口径已同步：CURRENT_STATUS.md 测试数（63→65）、通过数（1019→1017）、版本号（0.1.0→0.2.5）、.venv 状态
- ✅ USER_MANUAL.md 周期数（6→7）已修正
- ✅ phases/README.md Phase 14 策略数（6→10）、Phase 15 端点数（19→30+）、Phase 35-38 状态已同步

目标：
- ✅ 已达成 — 后续 phase 变更后需同步维护数字口径
### BL-203 细化多入口职责

目标：

- 继续明确 CLI、Streamlit、Flask WebUI 各自职责

### BL-204 为真实交易能力补更明确的验收门槛

目标：

- 已纳入 Phase 30 Live Trading Readiness
- 已建立实盘运行手册、测试验收计划、API 契约和风险披露文档作为前置门槛
- 需要在 `phase-30-live-trading-readiness.md` 中固化 checklist

### BL-206 API 契约治理

目标：

- ✅ 已建立 `docs/ASTOCK_API_CONTRACTS.md`
- 后续 API 变更必须维护 capability、envelope、错误码、schema 和审计引用

### BL-207 数据字典与血缘治理

目标：

- ✅ 已建立 `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`
- 后续数据字段、provider、质量标签、快照和 fallback 变化必须同步维护

### BL-208 测试验收与发布门槛治理

目标：

- ✅ 已建立 `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md`
- 后续 phase 必须按测试分层、阻断条件、回滚和证据要求归档

### BL-209 风险披露与合规边界治理

目标：

- ✅ 已建立 `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`
- 后续页面、报告、AI 输出、回测和交易入口必须保持风险披露一致

### BL-210 核心功能环境文档治理

目标：

- ✅ 已建立 `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`
- 后续核心功能启动、依赖、健康检查和 degraded 口径必须同步维护

### BL-211 AI 模型治理

目标：

- ✅ 已建立 `docs/ASTOCK_MODEL_GOVERNANCE.md`
- 后续 AI provider、prompt、模型输出 schema 和降级行为必须同步维护

### BL-212 WebUI 页面规范治理

目标：

- ✅ 已建立 `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`
- 后续 WebUI 顶层导航、页面状态、能力标签和旧入口迁移必须同步维护

### BL-213 变更兼容治理

目标：

- ✅ 已建立 `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`
- 后续 API/data/AI/trading/UI 兼容性变化必须同步维护

### BL-214 暂不纳入范围登记

目标：

- ✅ 已建立 `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md`
- 安全与隐私、SLA 与故障分级、用户角色/RBAC 当前只登记，不进入核心功能需求

### BL-215 数据迁移与升级治理

目标：

- ✅ 已建立 `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`
- 后续 DuckDB、cache、schema、报告归档和回测结果结构变化必须同步维护迁移、校验和回滚策略

### BL-216 WebUI 页面级验收治理

目标：

- ✅ 已建立 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`
- 后续 WebUI 页面开发或重构必须补齐输入、输出、状态、错误态和截图/替代证据

### BL-217 项目风险登记治理

目标：

- ✅ 已建立 `docs/ASTOCK_PROJECT_RISK_REGISTER.md`
- 后续 Phase 30-38 开始前必须检查相关 open 风险，完成后必须更新风险状态

### BL-218 架构决策记录治理

目标：

- ✅ 已建立 `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`
- 后续涉及 core、API、数据 schema、交易能力等级、WebUI 顶层导航、AI 输出边界的重大变更必须补 ADR

### BL-205 组合级风险与绩效归因

目标：

- 增加行业暴露、个股集中度、相关性、Beta、流动性、换手、VaR、压力测试和回撤归因要求
- 将单股/单策略分析升级为组合级投资工作台能力

### BL-400 DSA-10 多轮问股 — 支持单 symbol 上下文追问

| 状态 | 备注 |
|------|------|
| 📋 planned | 单股分析无上下文追问能力 |

现状：
- 单股分析缺少上下文追问能力

目标：
- 支持围绕单个 symbol 的上下文追问和报告引用

完成标准：
- 用户可围绕单一 symbol 连续追问，上下文不丢失
- 回答可引用历史报告和数据

### BL-401 DSA-11 图片/CSV/Excel 导入 — 自选股/持仓导入

| 状态 | 备注 |
|------|------|
| 📋 planned | 无导入功能 |

现状：
- 缺少导入功能，自选股/持仓需手动输入

目标：
- 支持导入 watchlist 或持仓
- 导入失败有可读错误

完成标准：
- 支持 CSV/Excel 文件导入
- 导入结果展示导入成功/失败明细

### BL-402 DSA-13 多市场支持 — A 股稳定后扩展港股/美股

| 状态 | 备注 |
|------|------|
| 📋 planned | 仅支持 A 股 |

现状：
- 当前只支持 A 股主路径

目标：
- A 股稳定后扩展港股、美股
- 不得影响 A 股主路径

完成标准：
- 多市场数据源接入
- 页面可区分市场来源

### BL-403 AIS-11 宏观分析 — 宏观数据、政策、行业映射

| 状态 | 备注 |
|------|------|
| 📋 planned | 无宏观数据查询和展示 |

现状：
- 宏观分析能力缺失

目标：
- 宏观数据、政策、行业映射进入主题研究
- 不抢 P0/P1 优先级

完成标准：
- 宏观数据可查询和展示
- 与行业和标的关联可追溯

### BL-404 TDX-07 Obsidian 消费 — 摘要/快照索引输出

| 状态 | 备注 |
|------|------|
| 📋 planned | 无 Obsidian 集成 |

现状：
- Obsidian 缺少 TDX 数据消费入口

目标：
- 只输出摘要或快照索引到 Obsidian
- 不同步大体量原始行情

完成标准：
- Obsidian 可接收摘要、链接和快照索引
- 不写入大体量原始行情数据

## 5. 建议执行顺序

建议以 `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` 中的 phase 顺序作为后续主线：

1. `Phase 30` / `BL-000`：Live Trading Readiness，先定实盘准入和能力口径
2. `Phase 31` / `BL-105`：Data Quality & Bias Control，补数据可信和回测可信
3. `Phase 32` / `BL-100`：Strategy Lab 模块整合
4. `Phase 33` / `BL-100A`：AI Research Center 模块整合
5. `Phase 34` / `BL-100B`：Market Leaders 龙头相关单入口
6. `Phase 35` / `BL-001` + `BL-002`：Trading & Execution，统一 QMT 能力边界和订单语义 — ✅ **已完成（done-with-exclusions）**
7. `Phase 36` / `BL-205`：Portfolio Risk & Attribution，补组合级风险和绩效归因
8. `Phase 37`：Ops & Audit，统一任务、错误、审计和健康状态
9. `Phase 38` / `BL-203`：Product Navigation Cleanup，清理多入口和体验一致性

## 6. 关联文档

- `docs/ASTOCK_REQUIREMENTS.md`
- `docs/ASTOCK_PRD.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`
- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`
- `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`
- `docs/ASTOCK_CURRENT_STATUS.md`

# A 股 WebUI 页面级验收清单

| 更新时间：2026-06-27 |

本文定义每个 WebUI 页面开发或重构完成后的页面级验收清单。它补充 `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`，重点检查输入、输出、页面状态、错误态、降级态和验收截图。

## 1. 验收记录模板

每个页面必须按以下模板记录：

| 字段 | 要求 |
|---|---|
| 页面名称 | 中文名和英文/路由名 |
| 入口路径 | 顶层导航、tab、旧入口跳转 |
| URL / route | Flask route 或前端路径 |
| 能力等级 | research / paper / managed / live-ready / mock |
| 输入 | 表单字段、query params、默认值 |
| 输出 | 表格、图表、卡片、报告、下载物 |
| API 依赖 | endpoint、method、关键 response 字段 |
| 数据来源 | provider、DuckDB、cache、LLM、QMT |
| 页面状态 | loading、empty、success、stale、degraded、error |
| 错误态 | 错误码、用户提示、重试动作 |
| 风险提示 | advisory、paper、managed、mock、数据延迟 |
| 验收截图 | success、empty、error/degraded 至少各一张或说明无法截图原因 |
| 测试命令 | API slice、UI slice、手工验证步骤 |
| 旧入口兼容 | 是否保留跳转、重定向或降级提示 |

## 2. 核心页面清单

| 模块 | 页面 | 必须验收的关键点 |
|---|---|---|
| Dashboard | 首页总览 | 系统状态、关键入口、能力标签、任务状态 |
| Dashboard | Dashboard v2（今日工作台） | 市场概览（指数、广度、板块）、自选/持仓摘要、AI任务状态（queued/running/succeeded/failed/cancelled/partial）、最新报告列表、提醒列表、板块/龙头/资金线索摘要、数据健康摘要、下一步操作区（开始分析、批量分析、查看报告、进入盯盘、运行回测、配置推送）、所有卡片需覆盖loading/empty/error/degraded/stale状态、无iframe使用、默认首页行为 |
| Watch Center v2 | 盯盘中心 | 自选列表合并、板块监测、龙虎榜、北向资金、提醒列表聚合、实时数据推送 |
| AI Research Center | 研究任务页 | symbol/date/mode 输入、模型和 prompt 信息、advisory 标记 |
| AI Research Center | 报告中心 | 报告列表、报告详情、来源、生成时间、复查入口 |
| AI Research Center | 完成度检查 | 报告完整性评分、缺失字段高亮、数据来源追溯、对比基准、复查建议 |
| Strategy Lab | 策略列表 | strategy registry、参数 schema、适用场景 |
| Strategy Lab | 回测页 | 输入区间、成本模型、指标、净值、交易明细、数据假设 |
| Strategy Lab | 优化页 | 参数空间、Top N、无交易参数处理、样本内/样本外标记 |
| Strategy Lab | 策略对比 | 多策略指标对比、排序、benchmark、可比性提示 |
| Strategy Lab | 完成度检查 | 策略完整性评分、参数覆盖率、回测覆盖率、数据依赖检查、对比基准 |
| Market Leaders | 龙头入口 | 单入口、顶部 tab、候选池、来源和刷新时间 |
| Market Leaders | 候选池 | 入池理由、出池理由、评分变化、资金线索 |
| Trading & Execution | 交易页 | paper/managed/live-ready 区分、风控结果、确认状态 |
| Trading & Execution | 风控页 | risk gate、reason code、kill switch 状态 |
| Data & Ops | 数据健康页 | provider、freshness、quality、fallback、snapshot |
| Data & Ops | 缓存管理页 | cache 状态、刷新、清理、stale/rebuilt 标记 |
| Data & Ops | 任务/审计页 | task lifecycle、错误、审计引用 |
| Portfolio Workbench | 组合风险页 | 持仓、行业暴露、集中度、回撤、归因 |
| Portfolio Risk & Execution | 组合风控与执行页 | 持仓汇总、行业暴露、集中度分析、回撤监控、归因分析、风控门禁状态、kill switch状态、执行确认队列、订单状态跟踪、交易日志 |

## 3. 页面状态验收

每个核心页面必须覆盖全部 6 种页面状态：loading、empty、success、stale、degraded、error。各状态定义如下：

- `loading`：等待数据或任务中。
- `empty`：无数据但页面可用，有下一步动作。
- `success`：正常展示核心输出。
- `stale`：数据过期或使用缓存。
- `degraded`：provider、LLM、QMT 或部分 API 不可用。
- `error`：API 失败、参数错误或系统异常。

交易相关页面还必须覆盖：

- `paper`：虚拟成交和虚拟资金。
- `managed`：受控执行，需要风控和人工确认。
- `blocked`：风控拦截或 kill switch 激活。
- `disabled`：QMT 不可用或 live-ready 未准入。

## 4. 错误态要求

错误态不得只显示“失败”。至少需要：

- error code。
- error category。
- retryable 标记或用户下一步动作。
- request id 或 task id。
- 数据是否保留旧值。
- 是否降级到 cache / fallback / paper / disabled。

## 5. 验收截图要求

每个 WebUI phase 至少留存：

- 主流程成功截图。
- 空态或初始态截图。
- 错误态或降级态截图。
- 交易相关页面的能力标签截图。
- 涉及旧入口迁移时的跳转/提示截图。

如果当前环境无法截图，phase 文档必须说明原因，并提供 API response 或 DOM 断言替代证据。

## 6. 验收通过标准

页面验收通过必须满足：

- 页面入口可达。
- 输入、输出和默认值明确。
- API 依赖和数据来源明确。
- loading / empty / error / degraded 至少有处理策略。
- research / paper / managed / live-ready / mock 标签不误导。
- 关键风险提示可见。
- 测试命令或手工步骤可复验。
- phase 文档引用本清单并附证据。

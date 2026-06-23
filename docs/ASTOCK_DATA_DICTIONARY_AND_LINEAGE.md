# A 股数据字典与数据血缘

| 更新时间：2026-06-23 |

本文定义 A 股数据字段、数据来源、质量标签和血缘要求。它用于支撑 Data Quality & Bias Control、Strategy Lab、AI Research、Trading 和 Ops 的生产级数据可信闭环。

## 1. 数据域

| 数据域 | 示例 | 主要使用模块 |
|---|---|---|
| 行情 | K 线、盘口、逐笔、成交量、涨跌幅 | Research、Strategy Lab、Trading |
| 基础资料 | 股票名称、交易所、上市日期、ST、退市状态 | Data & Ops、Strategy Lab |
| 估值/财务 | PE、PB、市值、营收、利润、资产负债 | Research、AI Research |
| 新闻 | 新闻标题、来源、发布时间、正文摘要 | AI Research |
| 公告 | 公告标题、类型、发布时间、原文链接 | AI Research |
| 研报 | 机构、评级、目标价、摘要、发布时间 | AI Research |
| 资金线索 | 龙虎榜、北向资金、主力资金 | Market Leaders |
| 回测结果 | trades、periods、metrics、equity curve | Strategy Lab |
| 交易状态 | 账户、订单、成交、持仓、风控结果 | Trading |
| 审计日志 | task run、audit event、数据快照 | Ops & Audit |

## 2. 核心字段字典

### 2.1 SecurityMaster

| 字段 | 类型 | 说明 | 质量要求 |
|---|---|---|---|
| `symbol` | string | 标准 A 股代码，如 `600519.SH` | 必须标准化 |
| `raw_symbol` | string | provider 原始代码 | 可选 |
| `name` | string | 股票名称 | 不能为空 |
| `exchange` | enum | `SH` / `SZ` / `BJ` | 必填 |
| `list_date` | date | 上市日期 | 回测防 survivorship bias 必需 |
| `delist_date` | date | 退市日期 | 可选 |
| `is_st` | bool | 是否 ST | 策略/风控必需 |
| `status` | enum | `active` / `suspended` / `delisted` | 必填 |

### 2.2 KLineBar

| 字段 | 类型 | 说明 | 质量要求 |
|---|---|---|---|
| `symbol` | string | 标准代码 | 必填 |
| `trade_date` | date/datetime | 交易日期或时间 | 必填 |
| `frequency` | enum | `1m` / `5m` / `30m` / `60m` / `1d` / `1w` / `1M` | 必填 |
| `open` | float | 开盘价 | 非负 |
| `high` | float | 最高价 | `high >= low` |
| `low` | float | 最低价 | `low <= high` |
| `close` | float | 收盘价 | 非负 |
| `volume` | float | 成交量 | 非负 |
| `amount` | float | 成交额 | 非负 |
| `adjust` | enum | `none` / `qfq` / `hfq` | 必填 |
| `provider` | string | 数据来源 | 必填 |
| `quality` | enum | `ok` / `stale` / `partial` / `fallback` / `invalid` | 必填 |

### 2.3 BacktestResult

| 字段 | 类型 | 说明 |
|---|---|---|
| `result_id` | string | 回测结果 ID |
| `strategy_name` | string | 策略名称 |
| `params` | object | 策略参数 |
| `symbols` | list[string] | 标的列表 |
| `start_date` / `end_date` | date | 数据区间 |
| `benchmark` | string | benchmark |
| `cost_model` | object | 佣金、印花税、滑点 |
| `data_assumptions` | object | 复权、停牌、涨跌停、T+1、样本外状态 |
| `metrics` | object | return、Sharpe、drawdown、win rate 等 |
| `trades` | list[object] | 交易明细 |
| `equity_curve` | list[object] | 净值曲线 |
| `data_snapshot_id` | string | 数据快照 |

### 2.4 ResearchAudit

| 字段 | 类型 | 说明 |
|---|---|---|
| `research_id` | string | 研究任务 ID |
| `symbol_scope` | list[string] | 标的范围 |
| `model` | string | 模型名称 |
| `prompt_hash` | string | prompt 哈希 |
| `context_snapshot_id` | string | 输入上下文快照 |
| `citations` | list[object] | 引用来源 |
| `generated_at` | datetime | 生成时间 |
| `confirmation_status` | enum | `none` / `reviewed` / `rejected` |

## 3. 数据血缘要求

每个数据对象必须能回答：

- 来源 provider 是什么？
- 是否来自 cache / DuckDB / live provider / mock？
- 何时生成或刷新？
- 是否发生 fallback？
- 是否有质量降级？
- 被哪些回测、研究、报告或交易动作使用？

## 4. 数据质量标签

| 标签 | 含义 | 展示要求 |
|---|---|---|
| `ok` | 数据完整且新鲜 | 正常展示 |
| `stale` | 数据过期 | 黄色标记，禁止 live-ready |
| `partial` | 字段缺失但可降级使用 | 显示缺失字段 |
| `fallback` | 主源失败后使用备源 | 显示 fallback 轨迹 |
| `mock` | 模拟或测试数据 | 明确标记，不得用于实盘 |
| `invalid` | 数据不可信 | 阻断回测比较或交易执行 |

## 5. 回测数据假设

每个回测必须记录：

- 数据来源和快照 ID。
- 复权方式。
- 是否包含退市/停牌/ST。
- 是否应用涨跌停不可成交。
- 是否应用 T+1。
- 成本模型和滑点。
- 是否样本外。
- 是否执行未来函数/look-ahead 检查。

## 6. 刷新频率要求

| 数据域 | 生产口径刷新频率 | 说明 |
|---|---|---|
| 日 K | 每交易日收盘后 | 回测主数据 |
| 分钟 K | 盘中按需或定时 | 研究/交易辅助 |
| 估值 | 每交易日或 provider 更新后 | 允许延迟但必须标注 |
| 新闻/公告 | 按 provider 更新 | 必须保留发布时间 |
| 研报 | 按 provider 更新 | 必须保留机构和发布时间 |
| 订单/成交 | 交易动作后实时或轮询 | live-ready 前必须 reconciliation |

## 7. 验收要求

- Phase 31 必须实现 DataQualityTag 和 BacktestDataAssumption 的文档/代码映射。
- Phase 32 必须让 BacktestResult 引用 data snapshot。
- Phase 33 必须让 ResearchAudit 引用 context snapshot。
- Phase 35 必须让订单和成交引用数据快照与审计事件。

# A 股测试与验收计划

| 更新时间：2026-06-23 |

本文定义 TradingAgents-Astock 的生产级测试、验收和发布门槛。它不替代 `tests/` 和 `docs/phases/`，而是规定后续 phase 如何证明“可以进入下一阶段”。

## 1. 测试分层

| 层级 | 目标 | 示例 |
|---|---|---|
| Unit | 验证函数/类行为 | 策略信号、费用模型、数据清洗 |
| Contract | 验证 schema/API 契约 | advisory schemas、API envelope、错误码 |
| Integration | 验证模块接线 | data router -> interface -> runtime |
| UI/API Slice | 验证页面和 API 闭环 | Flask WebUI + routes |
| Regression | 验证历史能力不退化 | A 股主链切片、全仓 pytest |
| Live Guarded | 验证外部依赖 | live provider、QMT、LLM |
| UAT | 验证用户工作流 | 研究、回测、模拟盘、受控执行 |

## 2. 标准验收门槛

每个 phase 必须提供：

- scope。
- 修改文件。
- API/UI/store schema 是否变化。
- 测试命令。
- 测试结果。
- 已知 skipped 原因。
- 风险和回滚。
- commit SHA。

## 3. 模块验收要求

### 3.1 Data & Ops

- provider fallback 可测试。
- stale/partial/mock/fallback/invalid 标签可验证。
- 数据刷新失败有错误码。
- DuckDB/store 读写可验证。

### 3.2 AI Research Center

- live research 缺少真实 LLM 时 fail closed。
- deterministic verification 可离线运行。
- 每个 AI 输出保留模型、prompt、数据快照和引用来源。
- advisory 输出不触发真实交易。

### 3.3 Strategy Lab

- 策略信号无 NaN 泄漏。
- 回测禁止未来函数。
- 回测结果包含数据假设、成本模型、benchmark。
- 优化结果不能让无交易参数排前。
- 多策略对比排序稳定。

### 3.4 Market Leaders

- 候选池有来源和刷新时间。
- 入池/出池理由可解释。
- 板块、资金、龙虎榜、北向均标注数据来源。

### 3.5 Trading & Execution

- paper 与 managed 视觉和 API 均区分。
- Risk Gate 拦截有 reason code。
- kill switch 可阻断后续交易。
- managed order 必须有人工确认记录。
- live-ready 前 reconciliation 可检测。

### 3.6 Ops & Audit

- 长任务有 task lifecycle。
- 关键动作有 Audit Event。
- 错误进入错误中心。
- 告警级别和处理动作可追踪。

## 4. UAT 场景

| 场景 | 步骤 | 通过标准 |
|---|---|---|
| 研究报告 | 输入 A 股 symbol -> 运行 AI Research -> 生成报告 | 报告含数据来源、模型、时间和 advisory 标记 |
| 策略回测 | 选择策略 -> 设置区间 -> 运行回测 | 输出指标、交易明细、数据假设和 benchmark |
| 策略优化 | 选择策略 -> grid search -> 查看 Top N | 无交易/数据不足参数不排前 |
| 龙头决策 | 打开 Market Leaders -> 查看候选池 -> 进入资金线索 | 候选股有入池理由和数据来源 |
| 模拟盘 | 发起 paper order -> 查看虚拟成交和持仓 | 明确显示 paper，不显示为真实账户 |
| 受控执行 | 发起 managed action -> 风控 -> 人工确认 | 无确认不得执行，拦截有 reason |
| Ops 审计 | 查看任务/错误/审计 | 能追踪关键动作和失败原因 |

## 5. 发布门槛

| 发布类型 | 最低要求 |
|---|---|
| docs-only | `git diff --check -- docs` 通过，索引无断链 |
| API change | contract tests + API slice tests |
| WebUI change | WebUI/API slice tests + 关键页面手工验证 |
| Strategy change | strategy unit + backtest + optimizer tests |
| Data change | provider fixture + data quality tests |
| Trading change | risk gate + paper/managed tests + rollback plan |
| Live-ready claim | runbook checklist + reconciliation + audit evidence |

## 6. 不允许验收的情况

- 只凭页面能打开就验收。
- 只凭 DeepSeek/Hermes 自述就验收。
- mock 数据被描述为 real。
- paper 状态被描述为真实账户。
- live provider 失败但没有 skip guard 或失败说明。
- 交易相关变更没有风控和回滚说明。

## 7. 后续要求

- Phase 30 起，每个 phase 文档必须引用本测试计划。
- Phase 31 起，回测必须展示数据质量和反偏差状态。
- Phase 35 起，交易相关验收必须包含订单生命周期和 kill switch。
- Phase 37 起，所有长任务必须有 Task Run 证据。

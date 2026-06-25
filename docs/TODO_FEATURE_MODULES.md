# 功能模块开发 TODO 清单

> 生成时间：2026-06-25
> 排除范围：实盘账户与交易相关（BL-000 ~ BL-004 暂不处理）
> 参考文档：`docs/ASTOCK_BACKLOG.md`、`docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`、`docs/phases/phase-3*.md`

---

## Phase 31 — BL-105 数据质量与回测反偏差

**前置依赖**: Phase 30（TradingMode enum、capability 标注规范）
**当前状态**: Phase 31 schema 已定义（`BacktestDataAssumption`），但功能不完整

### 31-01 数据质量标签体系
- [ ] 31-01-01 定义 `DataQualityTag` schema（normal/stale/partial/fallback/mock/degraded）
  - 文件：`tradingagents/astock/schemas/data_quality.py`（新建 schemas 目录）
  - 参考：Phase 31 任务 31-02 brief
- [ ] 31-01-02 在 provider 层附加 quality tag（router.py、adapters.py）
- [ ] 31-01-03 API 响应中携带 quality tag（routes_data.py）
- [ ] 31-01-04 Data Health 页面展示 quality tag（data_health.html）

### 31-02 交易日历
- [ ] 31-02-01 实现交易日历查询（排除节假日、周末、半日市）
  - 数据源：akshare calendar 或 mootdx
- [ ] 31-02-02 回测引擎中校验交易日（非交易日跳过/标记）
- [ ] 31-02-03 API 提供 `/api/v1/market/calendar` 端点

### 31-03 停复牌处理
- [ ] 31-03-01 定义停牌状态 schema（suspended_date/resumed_date/reason）
  - 当前无稳定数据源，标记为 `planned`
- [ ] 31-03-02 回测中标记停牌日不可成交
- [ ] 31-03-03 前端展示停牌标识

### 31-04 涨跌停处理
- [ ] 31-04-01 定义涨跌停状态 schema（limit_up/limit_down/price_range）
- [ ] 31-04-02 回测中校验涨跌停不可成交逻辑
- [ ] 31-04-03 行情数据中标注涨跌停状态

### 31-05 复权处理
- [ ] 31-05-01 统一前复权/后复权/不复权接口
- [ ] 31-05-02 除权除息日期与因子记录
- [ ] 31-05-03 回测默认使用前复权，可配置
- [ ] 31-05-04 复权数据 provenance 追踪

### 31-06 ST/退市处理
- [ ] 31-06-01 定义 ST/\*ST 标识 schema
- [ ] 31-06-02 退市股数据归档与过滤机制
- [ ] 31-06-03 回测中排除退市股或单独标记

### 31-07 Survivorship Bias 检测
- [ ] 31-07-01 实现幸存者偏差检测（退市股是否纳入回测池）
- [ ] 31-07-02 在 `BacktestDataAssumption` 中增加 `survivorship_bias_checked` 字段
- [ ] 31-07-03 回测结果页面展示 survivorship bias 状态

### 31-08 Look-ahead Bias 检测
- [ ] 31-08-01 实现未来函数检测机制（财报发布日期 vs 使用日期）
- [ ] 31-08-02 在 `BacktestDataAssumption` 中增加 `look_ahead_bias_checked` 字段
- [ ] 31-08-03 回测结果页面展示 look-ahead bias 状态

### 31-09 数据质量分级与 Provenance
- [ ] 31-09-01 定义数据质量等级（实时/准实时/历史/缺失）
- [ ] 31-09-02 每层数据 quality tag 与 provenance 记录
- [ ] 31-09-03 Provider fallback 时记录质量降级轨迹
- [ ] 31-09-04 Data Health 页面展示 provenance 信息

### 31-10 回测约束完善
- [ ] 31-10-01 涨跌停不可成交逻辑
- [ ] 31-10-02 停牌不可成交逻辑
- [ ] 31-10-03 T+1 结算约束
- [ ] 31-10-04 成交量容量约束
- [ ] 31-10-05 滑点模型可配置

### 31-11 文档与测试
- [ ] 31-11-01 编写 Phase 31 归档文档（更新 `docs/phases/phase-31-data-quality-bias-control.md`）
- [ ] 31-11-02 单元测试：`tests/test_data_quality_tags.py`
- [ ] 31-11-03 单元测试：`tests/test_survivorship_bias.py`
- [ ] 31-11-04 单元测试：`tests/test_lookahead_bias.py`
- [ ] 31-11-05 集成测试：回测结果附带数据质量报告
- [ ] 31-11-06 运行验收：`pytest tests/test_astock_data_sources.py -q`

---

## Phase 32 — BL-100 Strategy Lab 模块整合

**前置依赖**: Phase 31（`BacktestDataAssumption` schema、`DataQualityTag`）
**当前状态**: 策略/回测/优化/绩效/对比已存在，但入口分散

### 32-01 策略注册完善
- [ ] 32-01-01 审查现有 `_STRATEGY_REGISTRY` 完整性（`strategy_registry.py`）
- [ ] 32-01-02 确保所有 10 种策略都有 `params_schema` 定义
- [ ] 32-01-03 为动量轮动明确 Standalone 模式兼容性
- [ ] 32-01-04 统一 `execution/__init__.py` 导出与 registry 不漂移

### 32-02 Backtest Result Schema 完善
- [ ] 32-02-01 在 `BacktestResult` 中强制关联 `data_assumption`（已有但需完善）
- [ ] 32-02-02 增加 benchmark 对比字段
- [ ] 32-02-03 增加成本模型明细（commission/stamp_tax/slippage 分项）
- [ ] 32-02-04 增加交易明细中的涨跌停/停牌标记

### 32-03 Optimize Result Schema
- [ ] 32-03-01 定义 `OptimizeResult` schema（score/top_n/in_sample/out_sample/walk_forward）
  - 文件：新建 `tradingagents/astock/schemas/optimization.py`
- [ ] 32-03-02 API 端点 `/api/v1/backtest/optimize` 返回标准化 schema

### 32-04 Strategy Hub 页面整合
- [ ] 32-04-01 梳理 `strategy_hub.html` 当前 tab 结构
- [ ] 32-04-02 统一回测/优化/绩效/对比入口到 Strategy Hub
- [ ] 32-04-03 旧入口迁移策略（keep/redirect/deprecate）

### 32-05 动量轮动归属明确
- [ ] 32-05-01 明确动量轮动在 Strategy Lab 中的定位（组合策略 Standalone）
- [ ] 32-05-02 `momentum_rotation.html` 与 Strategy Hub 的关系

### 32-06 文档与测试
- [ ] 32-06-01 编写 Phase 32 归档文档
- [ ] 32-06-02 运行验收：`pytest tests/test_astock_strategies.py -q`
- [ ] 32-06-03 运行验收：`pytest tests/test_astock_backtest.py -q`
- [ ] 32-06-04 运行验收：`pytest tests/test_astock_optimizer.py -q`

---

## Phase 33 — BL-100A AI Research Center 模块整合

**前置依赖**: Phase 31（`data_assumption`、`DataQualityTag`）、Phase 32（`BacktestResult`）
**当前状态**: AI Agent/研究页/报告中心已存在，但缺统一审计

### 33-01 ResearchTask Schema
- [ ] 33-01-01 定义 `ResearchTask` schema（task_id/symbol/mode/status/snapshot）
  - 文件：新建 `tradingagents/astock/schemas/research_task.py`
- [ ] 33-01-02 支持单股/多股/主题/行业/持仓组合任务类型

### 33-02 ResearchAudit Schema
- [ ] 33-02-01 定义 `ResearchAudit` schema（model/prompt/snapshot/citation/generated_at）
  - 文件：新建 `tradingagents/astock/schemas/research_audit.py`
- [ ] 33-02-02 AI 输出强制记录输入数据版本、模型版本、prompt 版本

### 33-03 上下文包统一
- [ ] 33-03-01 定义上下文包 schema（行情/财务/公告/新闻/研报/策略结果/持仓风险）
- [ ] 33-03-02 AI Agent 页面复用统一上下文

### 33-04 Advisory-Only 强制
- [ ] 33-04-01 确保所有 AI 输出默认 advisory-only
- [ ] 33-04-02 AI 结论不得直接触发真实订单

### 33-05 LLM 降级策略
- [ ] 33-05-01 定义 LLM 不可用时的降级行为（fail closed / degraded）
- [ ] 33-05-02 降级状态在 UI 中显著标识

### 33-06 报告归档完善
- [ ] 33-06-01 统一 Markdown/JSON/PPT/Web report 归档字段
- [ ] 33-06-02 报告中心支持检索、复查、对比

### 33-07 文档与测试
- [ ] 33-07-01 编写 Phase 33 归档文档
- [ ] 33-07-02 运行验收：`pytest tests/test_astock_graph_runtime.py -q`
- [ ] 33-07-03 运行验收：`pytest tests/test_astock_graph_bridge.py -q`
- [ ] 33-07-04 运行验收：`pytest tests/test_astock_ppt.py -q`

---

## Phase 34 — BL-100B Market Leaders 单入口

**前置依赖**: Phase 31（`DataQualityTag`）
**当前状态**: 龙头/板块/资金/轮动页面分散（5 个独立入口）

### 34-01 Market Leaders 顶层入口
- [ ] 34-01-01 设计统一的 Market Leaders 页面（新模板或整合现有页面）
- [ ] 34-01-02 顶层导航只保留一个 Market Leaders / 龙头决策入口
- [ ] 34-01-03 内部 tab 设计：动量总览/候选池/板块强弱/资金线索/轮动回测

### 34-02 LeaderPool Schema 完善
- [ ] 34-02-01 审查现有 `LeaderPoolEntry` schema（`leader_pool.py`）
- [ ] 34-02-02 确保包含 source/reason/score/refreshed_at/entry_reason/exit_reason
- [ ] 34-02-03 候选池入池/出池理由可解释、可追溯

### 34-03 旧入口迁移
- [ ] 34-03-01 `momentum_dashboard.html` → 迁移/重定向到 Market Leaders
- [ ] 34-03-02 `momentum_rotation.html` → 迁移/重定向到 Market Leaders
- [ ] 34-03-03 `dragon_tiger.html` → 作为资金线索子 tab
- [ ] 34-03-04 `northbound.html` → 作为资金线索子 tab
- [ ] 34-03-05 `sectors.html` → 作为板块强弱子 tab

### 34-04 Fallback 语义标注
- [ ] 34-04-01 EastMoney/Sina/mock fallback 显著标注
- [ ] 34-04-02 mock 数据不得误导为真实数据

### 34-05 文档与测试
- [ ] 34-05-01 编写 Phase 34 归档文档
- [ ] 34-05-02 运行验收：`pytest tests/test_astock_web.py -q`
- [ ] 34-05-03 运行验收：`pytest tests/test_astock_api.py -q`

---

## Phase 36 — BL-205 组合级风险与绩效归因

**前置依赖**: Phase 32（`BacktestResult`、Strategy Registry）、Phase 35（Order/Position/Fill schema）
**当前状态**: 仅单股/单策略分析，无组合级能力

### 36-01 Portfolio Schema
- [ ] 36-01-01 定义 `Portfolio` schema（holdings/cash/nav）
  - 文件：新建 `tradingagents/astock/schemas/portfolio.py`
- [ ] 36-01-02 支持回测组合和模拟盘组合复用

### 36-02 RiskExposure Schema
- [ ] 36-02-01 定义 `RiskExposure` schema（industry/concentration/beta/liquidity）
- [ ] 36-02-02 行业暴露计算
- [ ] 36-02-03 个股集中度分析（HHI/Top-N）
- [ ] 36-02-04 Beta 计算（相对于沪深 300）
- [ ] 36-02-05 流动性评估

### 36-03 Attribution Schema
- [ ] 36-03-01 定义 `Attribution` schema（benchmark/selection/timing/cost/slippage）
- [ ] 36-03-02 超额收益分解（选股贡献/择时贡献）
- [ ] 36-03-03 交易成本贡献分析
- [ ] 36-03-04 滑点贡献分析

### 36-04 压力测试与 VaR
- [ ] 36-04-01 定义压力测试指标 schema（VaR/DD/stress scenarios）
- [ ] 36-04-02 历史情景压力测试（2015 股灾/2020 疫情/2022 封控）
- [ ] 36-04-03 最大回撤分解

### 36-05 Portfolio Workbench 页面
- [ ] 36-05-01 设计 Portfolio Workbench 页面（新模板 `portfolio.html`）
- [ ] 36-05-02 风险暴露可视化（行业分布/集中度）
- [ ] 36-05-03 归因分析可视化
- [ ] 36-05-04 压力测试结果展示

### 36-06 文档与测试
- [ ] 36-06-01 编写 Phase 36 归档文档
- [ ] 36-06-02 运行验收：`pytest tests/test_astock_backtest.py -q`
- [ ] 36-06-03 运行验收：`pytest tests/test_astock_paper_trader.py -q`

---

## Phase 37 — Ops & Audit Center

**前置依赖**: Phase 30-36 所有 schema 和 API
**当前状态**: 有 data health/SSE/缓存，但无统一审计

### 37-01 TaskRun Schema
- [ ] 37-01-01 定义 `TaskRun` schema（type/status/start/end/error）
  - 文件：新建 `tradingagents/astock/schemas/task_run.py`
- [ ] 37-01-02 覆盖任务类型：数据刷新/回测/AI 分析/报告生成

### 37-02 AuditEvent Schema
- [ ] 37-02-01 定义 `AuditEvent` schema（actor/input/output/snapshot/model/confirmation）
  - 文件：新建 `tradingagents/astock/schemas/audit_event.py`
- [ ] 37-02-02 关键操作自动记录审计事件

### 37-03 SSE Event 标准化
- [ ] 37-03-01 梳理现有 SSE event 字段（`routes_sse.py`）
- [ ] 37-03-02 迁移到 TaskRun schema

### 37-04 Ops Dashboard 页面
- [ ] 37-04-01 设计 Ops Dashboard 页面（新模板 `ops_audit.html`）
- [ ] 37-04-02 任务中心（进行中/已完成/失败）
- [ ] 37-04-03 错误中心（错误类型/影响范围/建议处理）
- [ ] 37-04-04 健康状态总览（provider/DuckDB/缓存/LLM/WebUI）

### 37-05 文档与测试
- [ ] 37-05-01 编写 Phase 37 归档文档
- [ ] 37-05-02 运行验收：`pytest tests/test_astock_sse.py -q`

---

## Phase 38 — BL-203 Product Navigation Cleanup

**前置依赖**: Phase 32-37 所有模块页面收敛
**当前状态**: 22 个独立页面，导航重复，入口分散

### 38-01 页面清点
- [ ] 38-01-01 列出所有 22 个 template 页面
- [ ] 38-01-02 列出当前 sidebar/nav 入口

### 38-02 目标导航设计
- [ ] 38-02-01 定义目标顶层导航（7 个模块）：
  - Dashboard
  - AI Research Center
  - Strategy Lab
  - Market Leaders
  - Trading & Execution
  - Data & Ops
  - Portfolio Workbench
- [ ] 38-02-02 绘制导航 Mermaid 图

### 38-03 旧入口迁移
- [ ] 38-03-01 标记每个旧入口的迁移策略（redirect/hidden/legacy）
- [ ] 38-03-02 更新 `base.html` / `base_standalone.html` 导航

### 38-04 文档与测试
- [ ] 38-04-01 更新 WebUI 产品规范（`ASTOCK_WEBUI_PRODUCT_SPEC.md`）
- [ ] 38-04-02 更新页面级验收清单（`ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`）
- [ ] 38-04-03 编写 Phase 38 归档文档
- [ ] 38-04-04 运行验收：`pytest tests/test_astock_web.py -q`
- [ ] 38-04-05 运行验收：`pytest tests/test_astock_api.py -q`

---

## Phase 39 — 端到端 UAT

**前置依赖**: Phase 30-38 全部完成
**当前状态**: 无端到端用户工作流验收

### 39-01 UAT 场景设计
- [ ] 39-01-01 编写 6 个端到端 UAT 场景表：
  1. 完整研究链路（symbol → AI Research → 报告 → 可追溯）
  2. 研究→回测→模拟盘（报告 → 策略 → 回测 → 模拟盘）
  3. 策略→交易（回测 → 优化 → 模拟盘下单 → 风控门）
  4. 龙头→候选池→交易（候选池 → 入池理由 → 交易页）
  5. 数据→AI→报告归档（数据刷新 → AI Research → 归档 → 复查）
  6. Ops 审计追溯（任意操作 → Ops Dashboard 查询）

### 39-02 UAT 执行
- [ ] 39-02-01 执行 UAT 场景 1-3
- [ ] 39-02-02 执行 UAT 场景 4-6
- [ ] 39-02-03 记录通过/失败结果
- [ ] 39-02-04 失败场景 root cause 分析

### 39-03 文档更新
- [ ] 39-03-01 更新 `ASTOCK_CURRENT_STATUS.md` 记录 UAT 结果

---

## 依赖关系总览

```
Phase 31 → Phase 32 → Phase 33 → Phase 34 → Phase 38
                    ↓           ↓
              Phase 36 → Phase 37 → Phase 38 → Phase 39
```

**强制依赖**:
- Phase 32 依赖 Phase 31 的 schema
- Phase 33 依赖 Phase 31 + Phase 32
- Phase 34 依赖 Phase 31
- Phase 36 依赖 Phase 32
- Phase 37 依赖 Phase 30-36
- Phase 38 依赖 Phase 32-37
- Phase 39 依赖 Phase 30-38

---

## 测试命令汇总

```bash
# Phase 31
pytest tests/test_astock_data_sources.py -q
pytest tests/test_astock_provider_fixtures.py -q
pytest tests/test_astock_tv_routes.py -q

# Phase 32
pytest tests/test_astock_strategies.py -q
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_optimizer.py -q
pytest tests/test_astock_api.py -q

# Phase 33
pytest tests/test_astock_graph_runtime.py -q
pytest tests/test_astock_graph_bridge.py -q
pytest tests/test_astock_ppt.py -q
pytest tests/test_astock_web.py -q

# Phase 34
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q

# Phase 36
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_paper_trader.py -q
pytest tests/test_astock_api.py -q

# Phase 37
pytest tests/test_astock_sse.py -q
pytest tests/test_astock_api.py -q
pytest tests/test_astock_web.py -q

# Phase 38
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q

# 全量回归
pytest tests/ -q
```

---

## 新建文件清单

| 文件路径 | 说明 | 所属 Phase |
|---------|------|-----------|
| `tradingagents/astock/schemas/` | 新建 schemas 目录 | 31-37 |
| `tradingagents/astock/schemas/data_quality.py` | DataQualityTag schema | 31 |
| `tradingagents/astock/schemas/optimization.py` | OptimizeResult schema | 32 |
| `tradingagents/astock/schemas/research_task.py` | ResearchTask schema | 33 |
| `tradingagents/astock/schemas/research_audit.py` | ResearchAudit schema | 33 |
| `tradingagents/astock/schemas/portfolio.py` | Portfolio schema | 36 |
| `tradingagents/astock/schemas/risk_exposure.py` | RiskExposure schema | 36 |
| `tradingagents/astock/schemas/attribution.py` | Attribution schema | 36 |
| `tradingagents/astock/schemas/task_run.py` | TaskRun schema | 37 |
| `tradingagents/astock/schemas/audit_event.py` | AuditEvent schema | 37 |
| `tradingagents/astock/web/templates/portfolio.html` | Portfolio Workbench | 36 |
| `tradingagents/astock/web/templates/ops_audit.html` | Ops Dashboard | 37 |
| `tests/test_data_quality_tags.py` | 数据质量标签测试 | 31 |
| `tests/test_survivorship_bias.py` | 幸存者偏差测试 | 31 |
| `tests/test_lookahead_bias.py` | 前视偏差测试 | 31 |

# 功能模块开发 TODO 清单 — 实际完成状态

> 更新时间：2026-06-25
> 排除范围：实盘账户与交易相关（BL-000 ~ BL-004 暂不处理）

> ⚠️ 本文件已更新为当前实际完成状态。之前的版本标记了大量已完成的子任务为 [ ]。

---

## Phase 31 — BL-105 数据质量与回测反偏差

**前置依赖**: Phase 30（TradingMode enum、capability 标注规范）

### 31-01 数据质量标签体系
- [x] 31-01-01 定义 `DataQualityTag` schema → commit `f8ded44` (附在 AStockResponse.meta.quality)
- [x] 31-01-02 在 provider 层附加 quality tag → commit `f8ded44`
- [x] 31-01-03 API 响应中携带 quality tag → commit `72a276a`
- [x] 31-01-04 Data Health 页面展示 quality tag → commit `2efdc18`

### 31-02 交易日历
- [x] 31-02-01 实现交易日历查询 → commit `70cc10d`
- [x] 31-02-02 回测引擎中校验交易日 → commit `c902808`
- [x] 31-02-03 API 提供 `/api/v1/market/calendar` 端点 → commit `70cc10d`

### 31-03 停复牌处理
- [ ] 31-03-01 定义停牌状态 schema — **数据源不稳定，标记 planned**
- [ ] 31-03-02 回测中标记停牌日不可成交
- [ ] 31-03-03 前端展示停牌标识

### 31-04 涨跌停处理
- [ ] 31-04-01 定义涨跌停状态 schema — **数据源不稳定，标记 planned**
- [ ] 31-04-02 回测中校验涨跌停不可成交逻辑
- [ ] 31-04-03 行情数据中标注涨跌停状态

### 31-05 复权处理
- [x] 31-05-01 统一前复权/后复权/不复权接口 → commit `07cd0d1`
- [ ] 31-05-02 除权除息日期与因子记录 — **数据源受限**
- [x] 31-05-03 回测默认使用前复权，可配置 → BacktestDataAssumption.adjustment
- [x] 31-05-04 复权数据 provenance 追踪 → ResearchContext 已有 DataSourceMeta

### 31-06 ST/退市处理
- [ ] 31-06-01 定义 ST/*ST 标识 schema — **数据源不稳定**
- [ ] 31-06-02 退市股数据归档与过滤机制
- [ ] 31-06-03 回测中排除退市股或单独标记

### 31-07 Survivorship Bias 检测
- [ ] 31-07-01 实现幸存者偏差检测功能 — **schema 字段已存在** (survivorship_bias_risk)
- [ ] 31-07-02 BacktestDataAssumption 字段已存在
- [ ] 31-07-03 回测结果页面展示

### 31-08 Look-ahead Bias 检测
- [ ] 31-08-01 实现未来函数检测 — **schema 字段已存在** (look_ahead_bias_risk)
- [ ] 31-08-02 BacktestDataAssumption 字段已存在
- [ ] 31-08-03 回测结果页面展示

### 31-09 数据质量分级与 Provenance
- [x] 31-09-01 数据质量等级 — DataQualityTag 已定义
- [x] 31-09-02 每层数据 quality tag — ResearchContext + DataSourceMeta
- [x] 31-09-03 Provider fallback 质量降级轨迹 — Phase 33 LLM degradation
- [x] 31-09-04 Data Health 页面展示 provenance — 已有

### 31-10 回测约束完善
- [ ] 31-10-01 涨跌停不可成交逻辑 — **待实现**
- [ ] 31-10-02 停牌不可成交逻辑 — **待实现**
- [x] 31-10-03 T+1 结算约束 — SettlementConstraint 已定义
- [ ] 31-10-04 成交量容量约束 — **待实现**
- [x] 31-10-05 滑点模型可配置 — AStockFeeConfig + slippage_bps 已实现

### 31-11 文档与测试
- [x] 31-11-01 Phase 31 归档文档 — 已有 evidence doc
- [x] 31-11-06 运行验收：`pytest tests/test_astock_data_sources.py -q` → 通过

---

## Phase 32 — BL-100 Strategy Lab 模块整合

**前置依赖**: Phase 31（BacktestDataAssumption schema、DataQualityTag）

### 32-01 策略注册完善
- [x] 32-01-01 审查 `_STRATEGY_REGISTRY` — strategy_registry.py 已存在
- [x] 32-01-02 所有策略 params_schema — 已有
- [x] 32-01-04 `execution/__init__.py` 导出 — 已统一

### 32-02 Backtest Result Schema 完善
- [x] 32-02-01 BacktestResult 关联 data_assumption — 已有
- [x] 32-02-02 benchmark 对比字段 — commit `5ef7467`
- [x] 32-02-03 成本模型明细 — fee_model.py + fee_config_used 已实现
- [ ] 32-02-04 交易明细中的涨跌停/停牌标记 — **依赖 31-03/31-04**

### 32-03 Optimize Result Schema
- [x] 32-03-01 OptimizeResult schema — `schemas/optimization.py` 已有
- [ ] 32-03-02 API 端点 `/api/v1/backtest/optimize` 返回标准化 schema — **待实现**

### 32-04 Strategy Hub 页面整合
- [x] 32-04-01 梳理 `strategy_hub.html` tab 结构 — 已有
- [ ] 32-04-02 统一回测/优化/绩效/对比入口到 Strategy Hub — **待实现**
- [ ] 32-04-03 旧入口迁移策略 — **待文档**

### 32-05 动量轮动归属
- [x] 32-05-01 动量轮动定位 — 明确为组合策略 Standalone
- [x] 32-05-02 momentum_rotation.html 关系 — 已有独立入口

### 32-06 文档与测试
- [x] 32-06-02 tests/test_astock_strategies.py — 通过
- [x] 32-06-03 tests/test_astock_backtest.py — 通过
- [x] 32-06-04 tests/test_astock_optimizer.py — 通过

---

## Phase 33 — BL-100A AI Research Center 模块整合

**前置依赖**: Phase 31（data_assumption、DataQualityTag）、Phase 32（BacktestResult）

### 33-01 ResearchTask Schema
- [x] 33-01-01 ResearchTask schema — `phase33_37_schemas.py` 已有
- [ ] 33-01-02 支持多标的/主题/行业/持仓组合任务类型 — **ResearchTask.symbol 当前为 str**

### 33-02 ResearchAudit Schema
- [x] 33-02-01 ResearchAudit schema — `phase33_37_schemas.py` 已有
- [x] 33-02-02 AI 输出强制记录输入版本 — 已接入 routes_ai_agent.py

### 33-03 上下文包统一
- [x] 33-03-01 上下文包 schema — ResearchContext 已实现
- [ ] 33-03-02 AI Agent 页面复用统一上下文 — **待实现（ai_agent.html）**

### 33-04 Advisory-Only 强制
- [x] 33-04-01 所有 AI 输出 advisory-only — schema + API 双 enforce ✅
- [x] 33-04-02 AI 结论不得触发订单 — advisory=True 已强制

### 33-05 LLM 降级策略
- [x] 33-05-01 LLM 不可用时降级 — status=degraded + llm_error 已实现
- [ ] 33-05-02 降级状态在 UI 中显著标识 — **待实现（ai_agent.html）**

### 33-06 报告归档完善
- [x] 33-06-01 统一归档字段 — ReportArchive schema 已实现
- [ ] 33-06-02 报告中心支持检索/复查/对比 — **待实现（reports.html）**

### 33-07 文档与测试
- [x] 33-07-01 Phase 33 归档文档 — 已更新
- [x] 33-07-02 tests/test_astock_graph_runtime.py — 通过
- [x] 33-07-03 tests/test_astock_graph_bridge.py — 通过
- [x] 33-07-04 tests/test_astock_ppt.py — 通过

---

## Phase 34 — BL-100B Market Leaders 单入口

**前置依赖**: Phase 31（DataQualityTag）

### 34-01 Market Leaders 顶层入口
- [x] 34-01-01 统一 Market Leaders 页面 — market_leaders.html 已有
- [x] 34-01-02 导航只保留一个入口 — 5→1 sidebar consolidation
- [x] 34-01-03 内部 tab 设计 — 5 个 tab（龙头/板块/北向/龙虎榜/动量轮动）

### 34-02 LeaderPool Schema 完善
- [x] 34-02-01 LeaderPoolEntry schema — leader_pool.py 已有
- [x] 34-02-02 source/reason/score/refreshed_at/entry_reason/exit_reason — 完整
- [x] 34-02-03 入池/出池理由可追溯 — 字段已有

### 34-03 旧入口迁移
- [x] 34-03-01~05 旧入口保留但不在 sidebar — 已完成

### 34-04 Fallback 语义标注
- [x] 34-04-01 EastMoney/Sina/mock fallback — LeaderPoolEntry.source 字段已标注
- [x] 34-04-02 mock 数据不误导 — source 字段标注来源

### 34-05 文档与测试
- [x] 34-05-01 Phase 34 归档文档 — 已有 evidence summary
- [x] 34-05-02 tests/test_astock_web.py — 通过
- [x] 34-05-03 tests/test_astock_api.py — 通过

---

## 真正需要实现的任务总表

| 优先级 | ID | 描述 | 说明 |
|--------|-----|------|------|
| P0 | 31-10-04 | 成交量容量约束 | `backtest_engine.py` 中根据日成交量限制单笔交易量 |
| P0 | 32-03-02 | `/api/v1/backtest/optimize` 端点 | 返回标准化 OptimizeResult |
| P1 | 33-01-02 | ResearchTask 支持多标的 | `symbol: str` → `symbols: list[str]` |
| P1 | 36-01 | Schema 拆分 | 从 `phase33_37_schemas.py` 拆到独立文件 |
| P1 | 37-01 | Schema 拆分 + SSE 标准化 | 同上 + routes_sse.py 使用 TaskRun schema |
| P2 | 36-02 | Portfolio Workbench 页面 | 新 HTML 模板 |
| P2 | 37-02 | Ops Dashboard 页面 | 新 HTML 模板 |
| P2 | 38-01 | Navigation 清理 | 清点所有页面 + 目标导航设计 |
| P3 | 31-03/04 | 停复牌/涨跌停 | 依赖稳定数据源，标记 planned |
| P3 | 31-07/08 | Bias 检测 | schema 字段已存在，检测逻辑待实现 |

# 功能模块开发 TODO 清单 — 实际完成状态

> 更新时间：2026-06-26（按当前代码与验证状态同步）
> 排除范围：实盘账户与交易相关（BL-000 ~ BL-004 暂不处理）
> 数据源状态：31-03/04/05 已修复 — 停复牌/涨跌停/复权因子均使用东财+akshare 双源稳定

---

## Phase 31 — BL-105 数据质量与回测反偏差

### 31-01 数据质量标签体系
- [x] 31-01-01 DataQualityTag schema → `f8ded44`
- [x] 31-01-02 provider 层 quality tag → `f8ded44`
- [x] 31-01-03 API 响应携带 quality tag → `72a276a`
- [x] 31-01-04 Data Health 页面展示 → `2efdc18`

### 31-02 交易日历
- [x] 31-02-01 交易日历查询 → `70cc10d`
- [x] 31-02-02 回测校验交易日 → `c902808`
- [x] 31-02-03 API `/api/v1/market/calendar` → `70cc10d`

### 31-03 停复牌处理 → ✅ akshare + 东财双源 + 交易池推断
### 31-04 涨跌停处理 → ✅ akshare 涨跌停池(EM) + 东财 push2 降级

### 31-05 复权处理
- [x] 31-05-01 统一复权接口 → `07cd0d1`
- [x] 31-05-02 除权除息因子记录 — **已修复: 东财 + akshare hist 双源+ DuckDB 持久化** ✅ `590543f`
- [x] 31-05-03 回测默认前复权 → BacktestDataAssumption.adjustment
- [x] 31-05-04 复权数据 provenance → ResearchContext

### 31-06 ST/退市处理
- [x] 31-06-01 ST/*ST schema → BacktestDataAssumption.st_stock ✅ `def5145`
- [x] 31-06-02 退市股检测 → `_detect_st_delisted()` ✅ `def5145`
- [x] 31-06-03 回测标记退市 → data_assumption.delisted ✅ `def5145`

### 31-07 Survivorship Bias 检测
- [x] 31-07-01 检测功能 ✅ `22f2a71`
- [x] 31-07-02 data_assumption 字段 ✅
- [x] 31-07-03 回测结果页面展示 ✅ `27cfd60` (Strategy Hub 单策略结果展示 bias flags)

### 31-08 Look-ahead Bias 检测
- [x] 31-08-01 检测功能 ✅ `22f2a71`
- [x] 31-08-02 data_assumption 字段 ✅
- [x] 31-08-03 回测结果页面展示 ✅ `27cfd60` (Strategy Hub 单策略结果展示 bias flags)

### 31-09 数据质量分级与 Provenance ✅ 全部完成

### 31-10 回测约束完善
- [x] 31-10-01 涨跌停不可成交 → `_is_at_price_limit()` ✅ `3a14b4c`
- [x] 31-10-02 停牌不可成交 → `_is_suspended()` ✅ `3a14b4c`
- [x] 31-10-03 T+1 结算约束 → SettlementConstraint
- [x] 31-10-04 成交量容量约束 → `983022c`
- [x] 31-10-05 滑点可配置 → AStockFeeConfig + slippage_bps

---

## Phase 32 — BL-100 Strategy Lab 模块整合

- [x] 32-01 策略注册 ✅
- [x] 32-02 BacktestResult schema (含 benchmark) ✅ `5ef7467`
- [x] 32-02-04 交易明细约束标记 ✅ `3a14b4c` + `def5145`
- [x] 32-03 OptimizeResult schema ✅ `3c7b1a3`
- [x] 32-04 Strategy Hub 整合（含优化 tab）✅ `65ec50f`

---

## Phase 33 — BL-100A AI Research Center

- [x] 33-01 ResearchTask schema（含多标的）✅ `29920da`
- [x] 33-02 ResearchAudit schema ✅
- [x] 33-03 AI 页面统一上下文 ✅ `4a29f13`
- [x] 33-04 Advisory-Only 强制 ✅
- [x] 33-05 降级状态 UI 标识 ✅ `4a29f13`
- [x] 33-06 报告中心检索/复查/对比 ✅ `4a29f13`

---

## Phase 34 — Market Leaders
- [x] `/market_leaders` 单入口已落地
- [x] 顶层 sidebar 已收敛为单一 Market Leaders 入口
- [x] 旧页面 (`momentum_rotation` / `dragon_tiger` / `northbound` / `sectors` / `momentum_dashboard`) 带 legacy_redirect banner 指向 /market_leaders
- [x] market_leaders.html 内部 iframe tab 切换 5 个子板块

---

## Phase 35 — Trading Execution
- [x] order / fill / position / reconciliation schema 已落地
- [x] `routes_trade.py`、`trading.html`、PaperTrader / RiskGate 接线已落地
- [x] API 回归已恢复：`tests/test_astock_api.py` -> `47 passed`
- [ ] 真实券商回报 reconciliation 与 `qmt/orders` 真实语义未闭环

---

## Phase 36 — Portfolio Risk & Attribution
- [x] 36-01 Schema 拆分 ✅ `fd5459a`
- [x] 36-02 Portfolio 页面 ✅ `22f2a71`

---

## Phase 37 — Ops & Audit
- [x] 37-01 SSE TaskRun 标准化 ✅ `3057979`
- [x] 37-02 Ops Audit 页面 ✅ `22f2a71`

---

## Phase 38 — Product Navigation Cleanup
- [x] 38-01 Navigation 清理 → 7 模块 sidebar ✅ `52718f1`
- [x] 38-02~10 文档同步 — 已消除数字口径漂移: API modules 14→16, handlers 57→62, 版本号一致 ✅

---

## 当前验证摘要

- `Phase 31 + Phase 33-38` 相关 schema/阶段测试：`python3 -m pytest tests/test_astock_phase31.py tests/test_astock_phases_33_38.py -q` -> `26 passed`
- 全量文件基线：覆盖 `63` 个测试文件，共 `1033` tests collected
- 当前完整结果：`1019 passed, 14 skipped, 0 failed`
- Git：`xg_dev` 与 `origin/xg_dev` 同步；当前未提交修改仅 `.hermes/dev-loop.yaml`
- 验证环境：仓库 `.venv` 已失效，`./.venv/bin/python3.10` 不存在；当前使用系统 `Python 3.13.9`

# Roadmap

当前季度计划。详细 backlog 见 `BACKLOG.md`。

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
| ✅ done | Web
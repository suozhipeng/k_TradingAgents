# A 股项目风险登记表

| 更新时间：2026-07-08（Phase 34-39 风险状态已更新 ✅） |

本文用于从项目经理视角持续跟踪 TradingAgents-Astock 核心功能开发风险。本文只覆盖当前纳入范围内的金融软件核心功能风险，不展开安全与隐私、SLA 与故障分级、用户角色/RBAC。

## 1. 风险等级

| 字段 | 取值 | 说明 |
|---|---|---|
| 影响 | `H` / `M` / `L` | 对交易安全、数据可信、交付计划或用户误导的影响 |
| 概率 | `H` / `M` / `L` | 在后续 Phase 30-39 中发生的可能性 |
| 状态 | `open` / `mitigating` / `accepted` / `closed` | 当前处理状态 |

## 2. 风险台账

| ID | 风险 | 类型 | 影响 | 概率 | 缓解措施 | 关联文档 | 状态 |
|---|---|---|---|---|---|---|---|
| R-001 | paper / managed / live-ready 能力边界被用户误解 | 交易 | H | M | 所有交易相关 API 和页面必须标注能力等级，live-ready 前必须通过 checklist | `01-arch/API.md`, `03-ops/live-trading.md`, `03-ops/compliance.md` | mitigating（Phase 30 已补能力定义 + Phase 35 done-with-exclusions） |
| R-002 | QMT 订单、成交、撤单、拒单和券商回报 reconciliation 未闭环 | 交易 | H | M | Phase 30/35 先补订单生命周期、reconciliation、风控前置门和审计引用；真实券商 reconciliation 明确 P3 暂不处理 | `BACKLOG.md`, `04-dev/traceability-matrix.md`, `../phases/phase-35-trading-execution-control.md` | accepted（P3 暂不处理，产品定位非实盘） |
| R-003 | 回测结果存在 look-ahead、survivorship、停牌/涨跌停成交假设不清 | 回测 | H | M | Phase 31 已补数据假设、反偏差状态和回测可比性标记，后续持续维护 | `03-ops/data-sources.md`, `04-dev/test-plan.md` | mitigating（Phase 31 已完成，需持续维护） |
| R-004 | 数据源 freshness、fallback、quality 不透明导致 AI/回测/交易误判 | 数据 | H | M | Phase 31 已补 data quality tag、freshness/quality/fallback 标记 | `03-ops/data-sources.md` | mitigating（Phase 31 已完成，需持续维护） |
| R-005 | AI 输出缺少模型、prompt、输入快照和引用，无法复查 | AI | M | M | Phase 33 已统一 ResearchTask / ResearchAudit，AI 输出默认 advisory-only | `03-ops/compliance.md` | mitigating（Phase 33 已完成，需持续维护） |
| R-006 | Strategy Lab 整合时策略 registry、API、WebUI、优化器注册点漂移 | 策略 | M | H | Phase 32 已完成 Strategy Lab 统一入口 + BacktestResult schema + optimizer；强制遵守策略开发规范 | `02-guide/strategy-dev.md`, `04-dev/test-plan.md` | closed（Phase 32 完成整合） |
| R-007 | WebUI 页面多入口、多语义导致用户心智混乱 | UI | M | H | Phase 38 已完成 7 模块顶层导航收敛 + 旧入口 redirect + deprecation banner | `02-guide/USER_MANUAL.md` | closed（Phase 38 完成导航收敛） |
| R-008 | DuckDB/cache/schema 变化破坏历史回测、报告或页面兼容 | 数据迁移 | M | M | schema 变化必须补迁移、校验、cache 重建和回滚说明 | `04-dev/PRD.md`, `BACKLOG.md` | open（数据库模块 v1.0 已内置迁移引擎） |
| R-009 | Phase 文档与真实代码状态漂移，导致后续开发依据不可靠 | 项目管理 | M | M | 已完成多次文档批量同步，当前状态已对齐；后续 phase 变更后需同步维护 | `../README.md`, `04-dev/traceability-matrix.md` | closed（文档已对齐，后续维护模式下持续） |
| R-010 | 原 TradingAgents core 被误改，破坏底层 AI 分析能力 | 架构 | H | L | 保留原 core，新增 A 股能力只改后来新增模块，必要兼容修复需 ADR 记录 | `01-arch/ADR.md` | open |

## 3. 风险更新规则

- 每个 Phase 开始前必须检查本表是否有相关 open 风险。
- 每个 Phase 完成后必须更新风险状态，不能只在 phase 文档中分散描述。
- 新增高影响风险必须分配 `R-*` 编号，并关联需求 ID 或 phase。
- 风险状态变为 `closed` 时必须有测试、文档或实现证据。
- 如果风险属于安全与隐私、SLA 与故障分级、用户角色/RBAC，只登记为范围外触发条件，不进入当前核心功能开发。

## 4. Phase 30-39 重点风险映射

| Phase | 重点风险 |
|---|---|
| Phase 30 Live Trading Readiness | R-001, R-002 |
| Phase 31 Data Quality & Bias Control | R-003, R-004, R-008 |
| Phase 32 Strategy Lab | R-006, R-008 |
| Phase 33 AI Research Center | R-005, R-010 |
| Phase 34 Market Leaders | R-004, R-007 |
| Phase 35 Trading & Execution | R-001, R-002, R-008 |
| Phase 36 Portfolio Risk & Attribution | R-003, R-004 |
| Phase 37 Ops & Audit | R-005, R-009 |
| Phase 38 Product Navigation Cleanup | R-007, R-009 |
| Phase 39 End-to-End UAT | R-009 |

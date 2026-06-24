# TradingAgents-Astock 文档入口

| 更新时间：2026-06-23 |

本文是 `docs/` 目录入口，用于减少重复文档和过时入口。

## 当前有效入口

| 目的 | 文档 |
|---|---|
| 当前事实基线 | `docs/ASTOCK_CURRENT_STATUS.md` |
| 总需求和范围 | `docs/ASTOCK_REQUIREMENTS.md` |
| 产品需求 | `docs/ASTOCK_PRD.md` |
| 技术模块拆解 | `docs/ASTOCK_TECH_REQUIREMENTS.md` |
| 后续执行队列 | `docs/ASTOCK_BACKLOG.md` |
| 专业缺口、代码边界、WebUI 重构设计 | `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` |
| 金融产品优化路线图 | `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` |
| 开发进度与 5 分钟任务拆解 | `docs/ASTOCK_DEVELOPMENT_PROGRESS_AND_5MIN_PLAN.md` |
| Hermes 可执行任务包 | `docs/ASTOCK_HERMES_EXECUTION_TASK_PACKS.md` |
| 需求追踪矩阵 | `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md` |
| 项目风险登记表 | `docs/ASTOCK_PROJECT_RISK_REGISTER.md` |
| 架构决策记录 ADR | `docs/ASTOCK_ARCHITECTURE_DECISION_RECORDS.md` |
| 产品指标与运维需求 | `docs/ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md` |
| API 契约 | `docs/ASTOCK_API_CONTRACTS.md` |
| 后台 API 文档 | `docs/ASTOCK_BACKEND_API_REFERENCE.md` |
| 数据字典与血缘 | `docs/ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md` |
| 数据迁移与升级手册 | `docs/ASTOCK_DATA_MIGRATION_AND_UPGRADE.md` |
| 数据源授权与使用边界 | `docs/ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md` |
| AI 模型治理 | `docs/ASTOCK_MODEL_GOVERNANCE.md` |
| 实盘运行手册 | `docs/ASTOCK_LIVE_TRADING_RUNBOOK.md` |
| 核心功能部署与环境 | `docs/ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md` |
| 测试与验收计划 | `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md` |
| 发布与变更管理 | `docs/ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md` |
| 风险披露与合规边界 | `docs/ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md` |
| WebUI 产品规范 | `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md` |
| WebUI 页面级验收清单 | `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md` |
| 文档范围登记 | `docs/ASTOCK_DOCUMENT_SCOPE_REGISTER.md` |
| 策略开发规范 | `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` |
| live research 环境配置 | `docs/ASTOCK_LIVE_RESEARCH_SETUP.md` |
| phase 归档索引 | `docs/phases/README.md` |
| Hermes / Codex / DeepSeek 协作流程 | `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` |
| Hermes skill 分派规则 | `docs/HERMES_SKILLS_PLAYBOOK.md` |
| Hermes 持久化模板 | `docs/hermes/README.md` |
| live provider 验证溯源 | `docs/verification_provenance/README.md` |

## 文档维护规则

- 当前状态只写入 `ASTOCK_CURRENT_STATUS.md`，不要散落到旧 phase 草稿。
- 新需求先写入 `ASTOCK_REQUIREMENTS.md` 或 `ASTOCK_BACKLOG.md`。
- 面向后续开发的产品优化拆解写入 `ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md`。
- 后台/前台开发进度、API、真实数据源、测试验收和 5 分钟任务拆解写入 `ASTOCK_DEVELOPMENT_PROGRESS_AND_5MIN_PLAN.md`。
- Hermes 可直接分派的任务 brief、允许范围、测试和回填要求写入 `ASTOCK_HERMES_EXECUTION_TASK_PACKS.md`。
- 需求到模块、测试、phase 的映射写入 `ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`。
- 项目级技术、数据、交易、AI、UI、迁移风险写入 `ASTOCK_PROJECT_RISK_REGISTER.md`。
- 重大架构或产品边界决策写入 `ASTOCK_ARCHITECTURE_DECISION_RECORDS.md`。
- 产品成功指标、运行指标、告警和 Ops 需求写入 `ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md`。
- 新增或修改 API schema、错误码、能力等级时，必须同步 `ASTOCK_API_CONTRACTS.md`。
- 新增、删除或调整后台 endpoint、数据源、能力等级、测试验收时，必须同步 `ASTOCK_BACKEND_API_REFERENCE.md`。
- 新增或修改 provider、store 字段、数据质量标签或血缘链路时，必须同步 `ASTOCK_DATA_DICTIONARY_AND_LINEAGE.md`。
- 新增或修改 DuckDB、cache、schema、报告归档或回测结果结构时，必须同步 `ASTOCK_DATA_MIGRATION_AND_UPGRADE.md`。
- 新增或修改数据源时，必须同步 `ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md` 中的来源、用途和使用边界。
- 新增或修改 AI provider、prompt、模型输出 schema 时，必须同步 `ASTOCK_MODEL_GOVERNANCE.md`。
- 声明 `managed` 或 `live-ready` 能力前，必须同步 `ASTOCK_LIVE_TRADING_RUNBOOK.md` 和 `ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md`。
- 修改核心功能启动、依赖、环境变量或健康检查时，必须同步 `ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md`。
- 每个 phase 的测试命令、验收门槛和发布阻断条件写入 `ASTOCK_TEST_ACCEPTANCE_PLAN.md`。
- API/data/AI/trading/UI 任一兼容性变化，必须同步 `ASTOCK_RELEASE_AND_CHANGE_MANAGEMENT.md`。
- 代码和 UI 边界先写入 `ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`，再进入 phase 实施。
- WebUI 页面状态、能力标签、顶层导航和旧入口迁移写入 `ASTOCK_WEBUI_PRODUCT_SPEC.md`。
- 每个 WebUI 页面开发或重构完成后，必须按 `ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md` 补输入、输出、状态、错误态和截图证据。
- 当前暂不纳入的外围模块只记录在 `ASTOCK_DOCUMENT_SCOPE_REGISTER.md`，不展开成需求模块。
- 新增策略或重构 Strategy Lab 必须同步 `ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`。
- phase 证据只写入 `docs/phases/phase-XX-*.md`。
- Hermes 运行态文件放 `.hermes/`；可复用模板才放 `docs/hermes/`。
- live provider 历史验证证据放 `docs/verification_provenance/`，只追加真实验证结果。
- 不再新增 `ASTOCK_PHASE*.md` 根目录阶段文件；阶段资料必须进 `docs/phases/`。
- 不再保留独立的临时评审报告；专业评审内容统一进入边界设计或当前状态摘要。

## 已合并或移除的旧入口

以下根目录文档已合并进对应 phase 或总控文档：

- `ASTOCK_PHASE4_GRAPH_WIRING.md` -> `docs/phases/phase-04-research-graph.md`
- `ASTOCK_PHASE5_RUNTIME_VERIFICATION.md` -> `docs/phases/phase-05-research-runtime.md`
- `ASTOCK_PHASE6_ENTRY_DISPATCH.md` -> `docs/phases/phase-06-entry-dispatch.md`
- `ASTOCK_DISPLAY_REPORT_SCHEMA.md` -> `docs/phases/phase-07-schema-cli.md`
- `ASTOCK_CLI_RENDERING.md` -> `docs/phases/phase-07-schema-cli.md`
- `ASTOCK_UI_READONLY.md` -> `docs/phases/phase-08-readonly-viewer.md`
- `ASTOCK_MULTIMARKET_VIEWER.md` -> `docs/phases/phase-08-readonly-viewer.md`
- `ASTOCK_PROFESSIONAL_GAP_ANALYSIS.md` -> `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`
- `HERMES_PROJECT_REVIEW.md` -> `docs/ASTOCK_CURRENT_STATUS.md` and `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`

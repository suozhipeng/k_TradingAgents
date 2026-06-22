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
- 代码和 UI 边界先写入 `ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`，再进入 phase 实施。
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

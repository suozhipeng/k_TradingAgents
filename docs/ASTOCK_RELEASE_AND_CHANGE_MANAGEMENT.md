# A 股发布与变更管理

| 更新时间：2026-06-23 |

本文定义 TradingAgents-Astock 核心功能开发中的变更、版本、兼容和回滚要求。它只面向代码与文档交付流程，不定义 SLA、故障等级、用户权限或企业发布流程。

## 1. 变更分类

| 类型 | 示例 | 必需文档 |
|---|---|---|
| docs-only | 需求、路线图、phase 归档 | README、相关需求文档 |
| API change | endpoint、response schema、错误码 | API 契约、测试验收 |
| data change | provider、store schema、数据质量标签 | 数据字典与血缘 |
| AI change | prompt、模型、报告 schema | 模型治理、风险披露 |
| strategy change | 策略、参数、优化器、回测结果 | 策略开发规范、测试验收 |
| trading change | 订单、风控、QMT、runbook | 实盘运行手册、风险披露 |
| UI change | 导航、页面、状态、错误态 | UI 规范、WebUI 边界设计 |

## 2. 版本记录

每个可交付变更应记录：

- phase 编号。
- 需求 ID。
- commit SHA。
- 影响模块。
- API/store/UI schema 是否变化。
- 是否影响原 TradingAgents core。
- 测试命令和结果。
- 回滚方式。

## 3. 兼容策略

后续开发应遵守：

- 不破坏原 TradingAgents core 的 AI 分析能力。
- legacy payload 兼容必须有测试或明确迁移说明。
- API schema 变更必须说明新增、废弃、兼容字段。
- store schema 变更必须说明迁移和回滚。
- WebUI 入口迁移必须有旧入口跳转或降级策略。

## 4. 合并门槛

核心功能变更合并前至少确认：

- `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md` 已更新。
- `docs/phases/phase-XX-*.md` 已准备或更新。
- API/data/AI/trading/UI 相关文档已同步。
- `docs/ASTOCK_TEST_ACCEPTANCE_PLAN.md` 对应测试已执行。
- 已知风险和回滚路径已记录。

## 5. 回滚要求

每个非 docs-only 变更必须说明：

- 可以回滚到哪个 commit 或 feature flag 状态。
- 回滚后是否影响数据。
- 是否需要清理缓存或重建 store。
- 是否需要停用 provider、LLM、QMT 或 WebUI 入口。

## 6. 验收要求

每个 phase 完成时必须能回答：

- 本次变更属于哪类。
- 哪些需求 ID 被实现或推进。
- 哪些文档被同步。
- 哪些测试证明未破坏既有能力。
- 如果失败，如何回滚。

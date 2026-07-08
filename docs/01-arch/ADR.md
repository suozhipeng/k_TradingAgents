# A 股架构决策记录 ADR

| 更新时间：2026-07-08 |

本文记录 TradingAgents-Astock 后续开发中的关键架构和产品决策，避免在 Phase 30-39 中反复争议。本文只记录当前核心功能范围内的决策，不展开安全与隐私、SLA 与故障分级、用户角色/RBAC。

## 1. ADR 状态

| 状态 | 含义 |
|---|---|
| `accepted` | 已采纳，后续开发默认遵守 |
| `proposed` | 已提出，尚未执行 |
| `superseded` | 已被新 ADR 替代 |
| `rejected` | 明确不采用 |

## 2. 决策记录

### ADR-001 保留原 TradingAgents core

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | 原项目底层 AI 多 Agent 分析能力是项目核心资产 |
| 决策 | 保留原 TradingAgents core，A 股能力优先在新增 astock/provider/WebUI/strategy/execution 模块扩展 |
| 影响 | 后续改动必须先判断是否触及 core；触及时只做兼容性修复并补测试 |
| 关联文档 | `03-ops/deployment.md`, `03-ops/compliance.md` |

### ADR-002 Flask WebUI 和 Streamlit viewer 不强行合并

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | Flask WebUI 承载产品页面，Streamlit viewer 承载只读运行时查看 |
| 决策 | 保持两者职责分离，不在当前核心功能阶段强行合并成单前端 |
| 影响 | 后续 WebUI 重构优先收敛 Flask 产品导航；Streamlit 继续作为只读 viewer |
| 关联文档 | `02-guide/USER_MANUAL.md`, `03-ops/compliance.md` |

### ADR-003 所有交易能力必须标注 capability

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | 当前系统具备 research、paper、managed 和 live-ready 雏形，容易被误解为自动实盘 |
| 决策 | API、页面、报告和 phase 证据必须标注 `research` / `paper` / `managed` / `live-ready` |
| 影响 | live-ready 声明必须通过准入 checklist；mock/paper 不得被描述为真实账户或真实订单 |
| 关联文档 | `01-arch/API.md`, `03-ops/live-trading.md`, `03-ops/compliance.md` |

### ADR-004 Strategy Lab 收敛策略、回测、优化、绩效和对比

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | 策略、回测、优化、绩效、对比、动量轮动已存在但入口分散 |
| 决策 | 后续统一为 Strategy Lab，使用统一 strategy registry、参数 schema、回测结果 schema 和优化结果 schema |
| 影响 | 新增策略必须遵守策略开发规范；动量轮动可保留 standalone 组合策略模式 |
| 关联文档 | `BACKLOG.md`, `02-guide/strategy-dev.md` |

### ADR-005 AI Research Center 保持 advisory-only

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | AI Agent、research 页面和报告中心需要收敛，但 AI 输出存在幻觉和解释风险 |
| 决策 | AI Research Center 输出默认 advisory-only，不直接触发真实订单 |
| 影响 | 必须记录模型、prompt、输入快照和引用；LLM 不可用时 fail closed 或 degraded |
| 关联文档 | `03-ops/compliance.md` |

### ADR-006 Market Leaders 顶层最多一个入口

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | 龙头、板块、资金、动量轮动、龙虎榜、北向页面分散 |
| 决策 | 顶层最多保留一个 Market Leaders / 龙头决策入口，内部用顶部 tab 切换 |
| 影响 | 旧入口需要迁移、跳转或降级提示；候选池必须展示来源、刷新时间和入池/出池理由 |
| 关联文档 | `02-guide/USER_MANUAL.md` |

### ADR-007 数据 schema 变化必须先有迁移策略

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | DuckDB、cache、回测结果、报告归档、AI audit 和交易状态都会影响历史可复查性 |
| 决策 | schema 变化必须先更新数据迁移与升级手册，并说明校验和回滚 |
| 影响 | 不能只改代码或页面；必须补迁移前后 schema、cache 重建、API/WebUI 回归 |
| 关联文档 | `04-dev/PRD.md`, `BACKLOG.md`, `database_module_whitepaper.md` |

### ADR-008 Phase 证据是交付事实来源

| 字段 | 内容 |
|---|---|
| 状态 | `accepted` |
| 背景 | 项目经历多个 phase，需求、状态和实现容易漂移 |
| 决策 | 每个 phase 的真实交付证据以 `phases/phase-XX-*.md` 为准，当前状态集中写入 `phases/README.md` |
| 影响 | 后续开发必须补需求 ID、scope、测试、风险、下一入口条件和 commit SHA |
| 关联文档 | `phases/README.md`, `04-dev/traceability-matrix.md` |

## 3. 新 ADR 规则

- 涉及 core、API 契约、数据 schema、交易能力等级、WebUI 顶层导航、AI 输出边界的重大变更必须新增 ADR。
- ADR 不替代需求文档；需求仍进入 `04-dev/PRD.md`、`BACKLOG.md` 和追踪矩阵。
- 如果新决策推翻旧决策，旧 ADR 状态改为 `superseded`，并引用新的 ADR 编号。
- ADR 不能隐式引入安全与隐私、SLA 与故障分级、用户角色/RBAC。

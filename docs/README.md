# TradingAgents — AStock Pro 文档体系

> 每个主题**只有一个权威文档**。版本历史见 [../CHANGELOG.md](../CHANGELOG.md)（已合并 AStock Pro 变更）。

## 当前状态

| 当前本地状态以 [`phase-archive.md`](phase-archive.md)、[`CHANGELOG.md`](CHANGELOG.md) 和 [`04-development.md`](04-development.md) 为准 |
- 2026-07-15 本地离线全仓验证基线：`ASTOCK_TESTING=1 pytest tests/ -q --tb=short` → `1178 passed, 10 skipped`；AStock 专项 `tests/test_astock*.py` → `739 passed, 9 skipped`；`TEST_PYDANTIC_BT=1` gate 单测已补跑通过。
- 2026-07-08 已完成真实 live 验收：DeepSeek live API `1 passed`，live provider `7 passed, 1 skipped`，端到端 `live_research` pipeline `VERIFICATION PASSED`
- 当前唯一未闭环 live 依赖为 `ASTOCK_IWENCAI_COOKIE`；未配置时 Iwencai 用例按设计跳过
- 默认产品范围为 Research-only：投研分析 + 策略回测 + 市场盯盘；执行页面与 `/api/v1/trade/*`、`/paper/*`、`/qmt/*`、`/portfolio/*` API 默认不可用。`ASTOCK_RESEARCH_ONLY=false` 仅保留兼容模式；**不接入真实券商**。
- 本地正式版（仅分析与回测）的问题整改、任务拆分和验收结果见 [`LOCAL_RELEASE_READINESS_PLAN.md`](LOCAL_RELEASE_READINESS_PLAN.md)。React/Vite 保留为非发布开发前端，不作为默认入口。
- 行情响应统一包含 `source`、`as_of`、`age_seconds`、`is_mock`、`is_stale`，UI 与调用方必须据此区分实时、缓存、降级与模拟数据。
- Jinja2 WebUI 已收敛为 22 个非共享页面模板与 2 个共享模板；旧盯盘 URL 以 `302` 跳转到 Market Leaders，唯一支持的图表入口为 KC Chart。

## 📂 文档结构

```
docs/
├── README.md              ← 你在这里
├── CHANGELOG.md           ← 版本白皮书
├── BACKLOG.md             ← 待完成任务清单
├── LOCAL_RELEASE_READINESS_PLAN.md ← 本地正式版发布就绪计划（仅分析与回测）
│
├── 01-architecture.md         ← 架构设计（API + ADR 整合）
├── 02-user-guide.md         ← 上手与使用（用户手册 + 快速入门 + 术语表 + 策略开发）
├── 03-operations.md         ← 运维与合规（部署 + 实盘 + 研究 + 数据源 + 合规 + 风险）
├── 04-development.md        ← 需求与开发（PRD + 新功能 + 测试 + 追踪）
│

│   ├── README.md          ← 阶段索引
│   ├── TEMPLATE.md        ← 阶段模板
│   └── phase-archive.md   ← Phase 31-39 交付总结
├── database_module_whitepaper.md ← 数据库模块白皮书
├── full_function_documentation.md ← 全功能文档
```

## 🧭 快速导航

### 🌐 全局概览

| 我想... | 打开... |
|---------|---------|
| 看当前状态 | [phase-archive.md](phase-archive.md) |
| 看当前计划 | [BACKLOG.md](BACKLOG.md) |
| 看本地正式版发布计划 | [LOCAL_RELEASE_READINESS_PLAN.md](LOCAL_RELEASE_READINESS_PLAN.md) |
| 查版本变更 | [../CHANGELOG.md](../CHANGELOG.md) |
| 全功能概览 | [full_function_documentation.md](full_function_documentation.md) |

### 🏗️ 架构设计

| 我想... | 打开... |
|---------|---------|
| 查看 API 端点 + 架构决策 | [01-architecture.md](01-architecture.md) |

### 📖 上手与使用

| 我想... | 打开... |
|---------|---------|
| 启动服务 / 用户手册 / 术语表 / 策略开发 | [02-user-guide.md](02-user-guide.md) |

### 🔧 运维与合规

| 我想... | 打开... |
|---------|---------|
| 部署 / 实盘 / 研究 / 数据源 / 合规 / 风险 | [03-operations.md](03-operations.md) |

### 🛠️ 需求与开发

| 我想... | 打开... |
|---------|---------|
| PRD / 新功能 / 测试计划 / 需求追踪 | [04-development.md](04-development.md) |

### 🗄️ 数据库

| 我想... | 打开... |
|---------|---------|
| 数据库架构 | [database_module_whitepaper.md](database_module_whitepaper.md) |

### 📋 阶段文档 (phases)

| 我想... | 打开... |
|---------|---------|
| 阶段索引 | [phase-archive.md](phase-archive.md) |
| 阶段模板 | [phase-template.md](phase-template.md) |
| Phase 31-39 交付总结 | [phase-archive.md](phase-archive.md) |

## ⚠️ 已知文档缺口

| 代码模块 | 状态 |
|---------|------|
| `tradingagents/astock/schemas/` (7 个 Pydantic 模型) | 未记录 — API 层面的 schema 已在 `01-architecture.md` §5 覆盖，内部模型属于实现细节 |

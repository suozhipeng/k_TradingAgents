# TradingAgents — AStock Pro 文档体系

> 每个主题**只有一个权威文档**。版本历史见 [../CHANGELOG.md](../CHANGELOG.md)（已合并 AStock Pro 变更）。

## 当前状态

| 当前本地状态以 [`phases/README.md`](phases/README.md) 和 [`04-development.md`](04-development.md) 为准 |
- 2026-07-08 本地离线验证基线：`1082 passed, 10 skipped`
- 2026-07-08 已完成真实 live 验收：DeepSeek live API `1 passed`，live provider `7 passed, 1 skipped`，端到端 `live_research` pipeline `VERIFICATION PASSED`
- 当前唯一未闭环 live 依赖为 `ASTOCK_IWENCAI_COOKIE`；未配置时 Iwencai 用例按设计跳过
- 当前产品范围明确为：投研分析 + 回测 + 模拟盘 + mock/read-only QMT managed 试运行；**不接入真实券商**

## 📂 文档结构

```
docs/
├── README.md              ← 你在这里
├── CHANGELOG.md           ← 版本白皮书（已归档至 _archived/，合并入根 CHANGELOG.md）
├── BACKLOG.md             ← 待完成任务清单
│
├── 01-architecture.md         ← 架构设计（API + ADR 整合）
├── 02-user-guide.md         ← 上手与使用（用户手册 + 快速入门 + 术语表 + 策略开发）
├── 03-operations.md         ← 运维与合规（部署 + 实盘 + 研究 + 数据源 + 合规 + 风险）
├── 04-development.md        ← 需求与开发（PRD + 新功能 + 测试 + 追踪）
│
├── phases/                ← 阶段设计文档
│   ├── README.md          ← 阶段索引
│   ├── TEMPLATE.md        ← 阶段模板
│   └── phase-summary.md   ← Phase 31-39 交付总结
├── database_module_whitepaper.md ← 数据库模块白皮书
├── full_function_documentation.md ← 全功能文档
└── _archived/             ← 历史归档
```

## 🧭 快速导航

### 🌐 全局概览

| 我想... | 打开... |
|---------|---------|
| 看当前状态 | [phases/README.md](phases/README.md) |
| 看当前计划 | [BACKLOG.md](BACKLOG.md) |
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
| 阶段索引 | [phases/README.md](phases/README.md) |
| 阶段模板 | [phases/TEMPLATE.md](phases/TEMPLATE.md) |
| Phase 31-39 交付总结 | [phases/phase-summary.md](phases/phase-summary.md) |

## ⚠️ 已知文档缺口

| 代码模块 | 状态 |
|---------|------|
| `tradingagents/astock/schemas/` (7 个 Pydantic 模型) | 未记录 — API 层面的 schema 已在 `01-architecture.md` §5 覆盖，内部模型属于实现细节 |


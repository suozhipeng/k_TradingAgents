# TradingAgents — AStock Pro 文档体系

> 每个主题**只有一个权威文档**。版本历史见 [../CHANGELOG.md](../CHANGELOG.md)（已合并 AStock Pro 变更）。

## 当前状态

- 当前本地状态以 [`phases/README.md`](phases/README.md) 和 [`04-dev/traceability-matrix.md`](04-dev/traceability-matrix.md) 为准
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
├── 01-arch/               ← 架构设计
│   ├── API.md             ← API 端点参考
│   └── ADR.md             ← 架构决策记录
│
├── 02-guide/              ← 上手与使用
│   ├── QUICK_START.md     ← 快速开始
│   ├── USER_MANUAL.md     ← 用户手册
│   ├── GLOSSARY.md        ← 术语表
│   └── strategy-dev.md    ← 策略开发规范
│
├── 03-ops/                ← 运维与合规
│   ├── deployment.md      ← 部署 + 产品指标与监控
│   ├── live-trading.md    ← 实盘运行
│   ├── live-research.md   ← 研究环境
│   ├── data-sources.md    ← 数据源授权与字典
│   ├── compliance.md      ← 风险披露 + 隐私声明
│   └── risk-register.md   ← 项目风险登记
│
├── 04-dev/                ← 需求与开发
│   ├── PRD.md             ← 产品需求（合并 PRD + 需求 + 技术需求）
│   ├── new-features-requirements.md ← 新增功能需求文档
│   ├── test-plan.md       ← 测试验收计划
│   └── traceability-matrix.md ← 需求追踪矩阵
│
├── phases/                ← 阶段设计文档
│   ├── README.md          ← 阶段索引
│   ├── TEMPLATE.md        ← 阶段模板
│   ├── phase-30 ~ 39      ← 活跃阶段文档（phase-30 已归档至 _archived/）
│
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

### 🏗️ 架构设计 (01-arch)

| 我想... | 打开... |
|---------|---------|
| 查看 API 端点 | [01-arch/API.md](01-arch/API.md) |
| 查看架构决策 | [01-arch/ADR.md](01-arch/ADR.md) |

### 📖 上手与使用 (02-guide)

| 我想... | 打开... |
|---------|---------|
| 启动服务 | [02-guide/QUICK_START.md](02-guide/QUICK_START.md) |
| 阅读用户手册 | [02-guide/USER_MANUAL.md](02-guide/USER_MANUAL.md) |
| 查阅术语 | [02-guide/GLOSSARY.md](02-guide/GLOSSARY.md) |
| 开发策略 | [02-guide/strategy-dev.md](02-guide/strategy-dev.md) |

### 🔧 运维与合规 (03-ops)

| 我想... | 打开... |
|---------|---------|
| 部署上线 | [03-ops/deployment.md](03-ops/deployment.md) |
| 实盘交易 | [03-ops/live-trading.md](03-ops/live-trading.md) |
| 配置研究环境 | [03-ops/live-research.md](03-ops/live-research.md) |
| 数据源与字典 | [03-ops/data-sources.md](03-ops/data-sources.md) |
| 合规与隐私 | [03-ops/compliance.md](03-ops/compliance.md) |
| 项目风险登记 | [03-ops/risk-register.md](03-ops/risk-register.md) |

### 🛠️ 需求与开发 (04-dev)

| 我想... | 打开... |
|---------|---------|
| 了解产品功能 | [04-dev/PRD.md](04-dev/PRD.md) |
| 查看新增需求 | [04-dev/new-features-requirements.md](04-dev/new-features-requirements.md) |
| 查看测试计划 | [04-dev/test-plan.md](04-dev/test-plan.md) |
| 查看需求追踪 | [04-dev/traceability-matrix.md](04-dev/traceability-matrix.md) |

### 🗄️ 数据库

| 我想... | 打开... |
|---------|---------|
| 数据库架构 | [database_module_whitepaper.md](database_module_whitepaper.md) |

### 📋 阶段文档 (phases)

| 我想... | 打开... |
|---------|---------|
| 阶段索引 | [phases/README.md](phases/README.md) |
| 阶段模板 | [phases/TEMPLATE.md](phases/TEMPLATE.md) |
| Phase 30 Live Trading Readiness | _archived/phase-30-live-trading-readiness.md (已归档) |
| Phase 31 Data Quality & Bias | [phases/phase-31-data-quality-bias-control.md](phases/phase-31-data-quality-bias-control.md) |
| Phase 32 Strategy Lab | [phases/phase-32-strategy-lab-consolidation.md](phases/phase-32-strategy-lab-consolidation.md) |
| Phase 33 AI Research Center | [phases/phase-33-ai-research-center.md](phases/phase-33-ai-research-center.md) |
| Phase 34 Market Leaders | [phases/phase-34-market-leaders-entry.md](phases/phase-34-market-leaders-entry.md) |
| Phase 35 Trading & Execution | [phases/phase-35-trading-execution-control.md](phases/phase-35-trading-execution-control.md) |
| Phase 36 Portfolio Risk | [phases/phase-36-portfolio-risk-attribution.md](phases/phase-36-portfolio-risk-attribution.md) |
| Phase 37 Ops & Audit | [phases/phase-37-ops-audit-center.md](phases/phase-37-ops-audit-center.md) |
| Phase 38 Product Navigation | [phases/phase-38-product-navigation-cleanup.md](phases/phase-38-product-navigation-cleanup.md) |
| Phase 39 E2E UAT | [phases/phase-39-e2e-uat.md](phases/phase-39-e2e-uat.md) |

## ⚠️ 已知文档缺口

| 代码模块 | 状态 |
|---------|------|
| `tradingagents/astock/schemas/` (7 个 Pydantic 模型) | 未记录 — API 层面的 schema 已在 `01-arch/API.md` §5 覆盖，内部模型属于实现细节 |


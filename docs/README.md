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
│   ├── test-plan.md       ← 测试验收计划
│   └── traceability-matrix.md ← 需求追踪矩阵
│
├── phases/                ← 阶段设计文档
│   ├── README.md          ← 阶段索引
│   ├── TEMPLATE.md        ← 阶段模板
│   └── phase-30 ~ 39      ← 活跃阶段文档
│
├── database_module_whitepaper.md ← 数据库模块白皮书
├── full_function_documentation.md ← 全功能文档
└── _archived/             ← 历史归档
```

## 🧭 快速导航

| 我想... | 打开... |
|---------|---------|
| 看当前状态 | `phases/README.md` |
| 启动服务 | `02-guide/QUICK_START.md` |
| 查看 API | `01-arch/API.md` |
| 了解产品功能 | `04-dev/PRD.md` |
| 查版本变更 | `../CHANGELOG.md` |
| 看当前计划 | `BACKLOG.md` |
| 部署上线 | `03-ops/deployment.md` |
| 实盘交易 | `03-ops/live-trading.md` |
| 开发策略 | `02-guide/strategy-dev.md` |
| 数据库架构 | `database_module_whitepaper.md` |
| 全功能概览 | `full_function_documentation.md` |

## ⚠️ 已知文档缺口

| 代码模块 | 状态 |
|---------|------|
| `tradingagents/astock/schemas/` (7 个 Pydantic 模型) | 未记录 — API 层面的 schema 已在 `01-arch/API.md` §5 覆盖，内部模型属于实现细节 |

## 📚 旧文件名映射（已归档）

| 旧文件名 | 新位置 |
|---------|--------|
| `ASTOCK_PRD.md` | `04-dev/PRD.md` |
| `ASTOCK_API_CONTRACTS.md` | `01-arch/API.md` |
| `ASTOCK_ARCHITECTURE_DECISION_RECORDS.md` | `01-arch/ADR.md` |
| `ASTOCK_REQUIREMENTS.md` | `04-dev/PRD.md` |
| `ASTOCK_TECH_REQUIREMENTS.md` | `04-dev/PRD.md` |
| `ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md` | `04-dev/traceability-matrix.md` |
| `ASTOCK_TEST_ACCEPTANCE_PLAN.md` | `04-dev/test-plan.md` |
| `ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` | `02-guide/strategy-dev.md` |
| `ASTOCK_DEPLOYMENT_AND_ENVIRONMENT.md` | `03-ops/deployment.md` |
| `ASTOCK_LIVE_TRADING_RUNBOOK.md` | `03-ops/live-trading.md` |
| `ASTOCK_LIVE_RESEARCH_SETUP.md` | `03-ops/live-research.md` |
| `ASTOCK_DATA_SOURCE_LICENSE_AND_USAGE.md` | `03-ops/data-sources.md` |
| `ASTOCK_RISK_DISCLOSURE_AND_COMPLIANCE.md` | `03-ops/compliance.md` |
| `ASTOCK_PROJECT_RISK_REGISTER.md` | `03-ops/risk-register.md` |
| `ASTOCK_PRODUCT_METRICS_AND_OPS_REQUIREMENTS.md` | `03-ops/deployment.md` §8 |
| `ASTOCK_BACKLOG.md` | `BACKLOG.md` |
| `ASTOCK_CURRENT_STATUS.md` | `phases/README.md` |
| `ASTOCK_HERMES_EXECUTION_TASK_PACKS.md` | 已移除（AI 操作指令，非项目文档） |
| `ASTOCK_WEBUI_PRODUCT_SPEC.md` | `02-guide/USER_MANUAL.md` |

> 历史文档已归档至 `_archived/`。Hermes 协作文件（workflow/skills/templates）已移除——它们属于 AI 工具操作文档，不属于项目文档。

# TradingAgents — AStock Pro 文档

> 产品经理整理的文档体系。每个主题**只有一个权威文档**。

---

## 📂 文档结构

```
docs/
├── README.md              ← 你在这里
├── CHANGELOG.md           ← 版本日志
├── ROADMAP.md             ← 当前季度规划
├── BACKLOG.md             ← 待完成任务清单
│
├── 01-arch/               ← 架构设计
│   ├── API.md             ← API 端点参考（合并契约+引用）
│   └── ADR.md             ← 架构决策记录
│
├── 02-guide/              ← 上手与使用
│   ├── QUICK_START.md     ← 快速开始
│   ├── USER_MANUAL.md     ← 用户手册
│   ├── GLOSSARY.md        ← 术语表
│   └── strategy-dev.md    ← 策略开发规范
│
├── 03-ops/                ← 运维与合规
│   ├── deployment.md      ← 部署与环境
│   ├── live-trading.md    ← 实盘运行
│   ├── live-research.md   ← 研究环境
│   ├── data-sources.md    ← 数据源授权与字典
│   ├── compliance.md      ← 风险披露与合规
│   ├── risk-register.md   ← 项目风险登记
│   ├── ops-metrics.md     ← 产品指标与运维
│   └── privacy.md         ← 隐私声明
│
├── 04-dev/                ← 需求与开发
│   ├── PRD.md             ← 产品需求（合并PRD+需求+技术需求）
│   ├── test-plan.md       ← 测试验收计划
│   ├── traceability-matrix.md ← 需求追踪矩阵
│   └── hermes-tasks.md    ← Hermes 任务包归档
│
├── 05-phases/             ← 阶段设计文档（活跃中）
│   ├── phase-30*          ← 交易执行
│   ├── phase-31*          ← 数据质量
│   ├── phase-32*          ← 策略实验室
│   ├── phase-33*          ← AI 研究中心
│   ├── phase-34*          ← 市场领导看板
│   ├── phase-35*          ← 交易执行控制
│   ├── phase-36*          ← 组合风控
│   ├── phase-37*          ← 运维审计
│   ├── phase-38*          ← 导航清理
│   ├── phase-39*          ← E2E UAT
│   └── phase-web-*        ← Web 阶段
│
├── hermes/                ← Hermes 协作文档
├── verification/          ← 数据源验证
└── _archived/             ← 历史版本（可查）
```

---

## 🧭 快速导航

| 我想... | 打开... |
|---------|---------|
| 启动服务 | `02-guide/QUICK_START.md` |
| 查看 API | `01-arch/API.md` |
| 了解产品功能 | `04-dev/PRD.md` |
| 查最新变更 | `CHANGELOG.md` |
| 看当前计划 | `ROADMAP.md` |
| 部署上线 | `03-ops/deployment.md` |
| 实盘交易 | `03-ops/live-trading.md` |
| 开发策略 | `02-guide/strategy-dev.md` |

---

> 历史文档已归档至 `_archived/`。如需查阅，直接进入。

# A 股部署与运维文档

| 更新时间：2026-07-08 |

本文定义 TradingAgents-Astock 的环境、依赖、启动、健康检查、部署要求，以及产品指标与监控。本文只服务于研究、回测、模拟盘、受控执行和 WebUI 等核心功能。

## 1. 环境分层

| 环境 | 用途 | 允许能力 | 禁止事项 |
|---|---|---|---|
| local | 本地开发、单元测试、文档验证 | research、paper、mock managed | 声明 live-ready |
| test | 集成测试、WebUI/API slice、provider fixture | research、paper、guarded live provider | 无说明直连真实交易 |
| staging | 受控演练、QMT 联调、回归验收 | research、paper、managed dry-run | 自动实盘 |
| production-like | 真实使用前演练环境 | research、paper、managed，live-ready 需单独准入 | 未通过 checklist 的真实交易 |

## 2. 依赖清单

| 依赖 | 用途 | 生产级要求 |
|---|---|---|
| Python runtime | 后端、CLI、Agent runtime | 版本固定，可复现安装 |
| Flask WebUI | 产品页面和 API | 启动命令、端口、健康检查可记录 |
| PostgreSQL / ClickHouse | 生产级 OLTP + OLAP | Docker compose 部署，容器化 |
| DuckDB | 本地 OLAP 分析缓存 | 数据目录、备份、迁移边界明确 |
| akshare / mootdx / Tencent / EastMoney / Sina | A 股数据 provider | 记录来源、fallback、质量和授权边界 |
| LLM provider | AI Research | 记录模型、prompt、失败降级 |
| QMT | 受控执行 | 未通过准入前只允许 managed/dry-run 口径 |

## 3. 环境变量与配置

后续开发不得把配置散落在代码中，至少需要记录：

- 数据库路径和缓存目录。
- provider 开关和 fallback 顺序。
- LLM provider、模型名称和超时配置。
- QMT 连接参数和 managed mode 开关。
- WebUI host、port、debug mode。
- 测试环境标记和 live dependency guard。

本文不要求记录密钥值、账号、隐私字段或密钥轮换策略；这些属于暂不纳入的安全与隐私文档。

## 4. 启动顺序

标准启动流程应满足：

1. 检查 Python 环境和依赖版本。
2. 检查 DuckDB/cache 目录可读写。
3. 检查 provider 可用性，失败时标注 fallback 或 degraded。
4. 启动 Flask WebUI/API。
5. 需要时启动 Streamlit viewer。
6. 需要时启动 QMT managed/dry-run 联调。
7. 运行健康检查并记录结果。

## 5. 健康检查

生产级健康检查至少覆盖：

- WebUI/API 是否可访问。
- DuckDB/store 是否可读。
- provider 是否可用、是否 fallback。
- LLM 是否可用，失败时是否 fail closed。
- QMT 是否 connected / disconnected / dry-run。
- 最近一次数据刷新时间。
- 最近一次任务失败原因。

## 6. 核心数据恢复边界

当前项目应先定义以下备份恢复口径：

- DuckDB/cache 数据目录备份。
- 报告、回测结果、AI Research 结果归档。
- phase 文档和需求矩阵随 git 管理。
- 运行态任务和审计事件在 Phase 37 后统一进入 Ops/Audit。

本文不承诺恢复时间目标；恢复时间目标属于暂不纳入的 SLA 与故障分级。

## 7. 验收要求

部署相关 phase 必须提供：

- 环境类型。
- 启动命令。
- 必需依赖。
- 健康检查结果。
- 已知 degraded 项。
- 回滚或恢复路径。
- 不涉及安全与隐私、SLA、用户角色/RBAC 的说明。

### 验收证据（2026-06-26）

| 验收项 | 状态 | 证据 |
|--------|------|------|
| 环境分层定义 | ✅ 完成 | §1 明确定义 local/test/staging/production-like 四层及其允许/禁止能力 |
| 依赖清单完整 | ✅ 完成 | §2 列出 Python/Flask/Streamlit/DuckDB/provider/LLM/QMT 依赖及生产级要求 |
| 启动顺序文档化 | ✅ 完成 | §4 从环境检查→provider 可用性→Flask→Streamlit→QMT 共 7 步 |
| 健康检查覆盖范围 | ✅ 完成 | §5 覆盖 WebUI/DuckDB/provider/LLM/QMT/数据刷新/任务失败 7 项 |
| 数据恢复边界明确 | ✅ 完成 | §6 DuckDB/cache/报告/任务/审计的备份恢复口径已定义 |
| 环境变量配置纪要 | ✅ 完成 | §3 DB路径/cache/provider/LLM/QMT/WebUI/测试标记均需记录 |

---

## 8. 产品指标与监控

> 合并自 `03-ops/ops-metrics.md`

### 8.1 指标分层

| 指标层 | 目标 | 示例 |
|---|---|---|
| 产品价值指标 | 判断用户是否完成关键工作流 | 研究报告完成率、回测完成率 |
| 金融质量指标 | 判断数据和分析是否可信 | 数据新鲜度、provider 可用率 |
| 交易安全指标 | 判断交易路径是否安全 | 风控拦截率、人工确认率 |
| 系统运行指标 | 判断系统是否稳定 | API 错误率、任务失败率 |
| 审计完整性指标 | 判断关键动作是否可追溯 | 审计事件覆盖率、数据快照覆盖率 |

### 8.2 告警需求

| 告警级别 | 场景 | 处理动作 |
|---|---|---|
| P0 | kill switch 触发、订单状态不一致、真实执行回报异常 | 阻断后续交易 |
| P1 | provider 主源不可用、数据严重延迟 | 降级或标红 |
| P2 | 单次 AI 生成失败、单次回测失败 | 页面提示并记录 |
| P3 | 非关键页面数据为空 | 记录日志，允许降级 |

### 8.3 不做事项

- 不在文档阶段引入复杂监控系统选型
- 不要求立即接 Prometheus、Grafana 或外部告警平台
- 不把指标做成装饰性数字；没有采集来源的指标不得显示为真实值

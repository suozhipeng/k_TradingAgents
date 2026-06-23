# A 股部署与环境文档

| 更新时间：2026-06-23 |

本文定义 TradingAgents-Astock 核心功能实现所需的环境、依赖、启动和健康检查要求。本文只服务研究、回测、模拟盘、受控执行和 WebUI 等核心功能，不扩展为企业级部署、安全与隐私策略、SLA 或故障等级。

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
| Streamlit viewer | 只读研究 viewer | 与 Flask 角色分离 |
| DuckDB | 本地缓存和数据存储 | 数据目录、备份、迁移边界明确 |
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

# A 股实盘运行手册

| 更新时间：2026-06-23 |

本文定义 TradingAgents-Astock 从研究/模拟/受控执行进入实盘辅助运行时的操作手册。当前系统尚不等同于完整自动实盘生产系统；任何真实执行必须先通过 Phase 30 Live Trading Readiness。

## 1. 运行模式

| 模式 | 含义 | 允许动作 |
|---|---|---|
| `research` | 只读研究和报告 | AI 分析、数据查询、报告生成 |
| `paper` | 模拟盘 | 虚拟订单、虚拟成交、模拟持仓 |
| `managed` | 受控执行 | 风控门 + 人工确认 + QMT 桥接 |
| `live-ready` | 满足准入清单后的实盘准备状态 | 仅在 checklist 全部通过后允许标记 |

默认模式不得高于 `managed`。

## 2. 启动前检查

### 2.1 环境检查

- `.env` 已配置必要 provider key。
- `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE` 明确设置。
- live research 不允许回退到 `BridgeLLM`。
- WebUI 运行端口明确，避免 macOS AirPlay 占用 5000。
- DuckDB/store 可读写。

### 2.2 数据检查

- provider 健康可见。
- 数据新鲜度可见。
- 关键数据源不可用时有 fallback 或降级策略。
- 回测/交易使用的数据快照可追溯。

### 2.3 交易检查

- 当前模式明确显示。
- kill switch 状态可见。
- 风控门状态可见。
- paper/managed/live-ready 视觉和文案区分。
- QMT 不可用时自动降级或阻断，不得伪装成功。

## 3. 实盘准入 checklist

进入 `live-ready` 前必须满足：

- 账户资金、持仓、可用资金、冻结资金状态可读取。
- 委托、成交、撤单、拒单、部分成交状态可读取。
- 本地订单与券商回报 reconciliation 可检测。
- kill switch 可启停并写审计。
- 最大单笔金额、最大持仓、最大日亏损、交易时段约束可执行。
- 所有交易动作有人工确认记录。
- 所有交易动作有 Audit Event。
- 数据快照和行情时间可追溯。
- 故障恢复和回滚流程已验证。

不满足任一项时，不得标记 `live-ready`。

## 4. 日常运行流程

1. 检查 Data & Ops：provider、DuckDB、缓存、任务状态。
2. 检查系统模式：确认仍为预期的 research/paper/managed。
3. 运行 AI Research 或 Strategy Lab。
4. 如需交易，先进入 paper 或 managed。
5. 执行前检查 Risk Gate、kill switch、数据快照和人工确认。
6. 执行后检查订单状态、成交状态和 reconciliation。
7. 记录异常、失败和审计事件。

## 5. 异常处理

| 异常 | 处理 |
|---|---|
| provider 主源失败 | fallback；若无可用备源，标记数据不可用 |
| 数据严重延迟 | 禁止 live-ready，允许 research 降级展示 |
| LLM 失败 | research 失败或降级，不产生交易动作 |
| Risk Gate 拦截 | 阻断订单，记录 reason code |
| kill switch 触发 | 阻断后续交易动作 |
| QMT 不可用 | 降级 paper 或阻断 managed |
| 订单状态不一致 | 停止后续交易，进入 reconciliation |
| DuckDB/store 不可用 | 阻断需要持久化的任务 |

## 6. 回滚策略

- WebUI 页面异常：回退到上一个稳定模板或禁用入口。
- API schema 异常：保留兼容字段，不删除旧字段。
- 数据刷新异常：保留旧数据快照，标记 stale。
- 回测异常：标记结果 invalid，不进入策略对比。
- 交易异常：启用 kill switch，停止后续执行。

## 7. 运行记录

每次 managed/live-ready 运行必须记录：

- 运行日期和模式。
- provider 状态。
- 数据快照。
- AI/策略输入。
- 风控结果。
- 人工确认。
- 订单/成交状态。
- 异常和处理结果。

## 8. 验收要求

- Phase 30 必须把本 runbook 转成可执行 checklist。
- Phase 35 必须验证订单生命周期和 reconciliation。
- Phase 37 必须把运行记录接入 Ops & Audit。

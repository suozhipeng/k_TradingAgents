# A 股 API 契约文档

| 更新时间：2026-06-26 |

本文定义 TradingAgents-Astock 的生产级 API 契约要求。当前代码中的具体端点以实现为准；本文用于约束后续 Phase 30-38 的接口口径、能力等级、错误语义和验收要求。

## 1. API 总原则

- 所有 API 必须标注能力等级：`research`、`paper`、`managed`、`live-ready`。
- `mock` 不是顶层能力等级；它只用于描述 `source`、`mock_mode` 或降级实现状态。
- 所有 API 响应必须包含稳定的 `success`、`data`、`error`、`meta` 结构，或在 phase 文档中说明兼容例外。
- 不能把 mock、paper、managed 响应描述成真实实盘。
- 交易相关 API 必须返回风控状态、确认状态和审计引用。
- 回测、AI、数据刷新等长任务必须返回 task id，并进入 Ops/Audit 追踪。

## 1.1 Phase 30 口径结论

- `research`：只读研究、行情查询、报告与页面展示，不产生真实下单能力。
- `paper`：虚拟资金、虚拟成交、虚拟持仓；当前 `/api/v1/trade/order`、`/api/v1/trade/state`、`/api/v1/paper/*` 均属于此类。
- `managed`：受控执行口径，要求风控门、人工确认、QMT 桥接和可追溯审计；当前仓库只具备雏形和 mock/read-only 入口。
- `live-ready`：准入状态，不是默认运行模式；只有 checklist、审计、回报对账和回滚链路全部闭合后才允许声明。

## 2. 标准响应 envelope

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "capability": "research",
    "source": "duckdb|provider|cache|mock|paper|managed",
    "request_id": "uuid",
    "generated_at": "2026-06-23T00:00:00Z",
    "data_snapshot_id": "optional",
    "audit_event_id": "optional"
  }
}
```

错误响应：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "DATA_PROVIDER_UNAVAILABLE",
    "message": "provider unavailable",
    "category": "data|validation|risk|execution|system",
    "retryable": true,
    "details": {}
  },
  "meta": {
    "capability": "research",
    "request_id": "uuid",
    "generated_at": "2026-06-23T00:00:00Z"
  }
}
```

## 3. 错误码分类

| 分类 | 示例错误码 | 处理要求 |
|---|---|---|
| `validation` | `INVALID_SYMBOL`, `INVALID_DATE_RANGE`, `INVALID_STRATEGY_PARAM` | 前端提示用户修正输入 |
| `data` | `DATA_PROVIDER_UNAVAILABLE`, `DATA_STALE`, `DATA_QUALITY_LOW` | 标注 provider、fallback 和数据质量 |
| `research` | `LLM_UNAVAILABLE`, `RESEARCH_CONTEXT_MISSING` | 不生成交易动作，只允许 advisory 降级 |
| `backtest` | `INSUFFICIENT_HISTORY`, `LOOKAHEAD_RISK`, `NO_TRADES` | 回测结果必须标记不可比较或低置信度 |
| `risk` | `RISK_GATE_BLOCKED`, `KILL_SWITCH_ACTIVE`, `LIMIT_EXCEEDED` | 阻断执行并写审计 |
| `execution` | `BROKER_UNAVAILABLE`, `ORDER_REJECTED`, `RECONCILIATION_MISMATCH` | 不得静默重试真实订单 |
| `system` | `TASK_FAILED`, `STORE_UNAVAILABLE`, `INTERNAL_ERROR` | 进入 Ops 错误中心 |

## 4. API 能力矩阵

| 模块 | API 范围 | 能力等级 | 生产级要求 |
|------|----------|----------|-----------|
| Data & Ops | `/api/v1/data/*`, `/api/v1/cache/*`, `/api/v1/data-health/*` | `research` | 返回 provider、freshness、quality、fallback |
| AI Research | `/api/v1/research/*`, `/api/v1/ai-agent/*`, `/api/v1/reports/*` | `research` | 返回模型、prompt、数据快照、引用来源 |
| Strategy Lab | `/api/v1/backtest/*`, `/api/v1/market/strategies` | `research` / `paper` | 返回数据假设、成本模型、benchmark、样本外状态 |
| Market Leaders | `/api/v1/market-data/*`, screener/sector endpoints | `research` | 返回候选池来源、入池/出池理由、刷新时间 |
| **Paper Trading** | `/api/v1/paper/*` | `paper` | 明确虚拟成交、虚拟资金、虚拟持仓 |
| **QMT Managed** | `/api/v1/qmt/*` | `managed` (mock) | 未接真实环境时必须标注 mock/read-only |
| **Trading** | `/api/v1/trade/*` | `paper` / `managed` / `live-ready` | 返回模式、风控、确认、订单状态和审计 |
| SSE / Tasks | `/api/v1/sse/*` | `research` / `paper` | 返回 task lifecycle、错误和进度 |

### 4.1 实际 endpoint 能力等级（Phase 30）

| Endpoint | 当前能力 | 说明 |
|----------|----------|------|
| `POST /api/v1/trade/order` | `paper` | 虚拟下单，走 PaperTrader |
| `GET /api/v1/trade/quote` | `research` | 真实市场行情（EastMoney/Sina） |
| `GET /api/v1/trade/state` | `paper` | PaperTrader 虚拟持仓 |
| `POST /api/v1/paper/cycle` | `paper` | 虚拟策略周期执行 |
| `GET /api/v1/paper/state` | `paper` | 虚拟账户状态 |
| `GET /api/v1/paper/trades` | `paper` | 虚拟成交记录 |
| `GET /api/v1/qmt/health` | `managed` (mock) | Mock QMT 健康检查 |
| `GET /api/v1/qmt/positions` | `managed` (mock) | Mock QMT 持仓 |
| `GET /api/v1/qmt/orders` | `managed` (mock) | Mock QMT 订单 |
| `GET /api/v1/kline` | `research` | 历史 K 线数据 |
| `GET /api/v1/data/health` | `research` | 数据源健康状态 |

## 5. 关键 schema

### 5.1 CapabilityMeta

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `capability` | enum | 是 | `research` / `paper` / `managed` / `live-ready` |
| `source` | string | 是 | `provider` / `duckdb` / `cache` / `mock` / `paper` / `managed` |
| `request_id` | string | 是 | 请求追踪 ID |
| `generated_at` | datetime | 是 | 生成时间 |
| `data_snapshot_id` | string | 否 | 数据快照 ID |
| `audit_event_id` | string | 否 | 审计事件 ID |

### 5.1A TradingMode

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mode` | enum | 是 | `research` / `paper` / `managed` / `live-ready` |
| `is_default` | bool | 否 | 是否默认模式 |
| `requires_human_confirmation` | bool | 否 | 是否要求人工确认 |
| `allows_real_broker_order` | bool | 否 | 是否允许真实券商下单 |
| `ui_status` | enum | 否 | `enabled` / `disabled` / `mock` / `degraded` |

模式解释：

- `research`：只读，不显示真实下单能力。
- `paper`：允许虚拟下单，但必须明确 `actionable=false` / `ResearchOnly` 研究语义。
- `managed`：允许受控执行，但必须有风控、人工确认、审计和桥接状态。
- `live-ready`：仅代表通过准入，不代表默认自动实盘。

### 5.1B ExecutionCapability

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `capability` | enum | 是 | `research` / `paper` / `managed` / `live-ready` |
| `mock_mode` | bool | 否 | 当前是否为 mock 或只读桩实现 |
| `effective_mode` | enum | 否 | 当前请求真正落到的运行模式 |
| `risk_status` | enum | 否 | `pending` / `allowed` / `blocked` |
| `confirmation_status` | enum | 否 | `not_required` / `pending` / `confirmed` / `rejected` |
| `execution_signal` | string | 否 | 如 `ResearchOnly` |
| `decision_scope` | string | 否 | 如 `paper_trading_only` / `risk_gate_only` |
| `audit_event_id` | string | 否 | 审计引用 |

Phase 30 约束：

- capability 用于表达“产品口径允许到哪一层”。
- `mock_mode` / `source=mock` 用于表达“当前实现是否仍是桩或降级”。
- `effective_mode` 用于表达“本次请求实际落到哪条执行链路”；例如页面传 `live`，若后端仍落到 PaperTrader，则必须写明 `effective_mode=paper`。

### 5.2 TaskRun

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task_id` | string | 是 | 任务 ID |
| `task_type` | enum | 是 | `data_refresh` / `research` / `backtest` / `report` / `trade` |
| `status` | enum | 是 | `queued` / `running` / `success` / `failed` / `cancelled` |
| `progress` | number | 否 | 0-100 |
| `started_at` | datetime | 否 | 开始时间 |
| `finished_at` | datetime | 否 | 结束时间 |
| `error` | object | 否 | 标准错误对象 |

### 5.3 OrderState

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `order_id` | string | 是 | 本地订单 ID |
| `broker_order_id` | string | 否 | 券商订单 ID |
| `mode` | enum | 是 | `paper` / `managed` / `live-ready` |
| `symbol` | string | 是 | 标的 |
| `side` | enum | 是 | `buy` / `sell` |
| `quantity` | number | 是 | 数量 |
| `status` | enum | 是 | `created` / `submitted` / `partial_filled` / `filled` / `cancelled` / `rejected` / `expired` / `error` |
| `risk_status` | enum | 是 | `pending` / `allowed` / `blocked` |
| `confirmation_status` | enum | 是 | `not_required` / `pending` / `confirmed` / `rejected` |
| `audit_event_id` | string | 是 | 审计事件 |

## 6. 版本与兼容

- 破坏性字段变更必须提升 API version 或提供兼容字段。
- 新增字段必须保持向后兼容。
- 删除 endpoint 前必须在 phase 文档中写迁移策略。
- 页面不能直接依赖未版本化的内部字段。

## 7. 验收要求

- Phase 30 必须为交易相关 API 增加能力等级标记。
- Phase 31 必须为数据 API 增加质量和 freshness 标记。
- Phase 32 必须为 Strategy Lab API 增加统一策略和回测结果 schema。
- Phase 37 必须为长任务和审计建立标准 TaskRun/Audit Event。

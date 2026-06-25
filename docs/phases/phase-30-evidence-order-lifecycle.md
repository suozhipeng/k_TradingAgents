# Phase 30 — 订单生命周期状态机

## 状态定义

```
                    ┌─────────────────────────────────────┐
                    │            created                   │
                    │  (订单已创建，未提交执行引擎)         │
                    └──────────┬──────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────────────────────┐
                    │           submitted                  │
                    │  (已提交执行引擎/券商，等待确认)      │
                    └──────────┬──────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
          ┌──────────────────┐  ┌──────────────────┐
          │   confirmed      │  │    rejected      │
          │ (人工/自动确认)  │  │ (券商拒绝)       │
          └────────┬─────────┘  └──────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
  ┌──────────────┐ ┌──────────────┐
  │ partial_filled│ │    filled    │
  │ (部分成交)    │ │ (全部成交)   │
  └───────┬──────┘ └──────────────┘
          │ (继续剩余部分)
          │
          ▼
  ┌──────────────┐
  │    expired   │
  │ (未成交过期) │
  └──────────────┘

另外两个终端状态（可从任意状态转入）：

  ┌──────────────┐       ┌──────────────┐
  │  cancelled   │       │    error     │
  │ (用户取消)   │       │ (系统/网络错误)│
  └──────────────┘       └──────────────┘
```

## 状态枚举（对应 ASTOCK_API_CONTRACTS.md OrderState.status）

| 状态 | 值 | 说明 | 可转入 |
|------|-----|------|--------|
| Created | `created` | 订单已创建，未提交执行引擎 | submitted, cancelled, error |
| Submitted | `submitted` | 已提交执行引擎/券商，等待响应 | confirmed, rejected, cancelled, error |
| Confirmed | `confirmed` | 人工或自动确认通过 | partial_filled, filled, cancelled, error |
| Partial Filled | `partial_filled` | 部分成交，剩余部分继续等待 | partial_filled, filled, cancelled, expired, error |
| Filled | `filled` | 全部成交，终端状态 | — |
| Cancelled | `cancelled` | 用户主动取消，终端状态 | — |
| Rejected | `rejected` | 券商/风控拒绝，终端状态 | — |
| Expired | `expired` | 超过有效期未成交，终端状态 | — |
| Error | `error` | 系统/网络错误，终端状态 | — |

## 各 TradingMode 支持的状态

| TradingMode | 支持的状态 |
|-------------|-----------|
| `research` | created, cancelled, rejected, error |
| `paper` | 全状态（立即跳转到 filled） |
| `managed` | 全状态（需要人工 confirmed 才能执行） |
| `live-ready` | 全状态（自动执行） |

## 状态转换规则

1. **非终端状态可以有向前的转换（created → submitted → confirmed → partial_filled → filled）**
2. **任何非终端状态都可以被 cancelled 或 error 中断**
3. **终端状态（filled / cancelled / rejected / expired / error）不可再转换**
4. **partial_filled 可以继续转为 filled（剩余部分成交）或 expired（剩余部分超时）**
5. **paper 模式下订单创建后立即转为 filled（模拟秒级成交）**

## 前端映射建议

| 状态 | 前端显示 | 颜色 |
|------|----------|------|
| created | 已创建 | 灰色 |
| submitted | 已提交 | 蓝色 |
| confirmed | 已确认 | 蓝色 |
| partial_filled | 部分成交 | 橙色 |
| filled | 全部成交 | 绿色 |
| cancelled | 已取消 | 灰色 |
| rejected | 已拒绝 | 红色 |
| expired | 已过期 | 黄色 |
| error | 异常 | 红色 |

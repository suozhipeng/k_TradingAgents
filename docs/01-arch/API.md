# API 参考

> 合并自 `ASTOCK_API_CONTRACTS.md` + `ASTOCK_BACKEND_API_REFERENCE.md`

---

## 1. 契约规范


| 更新时间：2026-07-08 |

本文定义 TradingAgents-Astock 的生产级 API 契约要求。当前代码中的具体端点以实现为准；本文用于约束后续接口口径、能力等级、错误语义和验收要求。

当前本地验证基线（2026-07-08）：
- `DEEPSEEK_API_KEY=placeholder pytest -q` → `1082 passed, 10 skipped`
- 真实 live 验收已补跑：`tests/test_deepseek_reasoning.py -k live -m integration` → `1 passed`
- 真实 live provider 验收已补跑：`tests/test_astock_live_providers.py -m integration` → `7 passed, 1 skipped`
- 当前未闭环项仅为 `ASTOCK_IWENCAI_COOKIE` 缺失时 Iwencai live 用例跳过

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
| **QMT Managed** | `/api/v1/qmt/*` | `managed` (mock) | 固定 mock/read-only；API 不探测真实 QMT，不查询真实委托 |
| **Trading** | `/api/v1/trade/*` | `paper` / `managed` / `live-ready` | 返回模式、风控、确认、订单状态和审计 |
| SSE / Tasks | `/api/v1/sse/*` | `research` / `paper` | 返回 task lifecycle、错误和进度 |

### 4.1 关键 endpoint 能力等级（Phase 30 快照）

> 以下为代表性端点（当前代码基线约 119 个端点，详见完整端点参考 §2）。

| Endpoint | 当前能力 | 说明 |
|----------|----------|------|
| `POST /api/v1/trade/order` | `paper` | 虚拟下单，走 PaperTrader |
| `GET /api/v1/trade/quote` | `research` | 真实市场行情（EastMoney/Sina） |
| `GET /api/v1/trade/state` | `paper` | PaperTrader 虚拟持仓 |
| `GET /api/v1/daily/review` | `research` | 结构化每日市场复盘（5 指数、板块、涨跌家数、北向、龙虎榜、涨跌幅榜、regime） |
| `POST /api/v1/analysis/watchlist` | `research` | Watchlist 技术分析摘要，含 `research_only` 统计 |
| `POST /api/v1/watchlist/batch-analyze` | `research` | 自选股批量分析，供 dashboard / watchlist 入口复用 |
| `POST /api/v1/paper/cycle` | `paper` | 虚拟策略周期执行 |
| `GET /api/v1/paper/state` | `paper` | 虚拟账户状态 |
| `GET /api/v1/paper/trades` | `paper` | 虚拟成交记录 |
| `GET /api/v1/qmt/health` | `managed` (mock) | Mock QMT 健康检查；`real=1` 不会启用真实 bridge |
| `GET /api/v1/qmt/positions` | `managed` (mock) | Mock QMT 持仓 |
| `GET /api/v1/qmt/orders` | `managed` (mock) | Mock account snapshot；`orders` 固定为空兼容字段，真实订单/委托查询暂不接入 |
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

### 验收证据（2026-06-26）

| 验收项 | 状态 | 证据 |
|--------|------|------|
| API 总原则（能力等级/标注/响应结构）| ✅ 完成 | §1 定义 4 级能力 + mock 语义 + 稳定性要求 |
| Phase 30 能力边界定义 | ✅ 完成 | §1.1 research/paper/managed/live-ready 四层定义 + 当前实际落点 |
| 标准响应 envelope | ✅ 完成 | §2 success/data/error/meta 完整结构 + 错误响应格式 |
| 错误码分类 | ✅ 完成 | §3 7 类（validation/data/research/backtest/risk/execution/system）+ 处理要求 |
| API 能力矩阵 | ✅ 完成 | §4 8 模块 × 能力等级 × 生产级要求 |
| 实际 endpoint 能力等级 | ✅ 完成 | §4.1 11 个关键 endpoint 显式标注 |
| CapabilityMeta schema | ✅ 完成 | §5.1 capability/source/request_id/generated_at/snapshot/audit |
| TradingMode schema | ✅ 完成 | §5.1A mode/is_default/confirmation/allows_real_broker/ui_status |
| ExecutionCapability schema | ✅ 完成 | §5.1B capability/mock/effective/risk/confirmation/audit |
| TaskRun schema | ✅ 完成 | §5.2 task_id/type/status/progress/timestamps/error |
| OrderState schema | ✅ 完成 | §5.3 order/broker/mode/symbol/side/quantity/status/risk/confirmation/audit |
| 版本兼容要求 | ✅ 完成 | §6 破坏性变更/新增字段/删除 endpoint/页面依赖规则 4 项 |



---

## 2. 完整端点参考


| 更新时间：2026-07-08 |

本文梳理 TradingAgents-Astock 当前后台 API、所属模块、数据源、能力等级、真实/模拟边界和测试验收。`01-arch/API.md` 定义 API 规范；本文列出现有与 Phase 30-39 目标 API 清单。

## 1. API 通用约定

- 基础前缀：`/api/v1`
- 能力等级：`research` / `paper` / `managed` / `live-ready`
- `mock` 只作为 `source`、`mock_mode` 或降级标签，不单独作为顶层 capability。

## 2. 请求/响应示例

> 以下示例均取自运行中 DuckDB 后端的真实响应。部分字段（如 `bars`）因数据量较大仅展示片断。

### 2.1 K 线查询

**请求：**
```bash
curl -X GET "http://localhost:5860/api/v1/kline?symbol=600519.SH&limit=2"
```

**响应：**
```json
{
  "symbol": "600519.SH",
  "interval": "1d",
  "bars": [
    {
      "adjust": "none",
      "amount": 7353757696.0,
      "bar_time": "2026-06-04 15:00",
      "close": 1277.97,
      "created_at": "2026-06-28 23:26",
      "high": 1285.9,
      "interval": "1d",
      "low": 1273.0,
      "open": 1285.9,
      "quality": "normal",
      "source": "mootdx",
      "symbol": "600519.SH",
      "trade_date": "2026-06-04",
      "turnover_rate": null,
      "updated_at": "2026-06-28 23:26",
      "volume": 57359.0
    }
  ]
}
```

### 2.2 实时报价

**请求：**
```bash
curl -X GET "http://localhost:5860/api/v1/trade/quote?symbol=600519.SH"
```

**响应：**
```json
{
  "symbol": "600519.SH",
  "name": "XD贵州茅",
  "last_price": 1168.63,
  "open": 1199.0,
  "high": 1199.0,
  "low": 1168.1,
  "change": -15.45,
  "change_pct": -1.3,
  "volume": 5006647,
  "bid": 1168.63,
  "ask": 1168.78,
  "source": "live",
  "timestamp": "2026-06-28T23:33:32.619479"
}
```

### 2.3 回测运行

**请求：**
```bash
curl -X POST "http://localhost:5860/api/v1/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH", "strategy": "MovingAverageTrend", "start": "2024-01-01", "end": "2024-06-01", "mock_data": true}'
```

**响应：**
```json
{
  "run_id": "20260628233332",
  "symbol": "600519.SH",
  "strategy_name": "MovingAverageTrend",
  "start_date": "2024-01-01",
  "end_date": "2024-06-01",
  "total_return": 0.050464,
  "annualized_return": 6.907112,
  "sharpe_ratio": 7.706053,
  "max_drawdown": 0.002245,
  "win_rate": 0.0,
  "total_trades": 3,
  "alpha": 0.0,
  "beta": 0.0,
  "benchmark_return": 0.0,
  "benchmark_max_drawdown": 0.0,
  "benchmark_symbol": "",
  "execution_signal": "ResearchOnly",
  "cost_breakdown": {
    "commission": 75.54,
    "slippage": 604.33,
    "stamp_tax": 101.47,
    "total_fees": 781.34
  },
  "data_assumption": {
    "adjustment": "forward",
    "cost_model": "zero",
    "data_quality": "mock",
    "data_source": "mock_deterministic",
    "delisted": false,
    "look_ahead_bias_risk": false,
    "price_limit_check": true,
    "settlement": "t+1",
    "slippage_bps": 0.0,
    "st_stock": false,
    "survivorship_bias_risk": true,
    "suspension_check": true,
    "volume_cap_pct": 25.0
  }
}
```

### 2.4 市场摘要

**请求：**
```bash
curl -X GET "http://localhost:5860/api/v1/market/summary?symbol=600519.SH"
```

**响应：**
```json
{
  "symbol": "600519.SH",
  "latest_price": 1168.63,
  "latest_date": "2026-06-26",
  "source": "mootdx",
  "updated_at": "2026-06-28 23:26",
  "pe": null,
  "pb": 17.75,
  "market_cap": 14608.83,
  "kline_bars": [{"bar_time": "2026-06-26 15:00", "close": 1168.63, "volume": 50066, "source": "mootdx", ...}],
  "valuations": [{"trade_date": "2026-06-28", "pe": null, "pb": 17.75, "market_cap": 14608.83, "source": "tencent"}],
  "indicators": []
}
```

### 2.5 错误响应

**请求：**
```bash
curl -X GET "http://localhost:5860/api/v1/kline?symbol="
```

**响应：**
```json
{
  "error": "symbol is required",
  "status": 400
}
```

## 3. Health / Dashboard

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/health` | GET | 服务健康 | `backend`, `status`, `store_connected`, `version` | research | `test_astock_api.py` |
| `/api/v1/dashboard/overview` | GET | 首页概览 | `statistics`, `recent_backtests`, `recent_trades`, `paper_positions`, `paper_equity_curve`, `latest_equity_curve` | research/paper | `test_astock_api.py`, `test_astock_web.py` |
| `/api/v1/admin/backend` | GET | 后端状态 | `backend`, `duckdb_connected`, `postgresql`, `postgresql_connected` | admin | — |

## 4. Data & Ops API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/kline` | GET | K 线 | `symbol`, `interval`, `bars[]` (含 bar_time/open/high/low/close/volume/amount/source) | research | `test_astock_api.py`, `test_astock_data_sources.py` |
| `/api/v1/valuation` | GET | 估值 | `symbol`, `valuations[]` (含 pe/pb/market_cap/source/trade_date) | research | 同上 |
| `/api/v1/orderbook` | GET | 盘口 | `symbol`, `snapshots[]` | research | `test_astock_data_sources.py` |
| `/api/v1/trade_tape` | GET | 分笔 | `symbol`, `ticks[]`, `count`, `meta` (含 source) | research | 同上 |
| `/api/v1/news` | GET | 新闻 | `symbol`, `news[]` | research | `test_astock_api.py` |
| `/api/v1/news/live` | GET | 实时新闻 | `symbol`, `type`, `source`, `items[]`, `count` | research | 同上 |
| `/api/v1/news/stock` | GET | 个股新闻 | `symbol`, `items[]`, `count` | research | 同上 |
| `/api/v1/research` | GET | 研报列表 | `symbol`, `reports[]` | research | `test_astock_provider_fixtures.py` |
| `/api/v1/research/pdf` | GET | 研报 PDF | PDF payload | research | live guard |
| `/api/v1/research/expectation` | GET | 一致预期 | `symbol`, `items[]`, `count` | research | provider tests |
| `/api/v1/research/search` | GET | 研报搜索 | `symbol`, `query`, `items[]`, `count` | research | 同上 |
| `/api/v1/fundamentals` | GET | 基本面 | `symbol`, `items[]` (period/ROE/净利润等财务指标), `count`, `meta` | research | `test_astock_interface_analyst.py` |
| `/api/v1/f10` | GET | F10 | `symbol`, `f10` (code/total_shares/industry/province), `meta` (含 source) | research | 同上 |
| `/api/v1/announcements` | GET | 公告 | `symbol`, `announcements[]` | research | `test_astock_data_sources.py` |
| `/api/v1/store/stats` | GET | 表统计 | `stats` (32 张表 × `rows`/`latest_date`) | research | `test_astock_store.py` |
| `/api/v1/data/refresh/kline` | POST | 刷新 K 线 | `symbol`, `rows_inserted`, `status` | research | 同上 |
| `/api/v1/data/refresh/valuation` | POST | 刷新估值 | `symbol`, `rows_inserted`, `status` | research | 同上 |
| `/api/v1/data/refresh/all` | POST | 刷新全部 | `results`, `status` | research | 同上 |
| `/api/v1/data/health` | GET | 数据健康 | `sources[]`, `summary` (total/available/degraded), `quality_overall`, `cleaning` | research | `test_astock_web.py` |

核心请求参数：

- `symbol`：A 股代码，例如 `600519.SH`。
- `start` / `end`：日期。
- `interval`：K 线周期。
- `limit`：返回条数。
- `source`：可选 provider。

目标补充：

- Phase 31：统一返回 `DataQualityTag` 和 `BacktestDataAssumption`。
- Phase 37：刷新任务返回 `TaskRun`。

## 5. TradingView / KLine API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/tv/stock-search` | GET | 股票搜索 | `stocks[]` (含 code/name) | research | `test_astock_tv_routes.py` |
| `/api/v1/tv/stock-info` | GET | 股票信息 | `symbol`, `name`, `exchange`, `currency`, `type` | research | 同上 |
| `/api/v1/tv/symbols` | GET | TV symbol resolve | `symbol`, `name`, `type`, `exchange`, `minmov`, `pricescale` | research | 同上 |
| `/api/v1/tv/history` | GET | TV history datafeed | `s`, `t[]`, `o[]`, `h[]`, `l[]`, `c[]`, `v[]` (TradingView 标准格式) | research | 同上 |

目标补充：

- 返回数据延迟、fallback、复权口径。
- KLine 页面显示 data quality 标签。

## 6. Strategy Lab API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/backtest/run` | POST | 运行回测 | `run_id`, `symbol`, `strategy_name`, `total_return`, `sharpe_ratio`, `max_drawdown`, `win_rate`, `total_trades`, `periods[]`, `trades[]`, `cost_breakdown`, `data_assumption`, `execution_signal`, `benchmark_*`, `alpha`, `beta` | research/paper | `test_astock_backtest.py`, `test_astock_api.py` |
| `/api/v1/backtest/results` | GET | 查询回测结果 | `results[]` (含 run_id/symbol/total_return/sharpe/max_drawdown/params) | research | 同上 |
| `/api/v1/backtest/results` | DELETE | 清理回测结果 | `status`, `deleted` | research | 同上 |
| `/api/v1/backtest/results/<id>` | DELETE | 删除单次结果 | `status`, `deleted` | research | 同上 |
| `/api/v1/backtest/compare` | GET | 策略对比 | `comparison[]` (含 strategy_name/total_return/sharpe/equity_curve/returns) | research | 同上 |
| `/api/v1/backtest/walkforward` | POST | WFA 分析 | `windows[]`, `summary` (含 avg_train/val_score, overfit_gap, param_stability) | research | — |
| `/api/v1/market/strategies` | GET | 策略列表 | `strategies[]` (name/description) | research | `test_astock_api.py` |

目标补充：

- Phase 32：统一 `StrategyRegistry`、`BacktestResult`、`OptimizeResult` schema。
- 回测结果必须包含 benchmark、成本模型、数据假设和反偏差状态。已达成（data_assumption 已返回）。

## 7. Market Leaders API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/market/summary` | GET | 市场摘要 | `symbol`, `latest_price`, `latest_date`, `source`, `pe`, `pb`, `market_cap`, `kline_bars[]`, `valuations[]`, `indicators[]` | research | `test_astock_api.py` |
| `/api/v1/market/overview` | GET | 宽泛市场概览 | `indices[]`, `advance`, `decline`, `source` (real/mock) | research | — |
| `/api/v1/market/sectors` | GET | 板块强弱 | `top[]`, `bottom[]`, `total` | research | 同上 |
| `/api/v1/market/dragon-tiger` | GET | 龙虎榜 | `stocks[]`, `date`, `total_records` | research | 同上 |
| `/api/v1/market/northbound` | GET | 北向资金 | `flow` | research | 同上 |
| `/api/v1/market/momentum-rotation` | POST | 动量轮动 | `leading_stocks[]`, `leading_source`, `equity_curve[]`, `benchmark_curve[]`, `total_return`, `sharpe_ratio`, `max_drawdown`, `dates[]` | research | `test_astock_web.py` |
| `/api/v1/market/regime` | GET | 市场状态 | `composite_score`, `verdict`, `recommended_strategies[]`, `dimensions` | research | — |

目标补充：

- Phase 34：统一 `LeaderPool` schema。
- mock fallback 必须进入 `meta.source=mock` 或页面显著标签。

## 8. AI Research API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/ai/analyze` | POST | AI 分析 | `status`, `symbol`, `advisory`, `llm_analysis`, `llm_error` | research | `test_astock_web.py`, `test_astock_graph_runtime.py` |
| `/api/v1/research/tasks` | POST | 创建研究任务 | — (目标 Phase 33) | research | — |
| `/api/v1/reports/list` | GET | 报告列表 | `items[]` (含 title/date/status) | research | — |

## 9. Paper / Trading / QMT API

| API | Method | 功能 | 响应 keys | 能力 | 测试 |
|---|---|---|---|---|---|
| `/api/v1/daily/review` | GET | 结构化每日市场复盘 | `date`, `indices`, `sectors`, `breadth`, `northbound`, `dragon_tiger`, `top_gainers`, `top_losers`, `regime` | research | `test_astock_api.py` |
| `/api/v1/analysis/watchlist` | POST | Watchlist 技术分析摘要 | `stocks[]`, `summary.total`, `summary.buy`, `summary.hold`, `summary.sell`, `summary.research_only` | research | `test_astock_api.py` |
| `/api/v1/watchlist/batch-analyze` | POST | Watchlist 批量分析 | `results[]`, `summary`, `errors[]` | research | `test_astock_api.py` |
| `/api/v1/paper/state` | GET | 模拟盘状态 | `positions`, `cash`, `total_value`, `pnl`, `trade_count`, `execution_signal`, `decision_scope`, `last_updated` | paper | `test_astock_paper_trader.py` |
| `/api/v1/paper/trades` | GET | 模拟盘交易 | `trades[]` | paper | 同上 |
| `/api/v1/paper/cycle` | POST | 模拟盘周期 | `positions`, `cash`, `total_value`, `pnl`, `trade_count`, `last_updated` | paper | 同上 |
| `/api/v1/trade/order` | POST | 下单 | `order` (含 order_id/symbol/side/quantity/price/status) | paper | `test_astock_api.py` |
| `/api/v1/trade/quote` | GET | 实时报价 | `symbol`, `name`, `last_price`, `open`, `high`, `low`, `change`, `change_pct`, `volume`, `bid`, `ask`, `source`, `timestamp` | research | 同上 |
| `/api/v1/trade/state` | GET | 交易状态 | `positions[]`, `cash`, `total_value`, `pnl`, `trade_count` | paper | 同上 |
| `/api/v1/qmt/health` | GET | QMT mock 健康 | `healthy`, `mock_mode`, `host`, `port`, `real_connection_check`, `status` | managed | `test_astock_qmt_bridge.py` |
| `/api/v1/qmt/positions` | GET | QMT 持仓 | `positions[]`, `mock_mode`, `status` | managed | 同上 |
| `/api/v1/qmt/orders` | GET | Mock/read-only 账户快照；真实订单/委托查询暂不接入 | `account_snapshot`, `orders[]` (固定空列表), `mock_mode`, `status` | managed | 同上 |

## 10. SSE / Ops API

| API | Method | 功能 | 响应 keys | 能力 |
|---|---|---|---|---|
| `/api/v1/sse/events` | GET | SSE 事件流 | SSE stream (event/data 格式) | research/paper |
| `/api/v1/sse/paper-progress` | GET | paper 进度流 | SSE stream | paper |
| `/api/v1/ops/tasks` | GET | 任务列表 | `tasks[]` | research |
| `/api/v1/alerts` | GET | 告警列表 | `alerts[]` (含 severity/rule/message/time) | research |

## 11. 验收矩阵

| API 类别 | 必跑测试 | Phase |
|---|---|---|
| Data & Ops | `tests/test_astock_data_sources.py`, `tests/test_astock_api.py`, `tests/test_astock_tv_routes.py` | 31 |
| Strategy Lab | `tests/test_astock_strategies.py`, `tests/test_astock_backtest.py`, `tests/test_astock_optimizer.py`, `tests/test_astock_api.py` | 32 |
| AI Research | `tests/test_astock_graph_runtime.py`, `tests/test_astock_graph_bridge.py`, `tests/test_astock_ppt.py`, `tests/test_astock_web.py` | 33 |
| Market Leaders | `tests/test_astock_web.py`, `tests/test_astock_api.py` | 34 |
| Trading & Execution | `tests/test_astock_paper_trader.py`, `tests/test_astock_execution_risk_gate.py`, `tests/test_astock_qmt_execution.py` | 30/35 |
| Ops & Audit | `tests/test_astock_sse.py`, `tests/test_astock_api.py`, `tests/test_astock_web.py` | 37 |

## 12. 更新规则

- 新增 endpoint 必须同步本文和 `01-arch/API.md`。
- 数据源变化必须同步 `03-ops/data-sources.md`。
- schema 变化必须同步 `04-dev/PRD.md`。
- 页面依赖 API 变化必须同步 `README.md`。
- Hermes 执行任务时必须把 API 变化写入对应 phase 文档。

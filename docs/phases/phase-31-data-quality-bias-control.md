# Phase 31 Data Quality & Bias Control 需求与 Hermes 任务包

| 状态：delivered | 验收状态：Codex accept ✅ | 更新时间：2026-06-25 |

## 0. 前置依赖

- Phase 30：TradingMode enum、capability 标注规范（数据 API 也需要 capability 标签）

## 1. Phase 目标

把数据可信、来源、延迟、fallback、回测反偏差和数据假设从文档要求落到 API/schema/UI 验收口径。重点处理 akshare、mootdx、Tencent、iwencai、EastMoney、Sina 等非 QMT 数据源。

## 2. 范围

后台模块：

- `tradingagents/astock/data_sources/router.py`
- `tradingagents/astock/data_sources/adapters.py`
- `tradingagents/astock/data_sources/eastmoney.py`
- `tradingagents/astock/data_sources/sina_sectors.py`
- `tradingagents/astock/api/routes_data.py`
- `tradingagents/astock/api/routes_data_health.py`
- `tradingagents/astock/api/routes_tv.py`

前台模块：

- `data_health.html`
- `settings.html`
- `kc_chart.html`
- `tv_chart.html`

API：

- `GET /api/v1/kline`
- `GET /api/v1/valuation`
- `GET /api/v1/data/health`
- `POST /api/v1/data/refresh/*`
- `GET /api/v1/tv/history`

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 31-01 | 列出 K 线 API 当前字段和缺失 metadata。 | docs first；代码只读。 | 字段表包含 source/generated_at/freshness/quality/fallback_path。 |
| 31-02 | 定义 `DataQualityTag` schema。 | data dictionary、API contracts。 | normal/stale/partial/fallback/mock/degraded 定义清楚。 |
| 31-03 | 定义 `BacktestDataAssumption` schema。 | data dictionary、strategy docs。 | 复权、成本、滑点、T+1、成交约束、样本外字段明确。 |
| 31-04 | 梳理交易日历数据来源。 | data source usage。 | akshare/mootdx 可用性和 fallback 明确。 |
| 31-05 | 梳理停复牌字段来源。 | data dictionary/source usage。 | 无稳定来源必须标 planned。 |
| 31-06 | 梳理涨跌停成交约束。 | data dictionary、test plan。 | 回测不可成交条件明确。 |
| 31-07 | 登记 survivorship / look-ahead 风险。 | risk register。 | 风险 ID 更新并关联 Phase 31。 |
| 31-08 | 为 BacktestResult 补 `data_assumption` 文档字段。 | API contracts、data dictionary。 | 回测结果可表达数据假设。 |
| 31-09 | 更新 Data & Ops 页面验收点。 | WebUI checklist。 | data_health/settings 要求展示 freshness/quality。 |
| 31-10 | 运行数据源验收并记录。 | phase evidence。 | `tests/test_astock_data_sources.py -q` 结果写入 phase。 |

## 4. 测试命令

```bash
pytest tests/test_astock_data_sources.py -q
pytest tests/test_astock_provider_fixtures.py -q
pytest tests/test_astock_tv_routes.py -q
pytest tests/test_astock_calendar.py -q
pytest tests/test_astock_adjustment.py -q
pytest tests/test_astock_backtest.py -q
```

## 5. 完成标准

- 数据输出有 source/freshness/quality/fallback/snapshot 口径。
- 回测结果可展示数据假设和反偏差状态。
- live provider 测试有 guard，不伪造成稳定通过。

---

## 6. 交付总结（2026-06-25）

### 已完成

| 任务 | 文件 | Commit |
|------|------|--------|
| 31-01 DataQualityTag schema + router/API/UI 集成 | `quality.py`, `router.py`, `routes_data.py`, `routes_data_health.py`, `data_health.html` | `f8ded44`, `72a276a`, `2efdc18` |
| 31-02 交易日历 + API + backtest 集成 | `calendar.py`, `routes_market_data.py`, `backtest_engine.py` | `70cc10d`, `c902808` |
| 31-03 停复牌 schema | 无稳定数据源，标记为 planned | — |
| 31-05 复权处理 | `adjustment.py` | `07cd0d1` |
| 31-08 BacktestResult.data_assumption | `backtest_engine.py` | `ff18573` |
| 31-10 交易日校验（回测约束） | `backtest_engine.py`（交易日验证）| `c902808` |
| 全量回归 | 578 passed, 13 skipped | `07cd0d1` |

### 测试增量

- 新增 18 个测试：calendar(9) + adjustment(6) + quality-tag(3)
- 全量 astock 测试从 560 → 578

### Codex 验收

- 31-01/02/05 均通过独立 Codex review (accept)
- BacktestDataAssumption populate 修复经 Codex 重审确认 (ff18573)

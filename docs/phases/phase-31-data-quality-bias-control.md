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

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-31-evidence-acceptance-checklist.md`

# Phase 31 — Data & Ops 页面验收清单

## Data Health 页面（`data_health.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示所有数据源健康状态 | □ 通过 |
| 空态 | 无数据源可用 | 显示 "no sources available" | □ 通过 |
| 错误态 | DuckDB store 不可用 | 显示 store error | □ 通过 |
| 降级态 | 部分数据源不可用 | 显示 degraded 计数和详情 | □ 通过 |
| **freshness** | 数据源有 generated_at | 显示数据新鲜度标签 | □ Phase 31 |
| **quality** | 数据源有质量标签 | 显示 normal/stale/degraded | □ Phase 31 |

## Settings 页面（`settings.html`）

| 验收点 | 输入条件 | 预期输出 | 状态 |
|--------|----------|----------|------|
| 成功态 | 正常加载 | 显示配置项 | □ 通过 |
| 数据源设置 | 修改数据源 | 保存设置 | □ 通过 |
| **quality display** | 数据源质量 | 显示 freshness/quality | □ Phase 31 |

---
**Commit SHA**: b410074


---

> 以下内容合并自 `phase-31-evidence-data-constraints.md`

# Phase 31 — Data Source Assumptions & Constraints 文档

## 交易日历

| 数据源 | 可用性 | Fallback | 说明 |
|--------|--------|----------|------|
| akshare | 可用（需网络） | mootdx | `tool_trade_date_hist_sina` 获取交易日历 |
| mootdx | 可用 | cache | 通达信协议，工作日更新 |
| 本地 DuckDB | 按需预加载 | 无 | 需要手动刷新 |

## 停复牌字段

| 字段 | 稳定来源 | 状态 |
|------|----------|------|
| 停牌状态 | akshare `stock_info_suspend` | available |
| 复牌日期 | akshare | available |
| 停牌原因 | akshare (partial) | available |
| **停复牌统一字段** | **无稳定聚合来源** | **planned** — 需自定义 adapter |

## 涨跌停成交约束

| 约束 | A 股规则 | 回测处理 |
|------|----------|----------|
| 主板 ±10% | 涨停不可买，跌停不可卖 | 回测应跳过 |
| 科创板 ±20% | 同上 | 回测应跳过 |
| ST ±5% | 同上 | 回测应跳过 |
| 新股首日 ±44% | 特殊规则 | 测试标记 |

## 偏差风险登记

| 风险 ID | 风险 | 说明 | Phase 31 关联 |
|---------|------|------|---------------|
| R-001 | Survivorship Bias | 使用回测数据时，退市股票不在数据集中 | Phase 31-07 |
| R-002 | Look-ahead Bias | 使用未来数据生成信号 | Phase 31-07 |
| R-003 | Data Staleness | 离线数据超过 4 小时未更新 | Phase 31-02 |

---
**Commit SHA**: b410074

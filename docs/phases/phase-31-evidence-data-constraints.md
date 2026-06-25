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

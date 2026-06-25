# Phase 36 — Portfolio Risk & Attribution

## Portfolio schema

| 字段 | 说明 |
|------|------|
| `holdings` | Position[] — 持仓列表 |
| `cash` | 现金余额 |
| `nav` | 净资产值 |
| `pnl_total` | 累计盈亏 |

## RiskExposure schema

| 字段 | 说明 |
|------|------|
| `industry_concentration` | 行业集中度 |
| `top_holding_pct` | 最大持仓占比 |
| `beta` | Beta 系数 |
| `liquidity_score` | 流动性评分 |
| `var_95` | VaR 95% |
| `max_drawdown` | 最大回撤 |
| `stress_loss_pct` | 压力测试损失 |

## Attribution schema

| 字段 | 说明 |
|------|------|
| `benchmark_return` | 基准收益 |
| `selection_effect` | 选股效应 |
| `timing_effect` | 择时效应 |
| `cost_impact` | 成本影响 |
| `slippage_impact` | 滑点影响 |

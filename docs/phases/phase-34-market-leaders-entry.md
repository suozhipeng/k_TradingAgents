# Phase 34 Market Leaders 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

## 1. Phase 目标

把龙头动量、动量轮动、龙虎榜、北向资金、板块强弱和候选池收敛为一个 Market Leaders 顶层入口，内部用顶部 tab 切换。

## 2. 范围

后台模块：

- `tradingagents/astock/api/routes_market_data.py`
- `tradingagents/astock/execution/momentum_rotation.py`
- `tradingagents/astock/data_sources/eastmoney.py`
- `tradingagents/astock/data_sources/sina_sectors.py`

前台模块：

- `momentum_dashboard.html`
- `momentum_rotation.html`
- `dragon_tiger.html`
- `northbound.html`
- `sectors.html`

API：

- `GET /api/v1/market/dragon-tiger`
- `GET /api/v1/market/sectors`
- `GET /api/v1/market/northbound`
- `GET /api/v1/market/blocks`
- `POST /api/v1/market/momentum-rotation`
- `GET /api/v1/market/momentum`

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 34-01 | 列出现有龙头/板块/资金页面。 | docs；templates 只读。 | momentum/rotation/dragon/northbound/sectors 覆盖。 |
| 34-02 | 定义 Market Leaders 顶层入口。 | WebUI spec、ADR。 | 顶层最多一个入口。 |
| 34-03 | 定义 LeaderPool schema。 | data dictionary、API contracts。 | source/reason/score/refreshed_at 完整。 |
| 34-04 | 梳理 EastMoney/Sina/mock fallback。 | data source usage、risk register。 | mock 必须显著标注。 |
| 34-05 | 定义候选池入池理由字段。 | data dictionary、WebUI checklist。 | 可解释、可追溯。 |
| 34-06 | 定义候选池出池理由字段。 | data dictionary、WebUI checklist。 | 可解释、可追溯。 |
| 34-07 | 更新 Market Leaders 效果图。 | progress plan / WebUI spec。 | tab 和候选池区域清晰。 |
| 34-08 | 更新页面级验收清单。 | WebUI checklist。 | success/empty/error/degraded 证据要求明确。 |
| 34-09 | 运行 WebUI 测试。 | phase evidence。 | `tests/test_astock_web.py -q` 有结果。 |
| 34-10 | 运行 API 测试。 | phase evidence。 | `tests/test_astock_api.py -q` 有结果。 |

## 4. 测试命令

```bash
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q
```

## 5. 完成标准

- 顶层导航最多一个 Market Leaders / 龙头决策入口。
- 候选池有来源、刷新时间、入池/出池理由。
- EastMoney/Sina/mock fallback 语义不误导。

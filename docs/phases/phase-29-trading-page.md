# Phase 29: 专业交易页 — 多模式交易控制台

## Metadata

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-22`
- Git branch: `xg_dev`
- Commits: `268d326`, `c341034`, `f355a89`, `f948f2f`, `eca4ba6`, `87e5b73`, `1960c65`, `44c1b52`

## Product Objective

构建 TradingView 风格的专业交易控制台（trading.html），支持 **三种运行模式**：

| 模式 | 简称 | 下单路径 | 数据源 |
|------|------|---------|--------|
| 模拟盘交易 | Paper Trading | PaperTrader（内存模拟） | 实时行情 + Paper 状态 |
| 实盘执行 | 实盘 | QMT xttrader（需 QMT 桥接） | QMT 实时数据 |
| 研究辅助 | 研究 | 禁止下单（只读） | 实时行情 + KLineChart |

前端默认 Paper 模式，通过模式切换器在三种模式间切换。所有下单指令均携带 `actionable` / `execution_signal` / `decision_scope` 标记供后端风控校验。

## Scope

### Included

1. **交易主页**（`trading.html`）：
   - 模式切换器（Paper / 实盘 / 研究），默认 Paper
   - KLineChart 日线图（30 天限制），默认 MA5/20/60
   - 实时报价面板（EastMoney push2 实时推送）
   - 订单面板（价格/数量/方向/类型）— 研究模式隐藏
   - 仓位表格 + 成交记录表格 — 研究模式只读
   - 股价联动：搜索输入联动 KC Chart
   - 指数默认（000001.SH）、智能前缀补全（auto→.SH）

2. **Trade API**（`routes_trade.py`）：
   - `POST /api/v1/trade/order` — 下单（PaperTrader）
   - `GET /api/v1/trade/quote` — 实时报价（EastMoney push2 → Sina 降级）
   - `GET /api/v1/trade/state` — 仓位/成交状态
   - 60 秒报价缓存
   - 全局 paper trader 实例共享

3. **Sidebar 导航**：
   - Trading（主页，路由 `/`）

4. **Stock-info 共享端**（`KCDataLoader`）：
   - `GET /api/v1/stock-info` — 统一返回名称、代码、交易所/板块、行业、indices

5. **搜索建议**（拼音/代码/名称）：
   - 全页面统一搜索建议组件

### Excluded

- QMT 实盘下单当前不可用（需 QMT bridge 运行），UI 模式切换器保留入口但标记"QMT 未连接"
- 不包含高级订单类型（仅限限价/市价）

## Product Positioning

交易页同时承载三种定位，通过模式切换器统一入口：

- **Paper Trading 控制台**（默认）— 下单走 `PaperTrader`，`actionable=false` / `execution_signal=ResearchOnly`
- **实盘执行控制台**（QMT 就绪后）— 下单走 `QmtExecution`，需人工确认（safety mode）
- **研究辅助交易页** — 只读模式，基于 KLineChart 和实时报价辅助决策，不开放下单

三种模式共享同一个 KLineChart 视图、实时报价面板和搜索组件。模式切换只影响订单面板的可见性和后端路由。

## 测试

```bash
source .venv/bin/activate && python -m pytest tests/test_astock_web.py tests/test_astock_api.py -q
```

结果：**150 passed, 0 failed, 0 errors**（HEAD `975f5ee`）。

## Risks

- 实时报价依赖 EastMoney push2，非交易时段无更新（降级到 Sina 缓存）
- 报价缓存 60s，高频操作可能看到过期价格
- PaperTrader 状态不持久化到 DuckDB（仅内存）
- QMT 实盘模式需 QMT bridge 进程就绪，不可用时自动回退 Paper

# Phase 29: 专业交易页 — TradingView 风格交易控制台

## Metadata

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-22`
- Git branch: `xg_dev`
- Commits: `268d326`, `c341034`, `f355a89`, `f948f2f`, `eca4ba6`, `87e5b73`, `1960c65`, `44c1b52`

## Product Objective

构建 TradingView 风格的专业交易控制台（trading.html），包含实时报价、K 线图、订单面板、仓位管理、交易记录，支撑 Paper Trading 和后续实盘执行。

## Scope

### Included

1. **交易主页**（`trading.html`）：
   - KLineChart 日线图（30 天限制），默认 MA5/20/60
   - KC Chart 画线去重
   - 实时报价面板（EastMoney push2 实时推送）
   - 订单面板（价格/数量/方向/类型）
   - 仓位表格 + 成交记录表格
   - 股价联动：搜索输入联动 KC Chart
   - 指数默认（000001.SH）、智能前缀补全（auto→.SH）

2. **Trade API**（`routes_trade.py`）：
   - `POST /api/v1/trade/order` — 下单（paper_trader）
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

- 不涉及 QMT 实盘下单（下单走 PaperTrader）
- 不包含高级订单类型（仅限限价/市价）

## Product Positioning

当前交易页定位于 **Paper Trading 控制台**，提供研究辅助交易能力。所有下单走 PaperTrader 模拟盘路径，`actionable=false` / `execution_signal=ResearchOnly` 标记保持不变。

## 测试

```bash
source .venv/bin/activate && python -m pytest tests/test_astock_web.py tests/test_astock_api.py -q
```

结果：**150 passed, 0 failed, 0 errors**（HEAD `975f5ee`）。

## Risks

- 实时报价依赖 EastMoney push2，非交易时段无更新（降级到 Sina 缓存）
- 报价缓存 60s，高频操作可能看到过期价格
- PaperTrader 状态不持久化到 DuckDB（仅内存）

# Phase 25: 股票筛选器 + 板块轮动

## 元数据

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-20`
- Git branch: `xg_dev`
- Commits: `658d27f`, `eca4ba6`, `183876a`, `062ff3b`

## 目标

构建股票筛选器（TradingView 风格）和板块轮动页面（ECharts treemap 热力图）。

## 范围

### 包含

1. **股票筛选器**（`screener.html`）：
   - TradingView 风格筛选面板
   - 指标条件：RSI 区间、MA 金叉/死叉、MACD 金叉/死叉、成交量比
   - 实时筛选结果表格
   - 路由 `/screener`

2. **板块轮动页面**（`sectors.html`）：
   - ECharts treemap 热力图（瓦片=板块，大小=总市值，颜色=涨跌幅）
   - 板块排行（涨跌幅 TOP/BOTTOM）
   - 数据源：EastMoney → Sina-stock_sector_spot 三级降级
   - 路由 `/sectors`

3. **板块热力图**（`trading.html`, ECharts treemap）
   - 交易主页集成

4. **数据源降级**：
   - EastMoney push2（交易时段）→ Sina-stock_sector_spot（非交易时段）→ Mock（兜底）

### 排除

- 不修改现有数据源适配器（板块数据走独立 Sina 模块）
- 不做行业分类深度学习

## 测试结果

WebUI + API 切片：146 passed（含 screener/sectors 路由测试）

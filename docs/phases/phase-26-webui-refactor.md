# Phase 26: WebUI 全平台重构 — Strategy Hub + Sidebar + Research v2

## Metadata

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-21`
- Completed: `2026-06-22`
- Git branch: `xg_dev`
- Commits: `87e5b73`, `8d8a6f9`, `964ef3c`, `f50bd3b`, `f854c9b`, `1960c65`, `44c1b52`

## Objective

全平台 WebUI 重构：合并 Backtest/Performance/Compare 到 Strategy Hub、Sidebar 精简去重、Research 页面 KLineChart v2、数据防爆。

## Scope

### Included

1. **Strategy Hub（三位一体策略研究控制台）**：
   - `strategy_hub.html` 新页面
   - 合并：回测（原 backtest）+ 绩效分析（原 performance）+ 多策略对比（原 comparison）
   - Tab 式界面：单策略回测 / 多策略对比
   - 路由 `/strategy_hub`

2. **Sidebar 导航精简**：
   - 移除 Backtest → Strategy Hub 替代
   - 移除 Performance → Strategy Hub Tab1+2
   - 移除 Compare → Strategy Hub Tab3
   - 移除旧路由 `/backtest`、`/comparison`、`/performance`

3. **Research 专业量化终端 v2**（`research.html`）：
   - KLineChart 替换 lightweight-charts
   - 工具条（刷新 K 线/KC Chart/TV Pro 跳转）
   - 指标栏（MA/EMA/BOLL/MACD/KDJ/RSI 切换）
   - 网格布局（K 线 + 右侧三 Tab：实时快讯/个股新闻/AI 研报）
   - TradingView 深色主题（#131722 bg, #1c2030 面板）

4. **交易主页报价联动**：
   - 搜索输入联动 KC Chart
   - 实时报价面板

5. **数据防爆 + 科学计数法封杀**：
   - 全页面 NaN/Inf 防御
   - Chart.js y-axis 回调 `isFinite`
   - 红涨绿跌统一（#ef5350/#26a69a）

### Excluded

- 不删除旧模板文件（保留 backtest.html/comparison.html 文件，仅移除路由）
- 不改 CLI/API 层

## Test Results

WebUI + API 切片：**146 passed, 0 failed, 0 errors**（更新测试断言后）

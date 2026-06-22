# Phase 23: 龙头股动量轮动决策系统

## Metadata

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-21`
- Git branch: `xg_dev`
- Commits: `3255e84`, `86f540b`, `05731ab`, `9fbf875`

## Objective

构建龙头股（市场领涨股）动量轮动决策系统，包括标的池动态获取、多因子动量评分策略、独立看板和 WebUI 集成。

## Scope

### Included

1. **龙头股策略模块**（`tradingagents/astock/execution/momentum_rotation.py`）：
   - 多因子动量评分（涨幅/成交量/换手率等）
   - 轮动调仓逻辑
   - 回测接口

2. **标的池动态获取**：
   - 优先东方财富 API（akshare）
   - 兜底默认龙头股名录
   - `86f540b`

3. **Streamlit 独立看板**（`streamlit_app.py` / momentum 部分）：
   - 实时动量评分展示
   - 轮动信号面板
   - `9fbf875`

4. **WebUI 集成**（`momentum_dashboard.html`, `momentum_rotation.html`）：
   - 动量决策终端页面
   - 动量轮动独立看板
   - Slidebar 链接：动量决策终端
   - `05731ab`

### Excluded

- 不涉及实盘执行（仅研究信号输出）
- 不替换现有回测策略（独立模块）

## Test Results

A 股切片回归：472 passed, 1 skipped, 0 failed（Phase 21 基线，动量模块不增加新测试文件）

## Risks

- 龙头股定义可能随市场风格变化，标的池需定期维护
- 动量因子在震荡市中可能失效

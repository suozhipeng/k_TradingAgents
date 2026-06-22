# Phase 28: 新增 WebUI 数据源页面（5 页）

## Metadata

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-20`
- Git branch: `xg_dev`
- Commit SHA: `f87d6fa`

## Objective

新增 5 个数据源展示页面到 WebUI，覆盖龙虎榜、北向资金、动量决策、数据健康等。

## Scope

### Included

1. **动量决策终端**（`momentum_dashboard.html`）
   - 龙头股动量实时看板
   - 路由 `/momentum_dashboard`

2. **动量轮动独立看板**（`momentum_rotation.html`）
   - 轮动策略独立页面
   - 路由 `/momentum_rotation`

3. **龙虎榜**（`dragon_tiger.html`）
   - 个股主力资金追踪
   - 路由 `/dragon_tiger`

4. **北向资金**（`northbound.html`）
   - 沪深股通资金流
   - 路由 `/northbound`

5. **数据健康页**（`data_health.html`）
   - 数据源状态监控面板
   - 路由 `/data_health`

### Excluded

- 不新增后端 API（复用现有 data source adapter 层）
- 不修改现有页面

## Test Results

WebUI 路由测试已覆盖全部 5 页：103 passed（含新增路由）

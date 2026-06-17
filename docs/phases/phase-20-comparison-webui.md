# Phase 20: 策略对比页面 (Strategy Comparison WebUI)

| 元数据 | 值 |
|--------|-----|
| Phase | 20 |
| 类型 | WebUI 增强 — 新页面 |
| 开始日期 | 2026-06-17 |
| 结束日期 | 2026-06-17 |
| 提交 SHA | pending |

## 范围

利用已有的 `/api/v1/backtest/compare` API 端点，创建全新的策略对比 WebUI 页面。

### 包含

- 增强 compare API：返回 `equity_curve`、`returns`、`rank` 字段，按综合评分排序
- `comparison.html` 新页面：多选策略、输入参数、绩效对比表格 + Chart.js 图表
- 侧边栏添加 "对比 Comparison" 导航链接
- 全量测试覆盖（WebUI 渲染测试 + API 字段验证）

### 排除

- 不修改已有策略逻辑或回测引擎
- 不修改其他页面
- 不涉及实盘数据

## 实现详情

### 修改的文件

| 文件 | 变更 |
|------|------|
| `tradingagents/astock/api/routes_backtest.py` | compare API 增强：在每个策略结果中添加 `equity_curve`（从 periods 提取 end_value）、`returns`（周期收益率）、`rank`（排名）。新增 `_composite` 评分函数：`0.5*Sharpe + 0.3*收益 - 0.2*回撤`。按评分降序排列并分配 rank。 |
| `tradingagents/astock/web/__init__.py` | 新增 `/comparison` 路由 → `comparison()` → `comparison.html` |
| `tradingagents/astock/web/templates/base.html` | 侧边栏在 Reports 和 Performance 之间插入 `🔀 对比 Comparison` 链接 |

### 新增的文件

| 文件 | 说明 |
|------|------|
| `tradingagents/astock/web/templates/comparison.html` | 完整策略对比页面（~350 行，13910 字节） |

### 核心设计

- **输入面板**：列出所有注册策略（checkbox 多选），全选/清除按钮，Symbol + 日期 + Mock 开关
- **排名表格**：按综合评分排序，Top 1 高亮（indigo 背景），排名 badge（🥇🥈🥉）
- **净值曲线叠加**：Chart.js 多线折线图，10 条不同配色，冠军加粗（2.5px vs 1.5px）
- **指标对比图**：
  - 收益/Sharpe 柱线组合图（条形 + 折线双 Y 轴）
  - 回撤/胜率柱线组合图（条形 + 折线双 Y 轴）
- 所有图表 dark 主题适配

### API 契约

**`GET /api/v1/backtest/compare`**

查询参数：`strategies`（逗号分隔）、`symbol`、`start`、`end`、`mock_data`

返回格式：
```json
{
  "comparison": [
    {
      "strategy_name": "BullTrend",
      "total_return": 0.12,
      "annualized_return": 0.45,
      "sharpe_ratio": 1.8,
      "max_drawdown": -0.08,
      "win_rate": 0.65,
      "total_trades": 10,
      "periods": [...],
      "equity_curve": [{"period": "2024-01", "value": 100000}, ...],
      "returns": [{"period": "2024-02", "return": 0.015}, ...],
      "rank": 1
    }
  ]
}
```

## 测试结果

### WebUI + API 测试
```
80 passed in 1.84s
```

### 回测/策略/优化器测试
```
81 passed, 40 subtests passed in 44.56s
```

### 页面 HTTP 验证
```
/comparison → 200 OK
/api/v1/backtest/compare → 200 OK, equity_curve + rank 字段正确
```

## 风险与注意事项

- 无 Breaking Changes — 新字段追加在原有响应中，旧客户端不受影响
- 首次加载 /comparison 时策略列表通过 `/api/v1/market/strategies` 动态获取
- 图表最多支持 10 种配色，超过 10 策略时会循环使用

## 下一阶段入口条件

无阻塞。可直接进入下一阶段。

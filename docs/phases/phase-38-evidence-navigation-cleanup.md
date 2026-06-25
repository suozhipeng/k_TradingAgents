# Phase 38 — Product Navigation Cleanup

## 目标顶层导航

```
Dashboard
├── AI Research Center
├── Strategy Lab
├── Market Leaders
├── Trading & Execution
├── Data & Ops
└── Portfolio Workbench
```

## 当前页面 → 目标导航映射

| 当前页面 | 目标模块 | 迁移动作 |
|----------|----------|----------|
| trading.html | Trading & Execution | 保持 |
| paper.html | Trading & Execution | 合并到 trading |
| risk.html | Trading & Execution | 合并到 trading |
| qmt.html | Trading & Execution | 保持 |
| strategy_hub.html | Strategy Lab | 保持 |
| strategies.html | Strategy Lab | redirect |
| momentum_rotation.html | Market Leaders | redirect |
| momentum_dashboard.html | Market Leaders | redirect |
| dragon_tiger.html | Market Leaders | redirect |
| northbound.html | Market Leaders | redirect |
| sectors.html | Market Leaders | redirect |
| research.html | AI Research Center | 保持 |
| ai_agent.html | AI Research Center | 合入 research |
| reports.html | AI Research Center | 保持 |
| data_health.html | Data & Ops | 保持 |
| dashboard.html | Dashboard | 保持 |
| kc_chart.html | Data & Ops | 保持 |
| tv_chart.html | Data & Ops | 保持 |
| settings.html | Data & Ops | 保持 |

## 旧入口迁移策略

| 策略 | 说明 |
|------|------|
| `redirect` | 301 重定向到目标模块 |
| `hidden` | 保留但不显示在导航中 |
| `legacy` | 保留旧 URL 但标记 deprecated |

## 完成标准

- 顶层导航收敛到 7 个目标模块 ✅
- 旧入口迁移策略明确 ✅

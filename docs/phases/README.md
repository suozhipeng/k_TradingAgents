# Delivery Phase 归档索引

本目录是 A 股 Delivery Phase 的本地权威归档。聊天记录、commit message 和零散 phase note 不能替代这里的归档记录。

## 1. 必需流程

每个 phase 都必须：

1. 创建或更新 `phase-XX-<slug>.md`。
2. 实现前记录 phase 目标和产品边界。
3. 实现后记录修改模块和行为变化。
4. 记录精确测试命令和结果。
5. 记录未解决风险和下一 phase 进入条件。
6. phase commit 完成后补充最终 Git commit SHA。
7. 同步更新本索引和 `docs/ASTOCK_CURRENT_STATUS.md`。

如果 commit SHA 在提交前未知，可以先写 `pending`，并在下一个文档 checkpoint 更新。

## 2. 归档索引

| Phase | 范围 | 状态 | 归档 / 证据 |
|---|---|---|---|
| 0 | 定位、边界、免责声明 | 完成 | [Phase 0](phase-00-boundary-blueprint.md) |
| 1 | Provider 选型、路由、fallback、缓存 | 完成 | [Phase 1](phase-01-provider-routing.md) |
| 2 | 五层 18 个能力点矩阵 | 基础完成 | [Phase 2](phase-02-capability-matrix.md) |
| 3 | Interface、tools、AStockAnalyst | 完成 | [Phase 3](phase-03-interface-analyst.md) |
| 4 | A 股研究链 graph bridge | 完成 | [Phase 4](phase-04-research-graph.md) |
| 5 | Research runtime 验证 | 完成 | [Phase 5](phase-05-research-runtime.md) |
| 6 | Research-only 入口分发 | 完成 | [Phase 6](phase-06-entry-dispatch.md) |
| 7 | 展示 schema 与 CLI | 完成 | [Phase 7](phase-07-schema-cli.md) |
| 8 | 只读 UI 与多市场 viewer | 完成 | [Phase 8](phase-08-readonly-viewer.md) |
| 9 | Trader、Risk、Portfolio Manager A 股适配 | 完成：advisory chain 接线、CLI/UI 渲染、runtime profile、62 项回归切片 | [Phase 9](phase-09-trader-risk-portfolio.md) |
| 10 | 回测与模拟盘 | 完成 | [Phase 10](phase-10-backtest-paper-trading.md) |
| 11 | QMT 桥接：只读到受控执行 | 完成 | [Phase 11](phase-11-qmt-controlled-execution.md) |
| 12 | DuckDB 本地数据库：10 表、CLI 工具、导入/导出 | 完成 | [Phase 12](phase-12-duckdb-local-database.md) |
| 13 | WebUI 国际化与市场切换：zh/en、LangSwitch、MarketSwitch | 完成 | [Phase 13](phase-13-webui-i18n-market-switch.md) |
| 14 | 六种回测策略：2 牛 / 2 震荡 / 2 熊 | 完成 | [Phase 14](phase-14-strategy-expansion.md) |
| 15 | Flask REST API + Chart.js + WebUI API client：19 端点 | 完成 | [Phase 15](phase-15-flask-api-chart-webui-client.md) |
| 16 | 批量回测、市场分析器、调度器、SSE：36 项测试 | 完成 | [Phase 16](phase-16-batch-backtest-scheduler-sse.md) |
| 17 | Flask Jinja2 WebUI 9 页面 + PPT 报告：54 项测试 | 完成 | [Phase 17](phase-17-flask-jinja-reporting.md) |
| 18 | 策略扩展 + 优化器：MACD、布林带、网格 + grid-search optimizer | 完成 | [Phase 18](phase-18-strategy-optimizer.md) |
| 19 | 绩效分析 + 数据刷新/缓存 + 测试重构：Chart.js，739/739 | 完成 | [Phase 19](phase-19-performance-refactor.md) |
| 20 | 策略对比 WebUI：compare API 增强，多策略 Chart.js 叠加 | 完成 | [Phase 20](phase-20-comparison-webui.md) |
| 21 | 测试稳定化：786/795 passed，0 failed，0 errors，4 次一致运行 | 完成 | [Phase 21](phase-21-test-stabilization.md) |
| — | WebUI risk/reports 页面升级 + mootdx 验证 + iwencai 文档 | 完成 | Phase 21 后 hotfix |
| 22 | KLineChart 全功能集成：替换 lightweight-charts，27 指标，17 画线工具，6 周期，mootdx 分钟数据，NaN 序列化修复 | 完成 | [Phase 22](phase-22-klinechart-integration.md) |
| 23 | 龙头股动量轮动决策系统：标的池、动量轮动策略、Streamlit + WebUI | 完成 | [Phase 23](phase-23-momentum-rotation.md) |
| 24 | AI Agent 分析页面：ai_agent.html | 完成 | [Phase 24](phase-24-ai-agent-page.md) |
| 25 | 股票筛选器 + 板块轮动：TradingView 风格筛选器、ECharts treemap 热力图 | 完成 | [Phase 25](phase-25-screener-sectors.md) |
| 26 | WebUI 全平台重构：Strategy Hub、sidebar 精简、Research v2、数据防爆 | 完成 | [Phase 26](phase-26-webui-refactor.md) |
| 27 | DataCleaner：全路径 NaN -> None 清理、`_coerce_float` 修复、`_clean_nan()` helper | 完成 | [Phase 27](phase-27-data-cleaner.md) |
| 28 | 新增 5 个 WebUI 页面：momentum dashboard、momentum rotation、dragon_tiger、northbound、data_health | 完成 | [Phase 28](phase-28-new-webui-pages.md) |
| 29 | 专业交易页：TradingView 风格交易控制台、实时报价、订单面板、KLineChart、持仓 | 完成 | [Phase 29](phase-29-trading-page.md) |
| 30 | Live Trading Readiness：交易能力边界、capability、runbook、kill switch | planned | [Phase 30](phase-30-live-trading-readiness.md) |
| 31 | Data Quality & Bias Control：数据质量、数据假设、回测反偏差 | planned | [Phase 31](phase-31-data-quality-bias-control.md) |
| 32 | Strategy Lab：策略、回测、优化、绩效、对比、动量轮动统一 | planned | [Phase 32](phase-32-strategy-lab-consolidation.md) |
| 33 | AI Research Center：AI Agent、研究、报告、模型审计统一 | planned | [Phase 33](phase-33-ai-research-center.md) |
| 34 | Market Leaders：龙头、板块、资金、候选池单入口 | planned | [Phase 34](phase-34-market-leaders-entry.md) |
| 35 | Trading & Execution：订单、成交、持仓、风控和 reconciliation | planned | [Phase 35](phase-35-trading-execution-control.md) |
| 36 | Portfolio Risk & Attribution：组合风险和绩效归因 | planned | [Phase 36](phase-36-portfolio-risk-attribution.md) |
| 37 | Ops & Audit Center：任务、错误、provider、模型和审计 | planned | [Phase 37](phase-37-ops-audit-center.md) |
| 38 | Product Navigation Cleanup：WebUI 顶层导航和旧入口收敛 | planned | [Phase 38](phase-38-product-navigation-cleanup.md) |

## 3. 命名规则

文件名使用小写 ASCII：

```text
phase-09-trader-risk-portfolio.md
phase-10-backtest-paper-trading.md
phase-11-qmt-controlled-execution.md
phase-12-duckdb-local-database.md
```

不要覆盖历史结果。后续工作改变早期结论时，应追加 dated correction section。

## 4. 协作治理

phase 归档由仓库级执行治理文档补充：

- [Hermes Skills Playbook](../HERMES_SKILLS_PLAYBOOK.md)
- [Hermes / Codex / DeepSeek 协作流程](../HERMES_CODEX_DEEPSEEK_WORKFLOW.md)
- [Phase 09 Hermes 执行 brief](phase-09-hermes-execution-brief.md)

涉及策略、回测、优化器、动量轮动和 Strategy Lab 的新 phase，必须同时参考 [A 股策略开发规范](../ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md)。

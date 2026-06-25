# A 股定制模块变更日志

遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 格式。
A 股定制部分使用独立的 `A-X.Y.Z` 版本号，与原 TradingAgents 的 `0.X.Y` 版本并行管理。

## [A-0.1.0] — 2026-06-23

### 新增
- Phase 0-29 全部完成交付
- 五层数据能力（行情、研报、新闻、基础数据、公告）
- 多 Agent 研究链（AStockAnalyst → Bull/Bear → Research Manager）
- advisory 决策链（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision）
- 回测引擎 + 模拟盘引擎 + QMT 桥接
- DuckDB 本地存储层（10 张表）
- Flask WebUI（22 个模板页面）+ Streamlit 只读 viewer
- CLI 报告渲染（Markdown/JSON/PPT）
- 10 种回测策略（2 牛 / 2 震荡 / 2 熊 + MACD / 布林带 / 网格）
- 策略参数优化器（grid search + 复合评分）
- 策略对比 WebUI
- 绩效分析 WebUI（Chart.js 净值/回撤/收益柱状图）
- KLineChart 全功能集成（27 技术指标 + 17 画线工具 + 6 周期）
- 龙头股动量轮动决策系统
- AI Agent 分析页面
- 股票筛选器 + 板块轮动热力图
- WebUI 全平台重构（Strategy Hub / sidebar 精简 / Research v2）
- 统一数据清洗层 DataCleaner（NaN→None 全路径防御）
- 专业交易页（TradingView 风格交易控制台）
- 5 个新增 WebUI 页面（动量终端/轮动看板/龙虎榜/北向资金/数据健康）
- 测试稳定化（786/795 passed, 0 failed, 0 errors）
- 数据源验证溯源机制（verification_provenance）
- live_research runtime profile 接入 DeepSeek

### 文档
- 完整 docs 体系（30+ 文档）
- PRD、Requirements、Tech Requirements、Backlog
- API Contracts、Backend API Reference
- Data Dictionary & Lineage、Data Migration & Upgrade
- Data Source License & Usage
- Model Governance、Risk Disclosure & Compliance
- Test Acceptance Plan、Release & Change Management
- Live Trading Runbook、Deployment & Environment
- WebUI Product Spec、WebUI Page Acceptance Checklist
- Document Scope Register、Project Risk Register
- Architecture Decision Records (8 项)
- Requirements Traceability Matrix（40+ 需求 ID）
- Product Optimization Roadmap（Phase 30-38）
- Development Progress & 5Min Plan
- Hermes Skills Playbook、Hermes/Codex/DeepSeek Workflow
- Strategy Development Guide
- Current Status、Phase 0-38 归档

### 修复
- 消除 `__path__=[]` 假包污染（Phase 19）
- NaN 全路径防御（adapters.py、routes_data.py、backtest 结果清洗）
- valuation 路由优化（tencent 优先 ~0.3s vs akshare ~26s）
- 买入逻辑 `net_cost <= cash` 防复发校验
- mootdx 0.11.7 本地验证通过
- 全仓回归稳定化（4 次连续一致通过）

### 已知限制
- QMT orders 查询仍为 mock/read-only 语义
- `/api/v1/trade/state` 属于 Paper Trading 路径
- 实盘账户/订单/成交 reconciliation 尚未闭环
- 策略/回测/优化/绩效/动量轮动尚未收敛到统一 Strategy Lab
- AI Agent/研究报告/新闻公告尚未收敛到统一 AI Research Center
- 龙头相关入口尚未收敛为单入口
- Phase 30-38 尚未实现

## [A-0.1.1] — 2026-06-26

### 变更
- 同步 `docs/` 与当前代码状态，修正文档中把 Phase 34/35 继续标为 `planned` 的漂移。
- 修复 `trade/order`、`trade/quote`、`market/sectors` 相关 API 回归，并补齐离线/受限环境下的稳定 fallback。
- 将 WebUI 规模口径更新为 `25` 个 HTML 模板，其中 `23` 个页面模板、`2` 个基础模板。
- 将 Flask API 规模口径更新为 `57` 个 route handler；Web 侧共有 `28` 个 route（含旧入口 redirect / alias）。
- 明确当前分支 `xg_dev` 与 `origin/xg_dev` 已同步；工作区当前存在未提交修改 `.hermes/dev-loop.yaml`。

### 验证
- 仓库内置 `.venv` 当前失效：`./.venv/bin/python3.10` 指向的解释器不存在，不能再直接作为“当前可用验证环境”写入状态文档。
- 使用系统 `Python 3.13.9` 验证：`tests/test_astock_phase31.py` 与 `tests/test_astock_phases_33_38.py` 共 `26 passed`。
- 覆盖全部 `63` 个测试文件的完整基线为：`1033` tests collected，`1019 passed, 14 skipped, 0 failed`。

### 已知限制
- `qmt/orders` 仍是 mock/read-only 语义，真实订单/委托查询尚未闭环。
- 仓库 `.venv` 仍未修复；当前通过系统 `Python 3.13.9` 完成验证。

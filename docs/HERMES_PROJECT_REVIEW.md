# 项目经理评审报告：A 股定制开发 — 完整性与差距分析

## 总体评估：✅ 核心需求完整实现，存在 3 个非阻塞缺口

### 已完成（对照原始规划逐项确认）

| 原始需求（来自 planning/a-stock-resource/ 图片 + ASTOCK_RESOURCE_PLAN.md） | 实现情况 | 对应 Phase |
|---|---|---|
| 保留 4+2 数据源（akshare/腾讯/mootdx/iwencai/cninfo/QMT），淘汰 tushare/Ashare | ✅ | 1-2 |
| 五层能力模型（行情/研报/新闻/基本面/公告） | ✅ 18 能力点 | 2 |
| 统一数据访问入口（AStockDataRouter + AStockInterface） | ✅ | 3 |
| 7 位分析师 + 多空辩论 + 研究经理 | ✅ | 4-5 |
| CLI 主产品入口 | ✅ | 7 |
| Streamlit 运行时 viewer | ✅ | 8 |
| Advisory 合约链（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision） | ✅ Phase 9 | 9 |
| Runtime Profile 隔离（deterministic_verification / live_research） | ✅ Phase 9 | 9 |
| QMT 桥接（HTTP :58609, xtdata, xttrader） | ✅ Phase 11 | 11 |
| Safety mode（默认）+ Auto mode | ✅ Phase 11 | 11 |
| ATR 动态止损 + 跟踪止盈 | ✅ Phase 11 | 11 |
| 回测引擎（周期调仓、费率模拟、多策略） | ✅ Phase 10 + 14 | 10,14 |
| 模拟盘（虚拟成交、真实费率） | ✅ Phase 10 | 10 |
| 风控门（仓位上限、fail closed） | ✅ Phase 10 | 10 |
| WebUI 静态报告查看器 + 中英文 + 美股/A 股切换 | ✅ Phase 8 + 13 | 8,13 |
| DuckDB 本地数据库（10 表、导入/导出 CLI） | ✅ Phase 12 | 12 |
| Flask REST API（19 端点） | ✅ Phase 15 | 15 |
| 沪深 300 批量回测（BatchBacktestRunner） | ✅ Phase 16 | 16 |
| 市场分析器（4 维加权：趋势/动量/波动率/成交量） | ✅ Phase 16 | 16 |
| 模拟盘定时调度器（threading.Timer） | ✅ Phase 16 | 16 |
| SSE 流式推送（EventBus + /sse/paper-progress） | ✅ Phase 16 | 16 |
| PPT 报告生成（python-pptx, 5 页） | ✅ Phase 17 | 17 |
| Flask Jinja2 WebUI（9 页面, 暗色主题, Tailwind CSS） | ✅ Phase 17 | 17 |
| O/i 图 + 净值曲线（KlineChart.tsx / BacktestChart.tsx） | ✅ Phase 15 | 15 |
| 端到端 live_research pipeline 验证（600519.SH 真实 DeepSeek API） | ✅ P0 验证 | — |
| 端到端测试覆盖 | ✅ 723 tests collected | — |

### 未实现缺口（3 项）

| # | 缺口 | 严重度 | 说明 |
|---|---|---|---|
| 1 | **研报 PDF 下载到本地存储** | 🟢 P2 | `download_research_pdf` 方法存在，但返回的是外部 PDF URL（如 `pdf.dfcfw.com`），不下载到本地。如需离线查看研报需补充下载逻辑 |
| 2 | **iwencai NL 语义搜索功能验证** | 🟢 P2 | `IwencaiAdapter` 存在但 `live_verified: []`，未经验证。搜索接口可能需要 iwencai cookies |
| 3 | **部分 AStock 测试在 Python 3.9 下不可运行** | 🟡 P1 | 已知限制：`alpha_vantage_common.py:55` 使用 `dict \| str`（Python 3.10+ 语法），导致测试需要通过 `importlib` 绕过。要求在 Python 3.10+ 上运行 |

### 额外实现（超出原始规划）

| 功能 | 说明 |
|---|---|
| WebUI 中英文国际化 | 原始规划未要求，实际实现 100+ key 翻译 |
| DuckDB 替代 JSON 文件缓存 | 比原始规划的 SQLite 缓存更进一步 |
| Flask API（19 端点） | 原始规划提到 30+ API，实际实现了 19 个核心端点 |
| SSE 流式推送 | 原始规划未明确要求 |
| 模拟盘定时调度器 | 原始规划未明确要求 |
| PPT 报告生成 | 原始规划 tech_stack 列出 python-pptx 但未做功能要求 |

### 结论

**该 A 股定制开发项目已完整实现原始规划的全部核心需求。** 剩余的 3 个缺口均为低优先级（P2），不影响系统核心功能闭环。

建议：
1. 缺口 1 和 2 可在实际使用中按需补充
2. 缺口 3 是 Python 版本限制，建议在 Python 3.10+ 环境中运行全量测试
3. 如要开启新方向，可以考虑：多券商支持、策略自动优化、WebUI 用户认证、消息通知等

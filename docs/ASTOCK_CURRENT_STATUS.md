# A 股二次定制开发基线

|更新时间：2026-06-25 (Phase 0-38 主体完成 + 944 tests passed) |

本文档是 A 股二次定制开发的当前事实基线。后续 Hermes 调度、ECC
验收和阶段推进优先以本文档为准。

每个 Delivery Phase 的详细记录必须归档到
`docs/phases/`。归档索引见 `docs/phases/README.md`。

专业金融开发缺口、代码边界和 WebUI 重构设计见
`docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md`。该设计明确：当前系统可用于
投研分析、策略验证、模拟盘和受控执行试运行，但尚不等同于完整实盘
生产交易系统。

## 1. 当前定位

当前系统是一个支撑全链路 A 股投资工作流的系统：
- Phase 0-9：只读研究与展示链路
- Phase 10：回测验证与模拟盘试跑
- Phase 11：QMT 桥接与受控执行（安全模式默认）
- Phase 12：DuckDB 本地数据库（持久化存储层）
- Phase 13：WebUI 国际化与市场切换（中英双语 + 美股/A 股切换）
- Phase 14：十种回测策略（2 牛 / 2 震荡 / 2 熊 + MACD 趋势 + 布林带均值回归 + 网格交易）
- Phase 15：Flask REST API + Chart.js 图表 + WebUI API 客户端（30 端点）
- Phase 16：批量回测 + 市场分析器 + 定时调度 + SSE 流式推送
- Phase 17：Flask Jinja2 WebUI 10 页面 + PPT 报告生成
- Phase 18：十种回测策略 + 策略参数优化器（MACD 趋势 / 布林带均值回归 / 网格交易 + StrategyOptimizer 网格搜索）
- Phase 19：绩效分析 WebUI（Chart.js 图表） + 数据刷新/缓存管理 + 测试重构全回归 739/739

已打通的主路径：

```text
AStockDataRouter
  -> AStockInterface
  -> AStockAnalyst
  -> Bull Researcher
  -> Bear Researcher
  -> Research Manager
  -> AStockGraphReport
  -> CLI / Streamlit read-only viewer
  -> Advisory chain (ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision)
  -> BacktestEngine / PaperTrader (Phase 10)
  -> QMTAdapter / QmtExecution (Phase 11, managed mode)
```

Phase 11 的默认执行模式是 **safety mode**（人工确认），auto mode 需用户显式开启。QMT 桥接不可用时自动降级到模拟盘路径。所有执行路径均保持 `actionable=false` 和 `execution_signal=ResearchOnly` 标记，直到人工确认放行。

## 2. 安全边界

`AStockGraphRuntime` 当前仍允许使用确定性的 `BridgeLLM` 做离线验证。
因此其研究链路输出必须标记为：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

兼容字段 `final_trade_decision` 只供旧报告结构展示，不代表可执行交易
决策。`TradingAgentsGraph` 不得把该字段传给通用信号解析器，也不得将
其写入交易决策记忆。

Phase 11 执行层增加了额外的安全边界：

- **Safety mode（默认）**：每次执行操作需要人工确认（`confirmed=True`）。
- **Auto mode**：用户显式通过配置或 CLI 参数开启，风险自担。
- **ATR 止损层**：实时计算 ATR 止损线，触发时自动拒绝下单，不依赖
  人工判断。
- **QMT 降级**：QMT 桥接不可用时自动走模拟盘路径，不中断分析链。
- **一切执行输出均保持 `actionable=false`**：直到 safety mode 下人工
  确认后才转为可执行信号。

## 3. Delivery Phase

| Phase | 范围 | 状态 |
|---|---|---|
| 0 | 定位、边界、免责声明 | 完成 |
| 1 | Provider 选型、路由、fallback、缓存 | 完成 |
| 2 | 五层 18 个能力点矩阵 | 完成基础实现 |
| 3 | `AStockInterface -> tools -> AStockAnalyst` | 完成 |
| 4 | A 股研究链 graph bridge | 完成 |
| 5 | 可重复执行的 research runtime | 完成 |
| 6 | `TradingAgentsGraph.propagate()` research-only 分发 | 完成 |
| 7 | 展示 schema 与 CLI 渲染 | 完成 |
| 8 | Streamlit 只读 UI 与 legacy 多市场 viewer | 完成 |
| 9 | Trader / Risk / Portfolio Manager A 股适配 | 规格完成，实现完成—A 股 advisory chain 接线、CLI/UI 渲染、runtime profile 隔离、62 项回归通过 |
| 10 | 回测与模拟盘 | 完成 |
| 11 | QMT 只读桥接到受控执行 | 完成 |
| 12 | DuckDB 本地数据库（10 表，CLI 工具，导入/导出） | 完成 |
| 13 | WebUI 国际化 + 市场切换（zh/en, LangSwitch, MarketSwitch） | 完成 |
| 14 | 十种回测策略（2 牛 / 2 震荡 / 2 熊 + MACD 趋势 + 布林带均值回归 + 网格交易） | 完成 |
| 15 | Flask REST API + Chart.js + WebUI API 客户端（30 端点） | 完成 |
| 16 | 批量回测 + 市场分析器 + 调度器 + SSE（36 项测试） | 完成 |
| 17 | Flask Jinja2 WebUI 10 页面 + PPT 报告（54 项测试） | 完成 |
| 18 | 策略扩展 + 参数优化器（3 新策略 + grid search + API + WebUI） | 完成 |
| 19 | 绩效分析 + 数据刷新/缓存 + 测试重构（Chart.js + 全回归 739/739） | 完成 |
| 20 | 策略对比 WebUI — compare API 增强（equity_curve/rank），多策略 Chart.js 叠加 | 完成 |
| 21 | 测试清噪与全仓回归稳定化 — 786 passed, 9 skipped, 0 failed, 0 errors | 完成 |
| 22 | KLineChart 全功能集成 — 替换 lightweight-charts, 27 技术指标, 17 画线工具, 6 周期切换, mootdx 分钟数据, NaN 序列化修复, TV Charting Library datafeed 准备 | 完成 |
| 23 | 龙头股动量轮动决策系统 — 标的池动态获取(东财优先), 动量轮动策略, Streamlit 独立看板, WebUI 集成 | 完成 |
| 24 | AI Agent 分析页面 — ai_agent.html 独立页面 | 完成 |
| 25 | 股票筛选器 + 板块轮动 — TradingView 风格筛选器, 板块热力图(ECharts treemap), 板块轮动页面(OpenStock 重构) | 完成 |
| 26 | WebUI 全平台重构 — 回测平台重构 + 交易主页报价联动 + Strategy Hub(三位一体策略控制台) + Sidebar 精简 + Research 专业量化终端 v2 + 数据防爆/科学计数法封杀 | 完成 |
| 27 | 统一数据清洗层 (DataCleaner) — 全路径 NaN→None 清理, _coerce_float 修复, _parse_financials 修复 | 完成 |
| 28 | 动量决策终端 / 动量轮动独立看板 / 龙虎榜 / 北向资金 / 数据健康页面 — 5 个新增 WebUI 页面 | 完成 |
| 29 | 专业交易页 — TradingView 风格交易控制台, 实时报价, 订单面板, KLineChart, 仓位管理, PaperTrader 桥接 | 完成 |
| 30 | Live Trading Readiness — 实盘准入清单与证据 | planned |
| 31 | Data Quality & Bias Control — 数据质量与回测反偏差 | 大部分完成（31-03/04 数据源不稳定 marked planned） |
| 32 | Strategy Lab Consolidation — 策略实验室整合 | 完成（含参数优化 tab） |
| 33 | AI Research Center — AI 研究中枢 | 完成（含降级横幅、报告对比、advisory-only） |
| 34 | Market Leaders Entry — 龙头股单入口 | planned |
| 35 | Trading Execution Control — 交易执行控制 | schema 已定义，实现 planned |
| 36 | Portfolio Risk & Attribution — 组合风险与归因 | 完成（schema + Portfolio 页面） |
| 37 | Ops & Audit Center — 运维审计中心 | 完成（SSE TaskRun 标准化 + Ops Audit 页面） |
| 38 | Product Navigation Cleanup — 产品导航清理 | 完成（7 模块 sidebar） |

## 4. 已完成能力

- A 股 symbol 标准化。
- 五层数据路由：行情、新闻、基本面、公告、研报。
- Provider fallback、统一错误语义和分桶缓存。
- Fixture provider 测试与可选 live provider 测试。
- A 股分析师结构化 section 输出。
- Bull / Bear / Research Manager 研究桥接。
- `AStockGraphReport` 统一展示 schema。
- CLI Markdown/JSON 报告。
- Streamlit 只读 viewer。
- Legacy generic finance 输出的共享 viewer dispatcher。
- A 股 Phase 09 advisory-only 合约 schema（ResearchConclusion, TraderProposal, RiskDecision, PortfolioDecision）。
- Runtime profile 隔离（deterministic_verification / live_research），
  包括 `require_live_research_clients` 防 BridgeLLM fallback。
- A 股 `live_research` 启动链已接入 `DEFAULT_CONFIG`、CLI、Streamlit 和
  repo-local 环境校验脚本。
- `AStockGraphReport` 扩展：runtime_profile、research_conclusion 等 advisory 字段。
- Phase 09 advisory chain：`ResearchConclusion -> TraderProposal -> RiskDecision -> PortfolioDecision`。
- CLI Markdown/JSON 与 Streamlit read-only viewer 已渲染 Phase 09 advisory 字段。
- Phase 09 合约验证 46 项测试通过。
- **3 个新策略**：MACD 趋势跟踪、布林带均值回归、网格交易（共 10 策略）
- **策略参数优化器**：`StrategyOptimizer` grid search + 默认搜索空间 + `POST /backtest/optimize`
- **WebUI 策略优化面板**：策略选择、日期范围、Top N、排名结果表格
- **绩效分析 WebUI**：Chart.js 净值曲线、回撤曲线、周期收益柱状图、信号分布图
- **数据刷新 API**：`POST /data/refresh/kline|valuation|all` — 手动拉取 provider → DuckDB
- **缓存管理 API**：`GET /cache/status` + `POST /cache/clear`
- **valuation 路由优化**：tencent 优先（~0.3s vs akshare ~26s），PB/market_cap 非空
- **测试重构**：11 个测试文件消除 `__path__=[]` 假包污染，全仓回归 739/739
- **运行脚本**：`run_webui.py`（`PORT=8080 python run_webui.py`）
- **策略对比 WebUI**：多选策略同参数运行，排名表格 + Chart.js 净值曲线叠加 + 指标对比图（Phase 20）
- **全仓回归稳定化**：4 次连续全仓 pytest 一致通过 786/795（9 skipped），0 failed，0 errors（Phase 21）
- **风控仪表盘升级**：risk.html 从 61 行升级为 200+ 行专业风控中心（规则表、ATR 止损、集中度图、告警日志、拦截记录、风险指标 Cards）
- **报告中心升级**：reports.html 从 75 行升级为 200+ 行报告管理页面（多类型报告生成、历史列表、搜索过滤、下载中心、服务状态）
- **mootdx 验证通过**：mootdx 0.11.7 本地通达信连接已验证（600519.SH 实时 K 线），移除 blueprint TODO
- **iwencai 文档完善**：补充 iwencai cookie 获取步骤到 `docs/ASTOCK_LIVE_RESEARCH_SETUP.md`
- **KLineChart 全功能集成**：27 个技术指标（MA/EMA/BOLL/MACD/KDJ/RSI 等）、17 个画线工具、6 周期切换（1m/5m/30m/60m/日/周/月）、十字光标信息面板、实时更新
- **龙头股动量轮动系统**：标的池动态获取（东方财富优先）、动量轮动策略（多因子评分）、Streamlit + WebUI 双入口
- **AI Agent 分析页面**：独立 ai_agent.html 页面
- **股票筛选器**：TradingView 风格筛选面板，支持 RSI/MA/MACD 金叉死叉/成交量比等指标条件
- **板块轮动页面**：ECharts treemap 热力图 + 板块排行（涨跌幅/资金流）、OpenStock 重构
- **WebUI 全平台重构**：Strategy Hub（三位一体策略研究控制台：回测 + 绩效 + 对比）、Sidebar 导航精简去重（Backtest/Performance/Compare → Strategy Hub）、交易主页报价联动、Research 专业量化终端 v2（KLineChart + 工具条 + 指标栏 + 网格布局）、数据防爆 + 科学计数法封杀 + 红涨绿跌统一
- **统一数据清洗层 DataCleaner**：全路径 NaN→None 清理（routes_data/_coerce_float/_parse_financials）
- **动量决策终端**（momentum_dashboard.html）：龙头股动量实时看板
- **动量轮动独立看板**（momentum_rotation.html）：轮动策略独立页面
- **龙虎榜**（dragon_tiger.html）：个股主力资金追踪
- **北向资金**（northbound.html）：沪深股通资金流
- **数据健康页**（data_health.html）：数据源状态监控面板
- **WebUI 总页面数**：22 个活跃页面（templates/ 目录）
- **NaN 全路径防御**：adapters.py _coerce_float 修复、routes_data.py _clean_nan() 模块级防护、backtest 结果清洗

## 4. 当前状态快照（2026-06-25）

### 基本信息
- **分支**: `xg_dev`，已同步远程 `origin/xg_dev`，领先 37 个提交
- **工作区**: 干净，无待提交修改
- **测试**: **944 passed, 14 skipped, 0 failed** — 全量回归稳定
- **WebUI**: 22 个活跃页面，Flask REST API 30+ 端点
- **交付阶段**: Phase 0-38，其中 Phase 30-38 大部分已完成

### 已完成的核心能力（Phase 0-29 + 30-38 大部分）
- ✅ 五层数据路由（行情/研报/新闻/基础数据/公告）
- ✅ A 股分析师 + Bull/Bear 辩论 + Advisory Chain
- ✅ 回测引擎（10 策略 + 参数优化 + 涨跌停/停牌/ST/退市约束）
- ✅ 模拟盘引擎（定时调度 + 虚拟成交 + SSE 推送）
- ✅ QMT 桥接（安全模式默认 + 人工确认）
- ✅ WebUI 22 页面 + Flask REST API 30+ 端点
- ✅ KLineChart 全功能（27 技术指标 + 17 画线工具）
- ✅ 动量轮动系统 + 股票筛选器 + 板块热力图
- ✅ 统一数据清洗层（DataCleaner）
- ✅ AI Research Center（ResearchTask + Audit + 降级标识 + 报告对比）
- ✅ 策略中心（Strategy Hub + 参数优化）

### 待开发项

#### 🔴 P0 — 数据源相关（planned，阻塞中）
| 任务 | 说明 |
|------|------|
| **31-03 停复牌处理** | 数据源不稳定，需自定义 adapter |
| **31-04 涨跌停处理** | 数据源不稳定，需自定义 adapter |
| **31-05-02 除权除息因子记录** | 数据源受限 |
| **31-07-03 幸存者偏差回测页面展示** | 后端检测已完成，前端待实现 |
| **31-08-03 前瞻偏差回测页面展示** | 后端检测已完成，前端待实现 |

#### 🟡 P1 — 功能完善
| 任务 | 说明 |
|------|------|
| **38-02~10 文档同步** | 导航清理后 wiki 更新 |
| **NFR-05~NFR-19** | 非功能性需求（可观测性/API契约/数据字典/测试发布门槛/合规/模型治理/WebUI一致性/数据迁移/页面验收/风险管理/ADR）— 全部 marked `planned` |

#### 🟢 P2 — 路线图后续阶段（Product Roadmap Stage，未开始）
| Phase | 范围 | 状态 |
|-------|------|------|
| **Phase 34** Market Leaders 单入口 | 龙头动量/轮动/板块强弱/资金线索/候选池整合 | `planned` |
| **Phase 35** Trading Execution 闭环 | 订单/成交/持仓/对账 schema 已定义，实现待开发 | `planned` |
| **Phase 36** Portfolio Risk & Attribution | 组合风险/归因 schema 已完成，页面待完善 | `partial` |
| **Phase 37** Ops & Audit Center | SSE TaskRun 标准化已完成，审计页面待增强 | `partial` |
| **Phase 38** Product Navigation Cleanup | 导航清理已完成，文档同步待完成 | `partial` |

#### ⚪ P3 — 实盘相关（暂不处理）
| 任务 | 说明 |
|------|------|
| **BL-000~BL-004** | 实盘账户/持仓/委托/成交/撤单/拒单 — 明确暂不处理 |

### 总结
当前项目**主体功能已基本完成**，剩余待开发项主要集中在：
1. **数据源不稳定导致的阻塞项**（停复牌、涨跌停、除权因子）— 等待可靠数据源
2. **前端展示补齐**（幸存者偏差/前瞻偏差页面）
3. **非功能性需求**（15+ 项 NFR，属于工程质量类）
4. **实盘相关**（BL-000~BL-004）明确暂缓

整体来看，系统已达到**投研分析 + 回测验证 + 模拟盘试跑**的完整闭环，具备从研究到受控执行的能力。

---

## 5. 当前缺口

### 专业评审摘要（2026-06-23）

从专业金融开发者角度看，当前系统仍需补齐以下闭环，才能从“实盘辅助分析/受控试运行”进入“实盘生产系统”口径：

- 实盘账户、持仓、委托、成交、撤单、拒单、部分成交和券商回报 reconciliation。
- kill switch、硬风控、权限控制、审计日志、异常恢复和运行监控。
- 交易日历、停复牌、涨跌停、复权、除权除息、ST、退市和数据质量分级。
- 回测反偏差：survivorship bias、look-ahead bias、未来函数、涨跌停不可成交、停牌不可成交。
- 组合级风险：行业暴露、集中度、相关性、Beta、流动性、容量、VaR、压力测试和绩效归因。
- Strategy Lab 模块整合：策略、回测、优化、绩效、对比、动量轮动统一注册和统一结果 schema。
- AI Research Center 模块整合：AI Agent、研究报告、新闻/公告/研报解读、模型/prompt/数据快照审计统一。
- Market Leaders 单入口：龙头动量、轮动回测、板块强弱、资金线索、候选池最多保留一个顶层入口。

后续执行入口以 `docs/ASTOCK_BACKLOG.md` 中的 `BL-000`、`BL-100`、`BL-100A`、`BL-100B` 为优先。

### 历史 P0 — 已完成 ✅

- 真实 LLM 与确定性验证 LLM 已通过 `RuntimeProfile` 形成强制隔离，
  且 `live_research` 启动链已部署。
- **环境变量注入已确认**：`.env` 包含 `DEEPSEEK_API_KEY`（35 字符有效值），
  `check_astock_live_research_env.py` 验证通过。
- **DeepSeek 实时 API 调用已验证**：`POST https://api.deepseek.com/chat/completions`
  返回 HTTP 200。
- **端到端 pipeline 验证已通过**：`scripts/verify_astock_live_pipeline.py` 对 `600519.SH`（贵州茅台）
  使用真实 DeepSeek 模型运行完整的 research→advisory chain（70 步），
  全部四个合约输出（ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision）
  均正确生成，`actionable=False` / `execution_signal=ResearchOnly` / `decision_scope=research_only`
  保持不变。

### 历史 P1 — 已完成 ✅

- `planning/codebase/` 模块图已同步 Phase 9-11 交付内容（commit `ce38370`）。
- Provider `live_verified` provenance 已修复：不再运行时合成假日期，使用
  `load_verification_provenance()` 从持久化记录读取或返回 `verified_on="unknown"`（commit `2888fde`）。
- WebUI/Streamlit 角色已明确：WebUI 为产品端入口，Streamlit 为运行时 viewer
  后端。WebUI 已实现 AStockGraphReport 报告查看器组件（commit `f218e84`）。
  两者保持独立代码库，不做全技术合并。
- `webui/` 目录下存在一个 React/TypeScript/Vite 前端实验项目（`webui/package.json`、`tsconfig`、`vite.config.ts`），当前未纳入产品主入口体系，定位为前端实验/迁移探索，不作为 Phase 30-38 验收范围。

### 历史 P2 — 口径说明

- “13 个接口”是原始材料口径；代码按五层拆成 18 个能力点。
  后续工程验收统一使用 18 个能力点，13 仅保留为来源说明。
  该事项已归档为后续规划参考，不在当前定制开发闭环范围内。

## 6. 历史入口条件与验证记录

以下为 Phase 10 启动前的历史入口条件，当前均已进入后续 phase 实现或归档，不再代表下一阶段入口：

1. 完成 Trader → Risk → Portfolio agent 接线，使 ResearchConclusion 能
   自然流向后继 advisory 合约。已完成。
2. 在 Python 3.10+ 环境中完成 A 股全回归（astock 回归 + 全仓回归）。
3. 部署 `live_research` runtime profile 的可运行验证环境。
   代码入口已完成；后续 live_research 部署回归已验证目标切片。
4. Phase 09 所有 advisory 输出保持 `actionable=false`、`execution_signal=ResearchOnly`。

产品与开发规格已归档到
`docs/phases/phase-09-trader-risk-portfolio.md`。当前 Phase 09 实现已包含
合约 schema、runtime profile 隔离、advisory chain 接线、CLI/UI 渲染与
目标测试通过。

2026-06-13 Phase 9 规格纠偏回归：

- Blueprint contract: `6 passed`
- A 股扩展回归: `50 passed`
- 全仓回归: `360 passed, 9 skipped`

2026-06-13 Phase 9 实现回归：

- Phase 09 合约测试: `46 passed` (Python 3.9, importlib bypass)
- A 股扩展回归: `50 passed` (基线；Phase 09 向后兼容)
- 全仓回归: 当前环境 Python 3.9，需 Python 3.10+ 执行

2026-06-14 Phase 9 接线 / 展示 / gate 回归：

- A 股回归切片: `62 passed`
- 覆盖范围: `tests/test_astock_graph_runtime.py`,
  `tests/test_astock_graph_bridge.py`, `tests/test_astock_interface_analyst.py`,
  `tests/test_astock_blueprint.py`, `tests/test_astock_data_sources.py`,
  `tests/test_astock_provider_fixtures.py`, `tests/test_astock_cli_report.py`,
  `tests/test_astock_ui_views.py`, `tests/test_hermes_codex_git_gate.py`

2026-06-14 live_research 部署回归：

- 目标切片: `48 passed`
- 覆盖范围: `tests/test_env_overrides.py`, `tests/test_astock_graph_runtime.py`,
  `tests/test_astock_cli_report.py`, `tests/test_astock_ui_views.py`

## 7. 验收基线

2026-06-22 Phase 22-28 增量验收：

```bash
source .venv/bin/activate && python -m pytest tests/test_astock_web.py tests/test_astock_api.py -q
```

结果：**150 passed, 0 failed, 0 errors**（WebUI + API 切片）。

全量回归状态（HEAD 7b7efef）：199 passed（A 股主链 9 切片），9 skipped（live provider / Pydantic BT 条件跳过），0 failed。

跳过项详情：
- 7 跳过：`test_astock_live_providers.py` — 需要 `ASTOCK_RUN_LIVE_TESTS=1` 环境变量
- 1 跳过：`test_astock_store.py:650` — 需要 `TEST_PYDANTIC_BT=1`
- 1 跳过：A 股切片中 `test_astock_store.py:650` 同上

0 failed / 0 errors。原始 baseline（2026-06-15: 636 passed, 2 failed, 76 errors）已完全收敛。

核心测试基础设施：
- `tests/conftest.py`：`ASTOCK_TESTING=1` 跳过反爬延迟 + `_dummy_api_keys` autouse fixture 注入 13 个 API key placeholder
- 无 `__path__=[]` 假包污染（Phase 19 已消除）
- 无需外部 API key、网络连接或特殊系统配置即可全仓运行

| 验收项 | 结果 |
|--------|------|
| WebUI + API 切片 (Phase 22-29 增量) | **150 passed, 0 failed, 0 errors** |
| A 股主链切片（9 文件） | **199 passed, 0 failed, 0 errors**（HEAD `7b7efef`） |
| 失败分桶 | 无 — 0 failed |
| 污染类缺陷 | 无（已消除 `__path__=[]` 假包、API key placeholder、`ASTOCK_TESTING=1`） |

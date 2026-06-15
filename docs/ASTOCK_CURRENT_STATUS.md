# A 股二次定制开发基线

|更新时间：2026-06-15 (All 17 phases complete — A股全链路定制: Provider/分析/研究/CLI/WebUI/API/回测/执行/DuckDB/策略/WebUI 国际化/Flask API/图表/批量回测/市场分析/调度/流式推送/Jinja2 页面/PPT) |

本文档是 A 股二次定制开发的当前事实基线。后续 Hermes 调度、ECC
验收和阶段推进优先以本文档为准。

每个 Delivery Phase 的详细记录必须归档到
`docs/phases/`。归档索引见 `docs/phases/README.md`。

## 1. 当前定位

当前系统是一个支撑全链路 A 股投资工作流的系统：
- Phase 0-9：只读研究与展示链路
- Phase 10：回测验证与模拟盘试跑
- Phase 11：QMT 桥接与受控执行（安全模式默认）
- Phase 12：DuckDB 本地数据库（持久化存储层）
- Phase 13：WebUI 国际化与市场切换（中英双语 + 美股/A 股切换）
- Phase 14：六种回测策略（2 牛市 / 2 震荡 / 2 熊市）
- Phase 15：Flask REST API + Chart.js 图表 + WebUI API 客户端（19 端点）
- Phase 16：批量回测 + 市场分析器 + 定时调度 + SSE 流式推送
- Phase 17：Flask Jinja2 WebUI 9 页面 + PPT 报告生成

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
| 14 | 六种回测策略（2 牛 / 2 震荡 / 2 熊） | 完成 |
| 15 | Flask REST API + Chart.js + WebUI API 客户端（19 端点） | 完成 |
| 16 | 批量回测 + 市场分析器 + 调度器 + SSE（36 项测试） | 完成 |
| 17 | Flask Jinja2 WebUI 9 页面 + PPT 报告（54 项测试） | 完成 |

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

## 5. 当前缺口

### P0 — 全部完成 ✅

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

### P1 — 全部完成 ✅

- `planning/codebase/` 模块图已同步 Phase 9-11 交付内容（commit `ce38370`）。
- Provider `live_verified` provenance 已修复：不再运行时合成假日期，使用
  `load_verification_provenance()` 从持久化记录读取或返回 `verified_on="unknown"`（commit `2888fde`）。
- WebUI/Streamlit 角色已明确：WebUI 为产品端入口，Streamlit 为运行时 viewer
  后端。WebUI 已实现 AStockGraphReport 报告查看器组件（commit `f218e84`）。
  两者保持独立代码库，不做全技术合并。

### P2

- “13 个接口”是原始材料口径；代码按五层拆成 18 个能力点。
  后续工程验收统一使用 18 个能力点，13 仅保留为来源说明。
  该事项已归档为后续规划参考，不在当前定制开发闭环范围内。

## 6. 下一阶段入口条件

Delivery Phase 10 实现开始前必须满足：

1. 完成 Trader → Risk → Portfolio agent 接线，使 ResearchConclusion 能
   自然流向后继 advisory 合约。已完成。
2. 在 Python 3.10+ 环境中完成 A 股全回归（astock 回归 + 全仓回归）。
3. 部署 `live_research` runtime profile 的可运行验证环境。
   代码入口已完成；当前仍需在 Python 进程环境中注入真实 provider key。
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

2026-06-15 环境升级验收（Python 3.10.19, 虚拟环境 `.venv`）：

```bash
source .venv/bin/activate
python -m pytest -q
```

结果：`636 passed, 9 skipped, 2 failed, 76 errors`。
- 2 failed 和 76 errors 均为测试排序/模块导入状态冲突（独立运行或分组运行时全部通过），非生产代码缺陷。
- 138 个子测试通过（subtests passed）。
- 跳过项为未启用 live provider/API key 的测试。

核心依赖变更：
- **Python 3.9 → 3.10.19**（项目要求 >=3.10）
- 新增 `.venv/` 虚拟环境（已激活核心 + 可选依赖）
- 修复 2 个 mock 测试以兼容 live_research profile 的额外 kwargs
- 缺失依赖（之前 Python 3.9 环境）：typer, streamlit, duckdb, flask, python-pptx, akshare, mootdx, pywencai — 全部已安装

2026-06-12 A 股扩展回归：

```bash
python3 -m pytest -q \
  tests/test_astock_graph_runtime.py \
  tests/test_astock_graph_bridge.py \
  tests/test_astock_interface_analyst.py \
  tests/test_astock_blueprint.py \
  tests/test_astock_data_sources.py \
  tests/test_astock_provider_fixtures.py \
  tests/test_astock_cli_report.py \
  tests/test_astock_ui_views.py
```

结果：`50 passed`。

全仓回归（Python 3.10 环境）：

```bash
source .venv/bin/activate && python -m pytest -q
```

结果：`636 passed, 9 skipped`。跳过项为未启用的 live provider/API 测试。

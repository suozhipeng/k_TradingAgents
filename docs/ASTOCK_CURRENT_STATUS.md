# A 股二次定制开发基线

更新时间：2026-06-14 (Phase 09 advisory chain + rendering + live runtime entry complete)

本文档是 A 股二次定制开发的当前事实基线。后续 Hermes 调度、ECC
验收和阶段推进优先以本文档为准。

每个 Delivery Phase 的详细记录必须归档到
`docs/phases/`。归档索引见 `docs/phases/README.md`。

## 1. 当前定位

当前系统是一个只读 A 股研究与展示链路，不是完整交易决策链，也不
包含自动下单能力。

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
```

当前 A 股路径不会进入：

- QMT order placement

但 Phase 09 已新增并接线 A 股 specific advisory 合约链：

```text
AStockGraphReport
  -> ResearchConclusion
  -> TraderProposal
  -> RiskDecision
  -> PortfolioDecision
  -> STOP (ResearchOnly)
```

当前 Phase 09 已包含 research conclusion 到 portfolio advisory 的状态接线，
并已在 CLI / Streamlit 只读展示层消费 advisory 字段。该链路仍保持
`ResearchOnly`，不会进入信号处理、交易记忆或 QMT。

## 2. 安全边界

`AStockGraphRuntime` 当前仍允许使用确定性的 `BridgeLLM` 做离线验证。
因此其输出必须标记为：

- `decision_scope=research_only`
- `actionable=false`
- `execution_signal=ResearchOnly`

兼容字段 `final_trade_decision` 只供旧报告结构展示，不代表可执行交易
决策。`TradingAgentsGraph` 不得把该字段传给通用信号解析器，也不得将
其写入交易决策记忆。

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
| 10 | 回测与模拟盘 | 未开始 |
| 11 | QMT 只读桥接到受控执行 | 未开始 |

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

### P0

- 真实 LLM 与确定性验证 LLM 已通过 `RuntimeProfile` 形成强制隔离，
  且 `live_research` 启动链已部署；当前主机仍缺实际 provider 环境变量 /
  API key 注入，因此还未完成真实 live 调用验证。

### P1

- `planning/codebase/` 的部分模块图仍以通用 TradingAgents 为主，需要
  持续同步 A 股模块。
- Provider `live_verified` 状态需要绑定测试日期和环境证据，不能只保留
  无日期的静态声明。
- WebUI 静态模块总览与 Streamlit runtime viewer 是两个独立前端，需要
  明确长期保留策略。

### P2

- “13 个接口”是原始材料口径；代码按五层拆成 18 个能力点。后续工程
  验收统一使用 18 个能力点，13 仅保留为来源说明。

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

全仓回归：

```bash
python3 -m pytest -q
```

结果：`360 passed, 9 skipped`。跳过项为未启用的 live provider/API 测试。

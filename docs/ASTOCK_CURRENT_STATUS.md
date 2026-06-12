# A 股二次定制开发基线

更新时间：2026-06-12

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

- Trader
- Aggressive / Conservative / Neutral Risk Analysts
- Portfolio Manager
- QMT order placement

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
| 9 | Trader / Risk / Portfolio Manager A 股适配 | 未开始 |
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

## 5. 当前缺口

### P0

- Trader、风险辩论、Portfolio Manager 尚未接入 A 股链路。
- 真实 LLM 与确定性验证 LLM 尚未形成强制的 runtime profile 隔离。

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

Delivery Phase 9 开始前必须满足：

1. 定义 A 股 TraderProposal、RiskDecision、PortfolioDecision 的结构化
   schema。
2. 明确真实 LLM runtime profile，禁止生产入口隐式回退到 BridgeLLM。
3. 为研究结论、交易建议和可执行信号定义不同字段，禁止复用
   `final_trade_decision` 表达三种语义。
4. 增加 A 股完整链路测试，但仍保持 `actionable=false`。

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

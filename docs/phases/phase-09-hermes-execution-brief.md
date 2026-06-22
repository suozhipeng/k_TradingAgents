# Phase 09 Hermes 执行 Brief

## 1. 用途

本文档把 Phase 09 规格转换为 Hermes 可以直接执行的 brief，避免重新打开 scope 或重新解释产品边界。

配套阅读：

- `docs/phases/phase-09-trader-risk-portfolio.md`
- `docs/ASTOCK_CURRENT_STATUS.md`
- `planning/codebase/ARCHITECTURE.md`
- `docs/HERMES_SKILLS_PLAYBOOK.md`

## 2. Phase 状态

- Delivery phase：`9`
- 当前状态：`implementation_complete`
- 实现状态：`complete`
- 分支：`xg_dev`
- 执行模式：`research_only`
- 不可协商 guardrail：`actionable=false`

## 3. Hermes 分派

- 首要 skill：`tradingagents-core`
- phase 控制 skill：`astock-rollout-orchestrator`
- ECC 验证 skill：`ecc-self-test`
- 交付路由：
  - schema 和 runtime profile 工作保留在 `tradingagents/astock/`
  - regression 和 acceptance 保留在 `tests/`
  - 持久化交付证据保留在 `docs/phases/`

## 4. 任务目标

维护并扩展 Delivery Phase 09：A 股 advisory-only Trader、Risk、Portfolio 输出。

Hermes 必须把 A 股 runtime 从研究结论扩展到组合建议输出，但不得创建任何执行路径、信号处理路径、交易记忆写入路径或 QMT 路径。

## 5. 强制边界

Hermes 必须始终保持：

1. 每个 Phase 09 输出的 `actionable` 都是 `false`。
2. `execution_signal` 始终为 `ResearchOnly`。
3. `live_research` 在真实 LLM client 不可用时必须 fail closed。
4. `live_research` 不得回退到 `BridgeLLM`。
5. Phase 09 输出不得调用 signal processing。
6. Phase 09 输出不得把 completed trade decision 写入 memory。
7. Phase 09 输出不得调用 QMT 或任何 broker interface。
8. 通用股票和 crypto 路径行为不得变化。

## 6. 必需交付物

Phase 09 已把以下内容作为实现基线；后续工作必须保留：

1. 在 `tradingagents/astock/` 下新增 A 股专用 Phase 09 schema。
2. 增加明确 runtime profile：
   - `deterministic_verification`
   - `live_research`
3. 将 A 股研究结果适配为 `ResearchConclusion`。
4. 将 Trader 输出适配为 `TraderProposal`。
5. 将三类风险观点结构化合成为 `RiskDecision`。
6. 将 Portfolio Manager 输出适配为 `PortfolioDecision`。
7. 扩展 A 股 report/runtime payload，使 Phase 09 advisory 字段可被只读消费者渲染。
8. 增加或更新 contract、runtime profile 隔离、research-only stop condition 的测试。
9. 实现后更新 phase archive 证据。

## 7. 建议文件范围

除非代码检查发现 `tradingagents/astock/` 内有更合适的相邻模块，否则优先使用：

- `tradingagents/astock/`
  - Phase 09 contract module
  - runtime profile configuration
  - graph/runtime adaptation
  - report schema extension
- `tests/`
  - `tests/test_astock_phase9_contracts.py`
  - `tests/test_astock_graph_runtime.py`
  - advisory rendering 所需的聚焦回归
- `docs/`
  - `docs/phases/phase-09-trader-risk-portfolio.md`
  - `docs/phases/README.md`
  - `docs/ASTOCK_CURRENT_STATUS.md`

## 8. 验收测试

最小定向测试：

```bash
python3 -m pytest -q \
  tests/test_astock_phase9_contracts.py \
  tests/test_astock_graph_runtime.py
```

A 股回归：

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

如果 Phase 09 修改通用模块，运行全量回归：

```bash
python3 -m pytest -q
```

## 9. 必须断言

Hermes 不得在以下断言不成立时标记任务完成：

1. 四个 Phase 09 contract 都拒绝 `actionable=true`。
2. `live_research` 不会回退到 `BridgeLLM`。
3. Phase 09 run 在 signal processing 和 QMT 之前停止。
4. Phase 09 result 不会作为 completed trade decision 持久化。
5. provider 数据缺失时降级为 typed advisory result。
6. 通用非 A 股流程保持不变。

## 10. Hermes 输出格式

Hermes 应返回简洁 phase report，包含：

- 已修改文件
- 已运行测试
- 已验证关键断言
- 开放风险
- 下一入口条件
- 最终 commit SHA

Hermes 还必须持久化本地结果：

1. 更新 `docs/phases/phase-09-trader-risk-portfolio.md`
2. 更新 `docs/phases/README.md`
3. 更新 `docs/ASTOCK_CURRENT_STATUS.md`
4. 在归档中保留最终 commit SHA

## 11. 直接 Hermes 命令

```bash
hermes chat -q "Continue Delivery Phase 09 in TradingAgents. Follow docs/phases/phase-09-trader-risk-portfolio.md and docs/phases/phase-09-hermes-execution-brief.md. Load tradingagents-core first. Preserve the A-share advisory-only chain, keep actionable=false and execution_signal=ResearchOnly, extend Phase 09 rendering or validation only within scope, run ECC regression tests, update docs/phases archive plus docs/ASTOCK_CURRENT_STATUS.md, then commit on xg_dev." --skills tradingagents-core,astock-rollout-orchestrator,ecc-self-test
```

## 12. 修正记录

- 2026-06-13：将 Phase 09 规格转换为 Hermes 执行 brief，使实现可以在无 scope 歧义的情况下开始。
- 2026-06-13：修正直接 Hermes 调用方式为当前 `hermes chat` + `--skills` 形式，替换无效的 `--agent` 形式。
- 2026-06-23：中文化本文档，并补充 `tradingagents-core` 作为首要 skill。

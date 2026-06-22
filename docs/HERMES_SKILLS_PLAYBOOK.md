# Hermes Skills Playbook

本文档是本仓库的 Hermes skill 分派契约。它用于说明不同任务应加载哪些 skill，以及 Hermes、DeepSeek、Codex 的协作边界。

## 1. 目标

使用稳定的三层 skill 模型：

- `tradingagents-core`：项目级核心上下文，覆盖原 TradingAgents 多 Agent 架构、回测方法、风险指标、数据 provider 链、A 股展示约定和 WebUI 规则。
- A 股专项 skill：负责 provider、interface、tool、analyst、phase rollout 等 A 股交付任务。
- ECC 通用 skill：负责 review、回归、自测和验收。

## 2. 当前 skill 清单

### 项目级核心

- `tradingagents-core`

`tradingagents-core` 是推荐默认加载的项目级 skill。涉及以下内容时必须加载：

- 多 Agent 架构：researchers -> analysts -> risk_mgmt -> trader。
- 原 TradingAgents 底层 AI 分析能力保留边界。
- A 股 provider 链：mootdx -> akshare -> DuckDB/store。
- 回测引擎、策略生命周期、风险指标、Sharpe / VaR / Drawdown。
- Strategy Lab、WebUI 重构、A 股展示约定。
- 新增或修改策略、回测、优化器、动量轮动。

### A 股专项

- `astock-provider-delivery`
- `astock-analyst-delivery`
- `astock-rollout-orchestrator`

### ECC 通用

- `ecc-readonly-review`
- `ecc-self-test`

## 3. 分派规则

### Step 1：先加载项目级核心上下文

以下任务先加载 `tradingagents-core`：

- 梳理项目、重构模块边界、更新需求文档。
- 分析是否破坏原 TradingAgents 底层 AI 分析能力。
- 策略、回测、优化器、绩效、风险指标相关开发。
- WebUI 信息架构和模块归并。

### Step 2：按交付面加载 A 股专项 skill

使用 A 股专项 skill 的场景：

- provider 实现或验证：`astock-provider-delivery`
- `AStockInterface`、tools、analyst 接线：`astock-analyst-delivery`
- 分阶段 A 股 rollout：`astock-rollout-orchestrator`

### Step 3：按验收方式加载 ECC skill

使用 ECC skill 的场景：

- 静态验收、漂移检查、范围检查：`ecc-readonly-review`
- 回归执行、自测、失败分桶：`ecc-self-test`

### Step 4：Hermes 负责调度

当任务同时包含实现和验收：

1. Hermes 先加载 `tradingagents-core` 建立项目上下文。
2. Hermes 使用 `astock-rollout-orchestrator` 拆 phase。
3. DeepSeek 执行编码任务。
4. Codex 作为独立 review gate。
5. ECC skill 负责静态 review 或回归验证。
6. 结果写回 phase 归档和当前状态文档。

默认角色：

- `Hermes`：负责 phase 调度、任务拆解、进度控制。
- `DeepSeek`：默认编码引擎。
- `Codex`：独立 review gate，负责验证结论、检查漂移和纠偏。
- 如果 Codex 当前不可用，Hermes 只能按 `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` 中定义的 fallback 条件执行 review gate，并明确标记为 `Hermes fallback review`。

## 4. Strategy Lab 专项要求

`tradingagents-core` 已蒸馏出 Section 12 策略开发规范。仓库内长期落点是：

- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`
- `docs/ASTOCK_TECH_REQUIREMENTS.md` 的 Strategy Lab 章节
- `docs/ASTOCK_BACKLOG.md` 的 `BL-100`
- `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` 的 Strategy Lab 边界

涉及策略开发时必须检查：

- `StrategyBase -> generate_signals` 生命周期。
- Crossover / Deviation / Momentum / Threshold / Grid 五类信号模式。
- `execution/__init__.py`、`routes_backtest.py` 的 `_STRATEGY_REGISTRY`、`routes_market.py` 的 `AVAILABLE_STRATEGIES` 三处注册点。
- 优化器复合评分：`0.35 * Sharpe + 0.30 * Return - 0.25 * Drawdown + 0.10 * TradeFrequency`。
- 多股票组合策略应明确采用 Standalone 模式或 StrategyBase 兼容模式。
- baostock 批量拉取必须使用 `rs.next()` + `rs.get_row_data()` 游标模式。
- 买入逻辑必须防止含费用后的 `net_cost > cash`。
- 必须处理参数爆炸、NaN 预热、Mock 无趋势、未来函数和样本外验证缺失。

## 5. 持久化规则

需要进入 Git 的持久化结果：

- phase 归档：`docs/phases/`
- 当前事实基线：`docs/ASTOCK_CURRENT_STATUS.md`
- 需求和技术边界：`docs/ASTOCK_REQUIREMENTS.md`、`docs/ASTOCK_TECH_REQUIREMENTS.md`
- 策略规范：`docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`
- Hermes 可复用模板：`docs/hermes/`
- live provider 验证溯源：`docs/verification_provenance/`

不应进入 `docs/hermes/` 的运行态内容：

- 当前运行状态。
- 临时 blocker。
- 时间戳运行日志。
- 分支本地执行输出。

这些内容继续放在 `.hermes/`。

## 6. 验收治理

- 不接受只基于 DeepSeek 自述的 phase 结论。
- 以正确性、漂移、scope compliance 为主时使用 `ecc-readonly-review`。
- 以回归执行和失败分桶为主时使用 `ecc-self-test`。
- Codex 必须给出 `accept`、`partial` 或 `fail` 后，Hermes 才能把 phase archive 标记为 complete。
- Codex 返回 `accept` 且工作区可提交时，Hermes 应在 handoff 前提交通过 review 的文件。
- `scripts/hermes_codex_git_gate.py` 是本仓库的最终 gate 辅助命令。
- `scripts/hermes_phase_loop.sh` 是本仓库 backlog driver；最新机器可读输出保存在 `.hermes/`。

## 7. 当前 phase 映射

| Phase | 推荐 skill |
|---|---|
| 3 | `tradingagents-core` + `astock-analyst-delivery` + `ecc-self-test` |
| 4 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-readonly-review` |
| 5 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 6 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 7 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-readonly-review` |
| 8 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-readonly-review` |
| 9 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 10 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 11 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 12 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 13 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-readonly-review` |
| 14 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 15 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 16 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 17 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 18 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 19 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 20-29 | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| 30+ | `tradingagents-core` + 按模块选择 A 股专项 skill + ECC review/test |

canonical phase scope 和完成状态以 `docs/ASTOCK_CURRENT_STATUS.md` 为准。

## 8. 当前仓库边界

- 保留原 TradingAgents 底层 AI 分析能力，不主动重构 `tradingagents/agents/`、`tradingagents/graph/`、`tradingagents/llm_clients/`、`tradingagents/dataflows/` 的通用核心。
- A 股新增层、API、WebUI、执行层和文档可以按 phase 边界重构。
- 所有 A 股 advisory 输出默认保持 `actionable=false`，真实交易必须经过受控执行边界。
- 不要把当前 A 股 bridge 的 `final_trade_decision` 当成可执行信号。
- `docs/phases/` 是 milestone archive。
- `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` 是 controller、coder、reviewer 分工的 repo-level 协作契约。

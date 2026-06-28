# Hermes Skills — 分派契约

本文档是本仓库的 Hermes skill 分派契约。它用于说明不同任务应加载哪些 skill，以及当前可用的 Hermes skill 清单。

## 1. 目标

使用稳定的 skill 模型：

- `tradingagents-core`（项目级核心上下文）
- A 股专项 skill（provider、graph、WebUI、strategy）
- 通用 skill（review、debug、test、plan）

## 2. 当前 skill 清单

### 项目级核心

- `tradingagents-core` — 推荐默认加载。覆盖多 Agent 架构、回测方法、风险指标、数据 provider 链、A 股展示约定和 WebUI 规则。

### A 股专项

| Skill | 适用场景 |
|-------|---------|
| `astock-provider-delivery` | 新增或验证 A 股数据 provider |
| `astock-graph-runtime` | A 股研究链 graph bridge 构建 |
| `astock-webui-page` | 新增/修改 WebUI 页面 |
| `astock-db-development` | DuckDB/PostgreSQL/ClickHouse 数据库开发 |
| `astock-db-audit` | 数据库生产就绪审计 |
| `backtest-strategy-development` | 策略实现与优化 |
| `webui-engineering` | Flask/Jinja2 WebUI 工程 |

### 通用开发

| Skill | 适用场景 |
|-------|---------|
| `code-review-and-quality` | 多维度代码审查 |
| `test-driven-development` | TDD 流程 |
| `planning-and-task-breakdown` | 任务拆解与分派 |
| `debugging-and-error-recovery` | 根因调试 |
| `systematic-debugging` | 系统性问题诊断 |
| `finishing-a-development-branch` | 分支收尾与合并 |
| `verification-before-completion` | 完成前验证 |

## 3. 分派规则

### Step 1：先加载项目级核心上下文

以下任务先加载 `tradingagents-core`：

- 梳理项目、重构模块边界、更新需求文档。
- 分析是否破坏原 TradingAgents 底层 AI 分析能力。
- 策略、回测、优化器、绩效、风险指标相关开发。
- WebUI 信息架构和模块归并。
- **任何涉及 A 股数据、回测或 WebUI 的任务**。

### Step 2：按交付面加载专项 skill

| 任务类型 | 推荐 skill |
|---------|------------|
| 数据 provider 实现或验证 | `tradingagents-core` + `astock-provider-delivery` |
| 数据库层开发 | `tradingagents-core` + `astock-db-development` |
| 数据库审计 | `astock-db-audit` |
| 新 WebUI 页面 | `tradingagents-core` + `astock-webui-page` |
| 策略开发 | `tradingagents-core` + `backtest-strategy-development` |
| WebUI 工程 | `tradingagents-core` + `webui-engineering` |

### Step 3：按需要加载通用 skill

- 代码审查：`code-review-and-quality`
- 调试问题：`debugging-and-error-recovery` 或 `systematic-debugging`
- 分支收尾：`finishing-a-development-branch`
- 验证：`verification-before-completion`

## 4. 持久化规则

需要进入 Git 的持久化结果：

- phase 归档：`docs/phases/`
- 当前事实基线：`docs/phases/README.md`
- 需求和技术边界：`docs/04-dev/PRD.md`
- Hermes 任务包：`docs/04-dev/hermes-tasks.md`
- 策略规范：`docs/02-guide/strategy-dev.md`
- Hermes 可复用模板：`docs/hermes/`
- live provider 验证溯源：`docs/verification_provenance/`

不应进入 `docs/hermes/` 的运行态内容：

- 当前运行状态。
- 临时 blocker。
- 时间戳运行日志。
- 分支本地执行输出。

这些内容继续放在 `.hermes/`。

## 5. 验收治理

- 不以 agent 自述为 phase 完成结论。
- 需要独立 review gate 用于验收。
- Codex / 独立审查给出 `accept` | `partial` | `fail` 后，phase 才能标记为完成。
- `scripts/hermes_codex_git_gate.py` 是本仓库的最终 gate 辅助命令。
- `scripts/hermes_phase_loop.sh` 是本仓库 backlog driver。

## 6. 当前仓库边界

- 保留原 TradingAgents 底层 AI 分析能力，不主动重构 `tradingagents/agents/`、`tradingagents/graph/`、`tradingagents/llm_clients/`、`tradingagents/dataflows/` 的通用核心。
- A 股新增层、API、WebUI、执行层和文档可以按 phase 边界重构。
- 所有 A 股 advisory 输出默认保持 `actionable=false`，真实交易必须经过受控执行边界。
- 不要把当前 A 股 bridge 的 `final_trade_decision` 当成可执行信号。
- `docs/phases/` 是 milestone archive。
- `docs/hermes-workflow.md` 是 controller、coder、reviewer 分工的 repo-level 协作契约。

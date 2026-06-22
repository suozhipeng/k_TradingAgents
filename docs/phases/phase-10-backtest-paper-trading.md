# Phase 10：A 股回测验证与模拟盘运行时

## 元数据

- Status: `implemented`
- Product specification: `complete`
- Implementation: `complete`
- Started: `2026-06-14`
- Completed: `2026-06-14`
- Owner: `Hermes (DeepSeek)`
- Git branch: `xg_dev`
- Commit SHA: `a088465`

## 产品目标

在 A 股只读研究链路（Phase 3-9）的基础上，增加可执行的回测验证（backtest）与模拟盘试跑（paper trading）能力，使 A 股五层数据、研究结论和 advisory 合约链能投入历史验证和模拟环境运行。

Phase 10 的输出仍保持 `ResearchOnly` 标记，不涉及真实下单；但引入执行语义的建模（虚拟成交、费率、持仓、风控），为 Phase 11 QMT 受控执行提供已验证的执行层基线。

## 范围

### 包含

1. **回测引擎接入**：基于现有 A 股五层数据源，构建可重复执行的回测框架。
   - 数据准备：使用现有五层 provider（行情/研报/新闻/基本面/公告）获取历史数据
   - 策略定义：至少 1 个基准策略（如均线趋势），输出评分与信号
   - 调仓周期：可配置（日/周/月）
   - 费率模型：佣金 + 印花税 + 滑点（可配置）
   - 结果统计：收益率、夏普比率、最大回撤、胜率
   - 报表输出：Markdown 回测报告

2. **模拟盘运行时**：构建定时触发的模拟交易引擎。
   - 定时调度器：可配置调仓频率
   - 信号生成：从研究链路/advisory 合约链读取信号
   - 虚拟成交：按收盘价/均价虚拟成交
   - 仓位管理：持仓记录、市值计算
   - 费率扣减：按真实费率模拟
   - 实时进度：SSE 流式推送（与 WebUI 配合）

3. **风控规则集成**：将 Phase 9 的 RiskDecision 合约中的约束（position_cap_pct、constraints、review_triggers）映射为可执行的风控拦截规则。
   - 仓位上限拦截
   - 缺失数据降级（不通过、不交易）
   - Advisory-only 标记强制保留

4. **与现有架构的集成**：
   - 回测报告复用 `AStockGraphReport` 展示 schema（或扩展）
   - 模拟盘状态可通过现有 CLI/Streamlit viewer 只读展示
   - 不修改 Phase 3-9 的只读研究链路

### 排除

- QMT 桥接或真实券商接口 — 这是 Phase 11
- 实盘下单 — 任何路径不得产生真实交易
- 多策略自动选择/评分系统 — 基线与基准策略先行
- 全量 300 支股票回测（目标态素材）— 先跑通单股/少量股
- 回测结果自动选入模拟盘 — 初期人工选择
- Web UI 的实时进度展示 — 可预留接口但不在 Phase 10 完成
- Python 3.9 兼容 — 要求 Python 3.10+
- 修改 Phase 0-9 已完成的归档文档

## 架构映射

| ARCHITECTURE.md section | Module | Expected change |
|---|---|---|
| 1.3 当前 A 股只读链路 | `tradingagents/astock/` | 新增回测/模拟盘子模块 |
| 13 Target data flow | A-share runtime state | 扩展至回测输出和模拟盘状态 |
| 3.1 顶层分层（目标态） | 回测引擎 / 模拟盘引擎 | 新模块，不改变现有只读层 |
| 5 Agent 层 | Trader / Risk / Portfolio | 回测/模拟盘消费现有合约输出，不修改 Agent |

## 产品决策

1. **Delivery Phase 10 = 回测 + 模拟盘放在一个实现阶段**。理由：回测提供历史验证基线，模拟盘提供实时环境验证，两者共享数据层和风控规则，拆成两个 delivery phase 会导致重复接线。
2. **回测引擎不引入 Backtrader 等外部框架**，初期用纯 Pandas + NumPy 实现。理由：减少依赖风险，A 股回测逻辑（周期调仓、A 股费率模型）与通用回测框架的抽象层不一定对齐。
3. **模拟盘使用定时调度 + 虚拟券商接口模式**，不引入事件驱动回测。
4. **风控规则从 Phase 9 的 RiskDecision 合约中的 constraints/list 字段读取**，不另建规则 DSL。约束直接表达为 Python 断言式过滤函数。
5. **模拟盘使用已有 A 股 provider 获取实时/当日数据**（如 mootdx/腾讯实时行情），不单独建新的实时数据管道。
6. **所有回测/模拟盘输出保持 `actionable=false`、`execution_signal=ResearchOnly`**。Phase 10 不能产生可自动执行的交易信号。
7. **回测/模拟盘的代码放在 `tradingagents/astock/execution/` 子包下**，与现有的 research-only 层（interface, analyst, runtime）保持物理隔离。

## 实现记录

### 目标文件

| File | Purpose |
|---|---|
| `tradingagents/astock/execution/__init__.py` | New: execution subpackage, exports |
| `tradingagents/astock/execution/backtest_engine.py` | New: backtest orchestrator — data loader, strategy runner, P&L calc |
| `tradingagents/astock/execution/strategy_base.py` | New: strategy base class + benchmark strategy (moving avg trend) |
| `tradingagents/astock/execution/fee_model.py` | New: A-share fee model (commission + stamp tax + slippage) |
| `tradingagents/astock/execution/metrics.py` | New: performance metrics (return, Sharpe, max drawdown, win rate) |
| `tradingagents/astock/execution/paper_trader.py` | New: paper trading scheduler, virtual execution, position manager |
| `tradingagents/astock/execution/risk_gate.py` | New: risk constraint executor — reads RiskDecision constraints, applies filters |
| `tradingagents/astock/report.py` or similar | Extended: backtest/paper trading report schema, reuse or extend AStockGraphReport |
| `tests/test_astock_backtest.py` | New: backtest engine tests |
| `tests/test_astock_paper_trader.py` | New: paper trading runtime tests |
| `tests/test_astock_execution_risk_gate.py` | New: risk gate integration tests |
| `docs/phases/phase-10-backtest-paper-trading.md` | Updated: implementation archive |

### 行为契约

- **BacktestEngine**:
  - Input: symbol list, trade_date range, strategy config, fee config
  - Output: `BacktestResult` (symbol, periods, trades, metrics dict)
  - Degradation: missing data → skip period, record in log
  - Safety: no external network calls except existing provider layer

- **PaperTrader**:
  - Input: scheduled trigger, signal source (advisory chain or manual)
  - Output: `PaperTradeState` (positions, cash, P&L, open orders)
  - Degradation: missing current price → skip execution cycle, record warning
  - Safety: `actionable=false` on all sources; `execution_signal=ResearchOnly`

- **RiskGate**:
  - Input: `RiskDecision` constraints, current portfolio state
  - Output: `allow` / `block` with reason
  - Degradation: unparseable constraint → `block` (fail closed)
  - Safety: cannot be bypassed by caller

## ECC 验收

### 最小测试

```bash
python3 -m pytest -q \
  tests/test_astock_backtest.py \
  tests/test_astock_paper_trader.py \
  tests/test_astock_execution_risk_gate.py
```

### A 股回归（Phase 10 不能破坏既有路径）

```bash
python3 -m pytest -q \
  tests/test_astock_graph_runtime.py \
  tests/test_astock_graph_bridge.py \
  tests/test_astock_interface_analyst.py \
  tests/test_astock_provider_fixtures.py \
  tests/test_astock_cli_report.py \
  tests/test_astock_ui_views.py \
  tests/test_astock_backtest.py \
  tests/test_astock_paper_trader.py \
  tests/test_astock_execution_risk_gate.py
```

### 必需断言

1. Backtest results are deterministic (same input → same output).
2. Paper trader never executes a trade with `actionable=true`.
3. Risk gate blocks when constraints are missing or unparseable (fail closed).
4. Phase 3-9 existing tests still pass with Phase 10 code present.
5. No QMT or broker import paths exist in `tradingagents/astock/execution/`.
6. All execution outputs carry `decision_scope` and `actionable=false` metadata.

## 风险与缺口

- **回测框架设计**：纯 Pandas 实现可能在大规模数据（沪深 300 × 3.4 年）时性能不足。考虑初期只覆盖单/少量股票，后期评估是否引入专用引擎。
- **模拟盘实时数据依赖**：paper trader 获取当日行情依赖现有 provider 的实时能力，部分 provider（如 mootdx）在非交易时段可能不返回有效数据。
- **与现有架构的集成点**：如何从 advisory 合约链读取信号而不耦合 — 初期使用简单的 polling 模式，SignalProcessor 走线留到 Phase 11。
- **Python 3.10+ 需求**：Phase 10 的 Pandas/NumPy 基础与 Python 3.9 兼容，但推荐在 3.10+ 环境中运行和验证。
- **没有 WebUI 实时展示**：模拟盘的 SSE 进度推送仅预留接口，前端消费不在 Phase 10 scope 内。

## 下一 phase 进入条件（Phase 11：QMT 受控执行）

1. Phase 10 Codex accept 已获得。
2. 至少 1 组单股回测结果可复现。
3. 模拟盘至少完成 1 个调度周期（含信号生成→风控→虚拟成交→仓位更新）。
4. `execution/` 子包与 `research-only` 层物理隔离已验证。
5. Phase 10 所有输出保持 `actionable=false` 和 `execution_signal=ResearchOnly`。

## 修正记录

- 2026-06-14: Created the product specification draft.
- 2026-06-14: Implemented Phase 10 backtest engine, paper trader, risk gate,
  fee model, strategy base, and metrics — 7 new modules under
  `tradingagents/astock/execution/`. 49 tests across 3 test files, all passed
  (26 backtest + 12 paper trader + 11 risk gate). Codex acceptance audit
  passed. Product boundary (`actionable=false`, `execution_signal=ResearchOnly`,
  `decision_scope` separation) intact.

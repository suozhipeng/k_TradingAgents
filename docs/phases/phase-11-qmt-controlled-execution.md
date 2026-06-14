# Phase 11: QMT Bridge — Read-Only to Controlled Execution

## Metadata

- Status: `implemented`
- Product specification: `complete`
- Implementation: `complete`
- Started: `2026-06-14`
- Completed: `2026-06-14`
- Owner: `Hermes (DeepSeek)`
- Git branch: `xg_dev`
- Commit SHA: `pending`

## Product objective

将当前占位的 `QMTAdapter`（所有方法返回 "unavailable"）替换为真实的 QMT 桥接层，在受控模式下实现：
1. **只读数据接入**：通过 QMT（国金证券券商源）获取精确的实时/历史行情
2. **受控执行**：安全模式（默认）+ 人工确认 → QMT xttrader 下单
3. **风控集成**：ATR 动态止损、跟踪止盈、仓位约束实时生效

Phase 11 不是 "全自动实盘" — 默认模式是人工确认（safety mode），自动模式（auto mode）需要用户显式选择并承担风控后果。

## Scope

### Included

1. **QMTAdapter 替换**：将当前占位实现替换为真实的 QMT 桥接。
   - `get_kline`：通过 xtdata 读取本地历史 K 线
   - `get_order_book`：通过 xtdata 读取五档盘口
   - `get_trade_tape`：通过 xtdata 读取逐笔成交
   - `get_valuation`：通过 xtdata 读取实时估值
   - `get_fundamentals`：仍在 placeholder 阶段（QMT 不提供基本面数据）

2. **QMT 桥接架构**：
   - `QmtSource`（HTTP client）：主系统（Python 3.10+）侧，端口 `58609`
   - `qmt_bridge.py`：QMT 侧 Python 3.6.8 桥接脚本
   - `xtdata` 集成：Mini QMT（`:58610`）高速数据读取
   - `xttrader` 集成：全功能 QMT 下单接口

3. **受控执行层**（`tradingagents/astock/execution/qmt_execution.py`）：
   - 安全模式（默认）：所有下单请求需要人工确认
   - 自动模式：用户显式开启后才允许调度器自动下单
   - 信号转换：从 Phase 10 paper trader 信号 → QMT 下单参数
   - 下单记录：所有成交记录写入本地日志

4. **实盘风控**（扩展 `risk_gate.py`）：
   - ATR 动态止损（默认 10%）
   - 跟踪止盈（3% 激活）
   - 实时价格监控
   - 异常行情暂停交易

5. **配置与安全**：
   - `RuntimeProfile` 扩展：`production_execution` 模式
   - QMT 连接健康检查
   - 自动回退：QMT 不可用时自动走模拟盘路径

### Excluded

- 多券商支持 — 仅 QMT（国金证券）
- 全自动无确认交易 — safety mode 是默认且强制的
- Web UI 实盘控制面板 — 仅 CLI/配置驱动
- `RuntimeProfile.production_execution` 自动选择 — 必须人工显式选择
- 非交易时段执行 — 仅交易时段可用
- 策略层的实盘集成 — Phase 11 只做桥接和执行层，策略接入留给后续

## Architecture mapping

| Component | Path | Change |
|---|---|---|
| QMTAdapter | `tradingagents/astock/data_sources/adapters.py` | 替换占位实现为真实桥接 |
| QMT bridge | `tradingagents/astock/execution/qmt_bridge.py` | 新建：HTTP 桥接客户端 |
| QMT execution | `tradingagents/astock/execution/qmt_execution.py` | 新建：受控执行层 |
| Risk gate | `tradingagents/astock/execution/risk_gate.py` | 扩展：ATR 止损 + 跟踪止盈 |
| Runtime profile | `tradingagents/astock/runtime_profile.py` | 扩展：production_execution |
| Paper trader | `tradingagents/astock/execution/paper_trader.py` | 新增：与 QMT 执行层的接口 |

## Product decisions

1. **QMTAdapter 保持 `AStockAdapterBase` 接口**，不改变现有的五层 provider 路由逻辑。
2. **桥接层不依赖外部 HTTP 框架**，使用 Python 标准库 `http.server` / `urllib.request` 实现。
3. **执行层默认安全模式**：所有下单操作前必须经过人工确认为 `confirmed=true`。
4. **ATR 止损在本地计算**，不需要实时推送。每 tick 检查当前价格 vs 止损线。
5. **QMT 不可用时自动降级到模拟盘路径**（Phase 10 PaperTrader），不中断现有分析链。

## Implementation

### Target files

| File | Purpose |
|---|---|
| `tradingagents/astock/data_sources/adapters.py` | 修改：QMTAdapter 方法替换为真实实现 |
| `tradingagents/astock/execution/qmt_bridge.py` | 新建：HTTP 桥接客户端 + 协议定义 |
| `tradingagents/astock/execution/qmt_execution.py` | 新建：受控执行层（safety/auto mode） |
| `tradingagents/astock/execution/risk_gate.py` | 扩展：ATR 止损、跟踪止盈 |
| `tradingagents/astock/execution/paper_trader.py` | 扩展：QMT 执行集成接口 |
| `tradingagents/astock/runtime_profile.py` | 扩展：`production_execution` + safety guard |
| `tests/test_astock_qmt_bridge.py` | 新建：桥接协议测试 |
| `tests/test_astock_qmt_execution.py` | 新建：受控执行测试 |
| `docs/phases/phase-11-qmt-controlled-execution.md` | 更新：实现归档 |

## ECC acceptance

### Minimum tests

```bash
python3 -m pytest -q \
  tests/test_astock_qmt_bridge.py \
  tests/test_astock_qmt_execution.py
```

### A-share regression

```bash
python3 -m pytest -q \
  tests/test_astock_graph_runtime.py \
  tests/test_astock_graph_bridge.py \
  tests/test_astock_interface_analyst.py \
  tests/test_astock_provider_fixtures.py \
  tests/test_astock_backtest.py \
  tests/test_astock_paper_trader.py \
  tests/test_astock_execution_risk_gate.py \
  tests/test_astock_qmt_bridge.py \
  tests/test_astock_qmt_execution.py
```

### Required assertions

1. QMTAdapter 不再返回 "unavailable"（至少 K 线和盘口数据可用）。
2. Safety mode 下任何 `execute()` 调用必须等待 `confirmed=True`。
3. ATR 止损触发时自动拒绝下单。
4. QMT 桥接不可用时降级路径正常（不崩溃）。
5. Phase 0-10 所有测试在 Phase 11 代码存在下仍然通过。
6. 无隐式的自动执行路径（必须人工确认或显式 auto mode）。

## Risks and gaps

- QMT 桥接依赖外部进程（qmt_bridge.py on Python 3.6.8），测试环境无法完整覆盖。
- ATR 止损需要实时价格流；mock 测试无法验证延迟容忍度。
- xttrader 下单在测试环境不可用，只能验证桥接协议和执行层逻辑。
- safety mode 的人工确认机制在 CLI 下依赖 user input，在 Streamlit 下需待前端完成。

## Next-phase entry criteria

N/A — Phase 11 是当前 roadmap 最后一个 delivery phase。

## Corrections

- 2026-06-14: Created the product specification draft.
- 2026-06-14: Implemented QMT bridge (HTTP client + mock mode), controlled
  execution engine (SAFETY/AUTO mode), ATR stop-loss, trailing stop, and
  runtime profile extension — 2 new modules, 2 new test files. 117 tests
  passed (68 Phase 11 + 49 Phase 10 regression). Codex acceptance audit
  passed. Safety mode is default and mandatory. No unsafe execution paths
  introduced.

# Phase 14：6 策略层 — 回测策略扩展

## 元数据

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-15`
- Owner: `Hermes (DeepSeek)`
- Git branch: `xg_dev`
- Commit SHA: `980271f`

## 产品目标

Extend the Phase 10 backtest strategy layer from a single moving-average trend strategy to a family of 6 strategies covering bull, range, and bear market conditions:

- **Bull market (2)**: BullTrendStrategy (trend-following + MA bull alignment), ValueAverageStrategy (value/price-percentile)
- **Range market (2)**: MeanReversionStrategy (overbought/oversold reversion), RSIRangeStrategy (RSI interval trading)
- **Bear market (2)**: DefensiveMomentumStrategy (positive momentum + low vol), PutWriteStrategy (protective put writing)

## 范围

### 包含

1. **6 new strategy classes** in `tradingagents/astock/execution/strategy_base.py`:
   - `BullTrendStrategy` — MA5/MA20/MA60 bull alignment + volume confirmation → buy; breakdown → sell
   - `ValueAverageStrategy` — price percentile over lookback window → buy at low pct, sell at high pct
   - `MeanReversionStrategy` — price deviation from MA in std units → buy/sell at extremes
   - `RSIRangeStrategy` — RSI oscillator → buy at oversold (<30), sell at overbought (>70)
   - `DefensiveMomentumStrategy` — ROC-based momentum with volatility filter → buy when positive & low vol, sell when negative
   - `PutWriteStrategy` — MA cross + trend slope → buy at uptrend, sell/avoid at downtrend
   - All strategies extend `StrategyBase` with validated config, uniform `generate_signals(data: pd.DataFrame) -> pd.Series` interface

2. **Package exports** updated:
   - `tradingagents/astock/execution/__init__.py` — export all 6 new strategies
   - `tradingagents/astock/__init__.py` — export all 6 + add to `__all__`

3. **Test suite** (`tests/test_astock_strategies.py`, 398 lines, 26 tests):
   - 3 regression tests for `MovingAverageTrendStrategy` (unchanged behavior)
   - 3 tests per strategy class (buy, sell, validation/edge cases)
   - Uniform constraint tests (output shape, value range, error handling)
   - Custom `importlib` bypass for Python 3.9 compatibility (avoids full package init chain)

### 排除

- No changes to `BacktestEngine`, `PaperTrader`, `RiskGate` — strategies plug into existing framework
- No changes to existing Phase 10 tests or behavior
- No live-market signal generation or advisory chain integration
- No strategy hyperparameter optimization or auto-tuning
- No integration tests with `AStockStore` or `AStockInterface`

## 架构映射

| Module | Change |
|---|---|
| `tradingagents/astock/execution/strategy_base.py` | +6 strategy classes (377 lines) |
| `tradingagents/astock/execution/__init__.py` | Export all strategies |
| `tradingagents/astock/__init__.py` | Package re-exports |
| `tests/test_astock_strategies.py` | New — 26 tests (398 lines) |

## 产品决策

- **StrategyBase as abstract base**: All strategies share `generate_signals(df) -> pd.Series` contract with integer output (-1/0/1). BacktestEngine iterates over strategies generically.
- **Config dict pattern**: Each strategy accepts optional config dict with validated bounds (e.g., `fast_ma < mid_ma < slow_ma`, `pe_low_pct < pe_high_pct`). Validation at `__init__` time, not at signal generation.
- **No external TA library**: All calculations (MA, RSI, ROC, percentile) computed inline with pandas rolling/expanding — zero new dependencies.
- **Volume confirmation optional**: Strategies detect presence of `volume` column and adjust logic accordingly — works with or without volume data.

## 实现记录

### 修改文件

| File | Lines | Purpose |
|---|---|---|
| `tradingagents/astock/execution/strategy_base.py` | +377 | 6 new strategy classes |
| `tradingagents/astock/execution/__init__.py` | ~15 | Export all strategies |
| `tradingagents/astock/__init__.py` | ~15 | Package re-exports |
| `tests/test_astock_strategies.py` | +398 | 26 tests |

### 行为契约

- **Input**: `pd.DataFrame` with `close` column (required), optional `volume` column
- **Output**: `pd.Series[int]` with same index as input, values in {-1, 0, 1}
- **Degradation**: Missing `close` column raises `KeyError`; insufficient data produces NaN → filled to 0
- **Safety boundary**: All signals are integer-only. Return 0 (hold) when conditions are not met. No partial/fractional positions.

## ECC 验收

### 命令

```bash
cd /Users/szp/Desktop/Code/k-code/ai-lab/TradingAgents
python3 -m pytest tests/test_astock_strategies.py -v --tb=short
```

### 结果

- Pass: `26`
- Fail: `0`
- Skip: `0`
- Environment gaps: Python 3.9 only (tests use importlib bypass for 3.9 compatibility)
- Codex verdict: `accept` (via Hermes fallback review — Codex CLI unavailable; see below)

### Hermes fallback review

**Fallback reason**: Codex CLI not installed in this environment. Hermes applies the same ECC acceptance criteria per `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` fallback gate.

**Review scope**:
- 6 strategy implementations in `strategy_base.py`
- Package export changes in `__init__.py` files
- 26 tests in `test_astock_strategies.py`

**Verdict**: `accept`

**Evidence**:
- All 26 strategy tests pass (0 failures, 0 skips)
- Each strategy produces integer signals in {-1, 0, 1} (uniform constraint tests pass)
- Validation tests confirm config bounds are enforced at init time
- MovingAverageTrendStrategy regression tests unchanged — 3/3 pass
- Signal output index matches input index (uniform constraint)
- Missing price column raises KeyError (not silent NaN)
- No external dependencies added (pandas-only math)

**Drift or defects**: None detected

**Open risks**:
- Python 3.10+ users will need a proper import path; test bypass is for 3.9 only
- No integration with BacktestEngine/PaperTrader — strategies are tested in isolation
- Strategy parameters are reasonable defaults but not optimized for any specific market

**Required corrections**: None

## 风险与缺口

1. **Python 3.9 test bypass**: Test file uses `importlib.util.spec_from_file_location` to avoid the full package init chain (which breaks on 3.9 due to `dict | str` syntax in `alpha_vantage_common.py`). On Python 3.10+, tests should import normally through the package.
2. **No wire-up to training/optimization**: Strategies are manual-config only. No auto-parameter tuning or walk-forward optimization.
3. **No multi-strategy portfolio**: Each strategy generates signals independently. BacktestEngine runs one strategy at a time. Future enhancement: strategy ensemble vote weighting.

## 下一 phase 进入条件

Phase 14 is a standalone strategy expansion. No dependencies on subsequent phases. The next natural step would be Phase 15: strategy ensemble voting + portfolio allocation, or integration of strategies into the PaperTrader/BacktestEngine test fixtures.

## 修正记录

_No corrections at time of writing._

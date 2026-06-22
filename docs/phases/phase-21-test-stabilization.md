# Phase 21：测试清噪与全仓回归稳定化

## 范围

把当前 TradingAgents 仓库的全仓 pytest 从"分组能过但整仓存在排序/导入污染"收敛为稳定、可重复、可解释的回归基线。

### 包含

- `tests/` 下的测试隔离、fixture、mock、monkeypatch、import 清理
- `tests/conftest.py` 测试辅助工具验证
- 失败分桶与回归基线文档更新
- 回归命令整理与结果归档

### 排除

- 不开发新功能
- 不修改 A 股 runtime / QMT / backtest / WebUI 的产品行为
- 不通过弱化断言、删除关键测试、扩大 skip 范围来"做绿"
- 不改 phase 边界，不顺手处理无关代码风格问题

---

## 发现：当前测试系统状态

在 Phase 21 启动时，**测试系统已经处于稳定状态，优于原始基线文档记录的结论**：

| 指标 | 2026-06-15（原始 baseline） | 2026-06-19（Phase 21 实际状态） |
|---|---|---|
| 全仓 passed | 636 | **786** |
| failed | 2 | **0** |
| errors | 76 | **0** |
| skipped | 9 | 9 |
| subtests passed | 138 | 120 |

原始文档引用的 "636 passed, 2 failed, 76 errors" 来自 Python 3.9→3.10 环境升级过渡期。Phase 19 已完成的假包污染修复（消除 `__path__=[]` 注入）和后继的 Phase 20 提交已经实际解决了所有 regression 缺陷。

---

## 执行记录

### 1. 全仓回归 — 第 1 次 baseline

```bash
source .venv/bin/activate && python -m pytest -q
```

**结果：786 passed, 9 skipped, 9 warnings, 120 subtests passed**

### 2. 全仓回归 — 第 2 次（重复性验证）

```bash
source .venv/bin/activate && python -m pytest -q
```

**结果：786 passed, 9 skipped, 9 warnings, 120 subtests passed**

### 3. 全仓回归 — 第 3 次（`--cache-clear` 验证缓存无关性）

```bash
source .venv/bin/activate && python -m pytest -q --cache-clear
```

**结果：786 passed, 9 skipped, 9 warnings, 120 subtests passed**

### 4. 全仓回归 — 第 4 次（最终确认）

```bash
source .venv/bin/activate && python -m pytest -q --tb=short -W ignore::DeprecationWarning
```

**结果：786 passed, 9 skipped, 9 warnings, 120 subtests passed**

### 5. A 股主链切片（25 文件）

```bash
source .venv/bin/activate && python -m pytest -q \
  tests/test_astock_graph_runtime.py \
  tests/test_astock_graph_bridge.py \
  tests/test_astock_interface_analyst.py \
  tests/test_astock_blueprint.py \
  tests/test_astock_data_sources.py \
  tests/test_astock_provider_fixtures.py \
  tests/test_astock_cli_report.py \
  tests/test_astock_ui_views.py \
  tests/test_astock_store.py \
  tests/test_astock_backtest.py \
  tests/test_astock_web.py \
  tests/test_astock_api.py \
  tests/test_astock_anti_crawl.py \
  tests/test_astock_batch_backtest.py \
  tests/test_astock_execution_risk_gate.py \
  tests/test_astock_market_analyzer.py \
  tests/test_astock_optimizer.py \
  tests/test_astock_paper_trader.py \
  tests/test_astock_phase9_contracts.py \
  tests/test_astock_ppt.py \
  tests/test_astock_qmt_bridge.py \
  tests/test_astock_qmt_execution.py \
  tests/test_astock_scheduler.py \
  tests/test_astock_sse.py \
  tests/test_astock_strategies.py
```

**结果：472 passed, 1 skipped, 2 warnings, 45 subtests passed**

### 6. 测试用例总数

```bash
for f in tests/test_*.py; do python -m pytest "$f" --co -q 2>/dev/null; done
```

**结果：795 个测试用例**

---

## 失败分桶

| 分桶 | 计数 | 说明 |
|---|---|---|
| **0 failed** | 0 | 全仓零失败 |
| **0 errors** | 0 | 全仓零错误 |
| **import/sys.modules 污染** | 0 | Phase 19 已消除 `__path__=[]` 假包 |
| **env 泄漏** | 0 | `conftest.py` 的 `_dummy_api_keys` autouse fixture 全覆盖 |
| **monkeypatch 未恢复** | 0 | 未发现泄漏 |
| **全局单例/默认配置污染** | 0 | 未发现泄漏 |
| **临时文件/数据库/缓存复用** | 0 | DuckDB 测试使用独立数据库路径 |
| **Web/UI/Flask app state 残留** | 0 | Web 测试使用独立 test client |

## 跳过项分析

| 跳过项 | 文件:行 | 条件 | 合理性 |
|---|---|---|---|
| 7 tests | `test_astock_live_providers.py:101,115,125,139,150,174` | `ASTOCK_RUN_LIVE_TESTS=1` | ✅ 合理 — 需要 live API key |
| 1 test | `test_astock_store.py:650` | `TEST_PYDANTIC_BT=1` | ✅ 合理 — 可选依赖 (pydantic BacktestResult) |

所有 9 个跳过均在条件明确、可再现的 skip guard 下，无需干预。

---

## 测试基础设施文档

### `tests/conftest.py`

```python
# 1. ASTOCK_TESTING=1 — 在 conftest 导入时设置，跳过所有反爬随机延迟
os.environ.setdefault("ASTOCK_TESTING", "1")

# 2. _dummy_api_keys autouse fixture — 为 13 个已知 API key env var 注入
#    placeholder（保留环境中原有值作为优先级）
#    覆盖：OPENAI, GOOGLE, ANTHROPIC, XAI, DEEPSEEK, DASHSCOPE,
#         ZHIPU, MINIMAX, OPENROUTER, AZURE_OPENAI, ALPHA_VANTAGE
@pytest.fixture(autouse=True)
def _dummy_api_keys(monkeypatch):
    for env_var in _API_KEY_ENV_VARS:
        monkeypatch.setenv(env_var, os.environ.get(env_var, "placeholder"))

# 3. mock_llm_client fixture — 全局 LLM client mock
@pytest.fixture()
def mock_llm_client():
    ...
```

### 推荐的回归命令

```bash
# 全仓回归
source .venv/bin/activate && python -m pytest -q

# 全仓回归 + 缓存清除（验证缓存无关性）
source .venv/bin/activate && python -m pytest -q --cache-clear

# 上次失败重跑
source .venv/bin/activate && python -m pytest -q --lf

# A 股主链切片
source .venv/bin/activate && python -m pytest -q tests/test_astock_*.py
```

---

## 损坏风险

| 风险 | 说明 |
|---|---|
| **无污染类缺陷** | 当前全仓无 failed/error，无需担忧风险 |
| **跳过项覆盖** | 如果未来新增需要 live provider key 的测试，需确保 skip 条件一致 |
| **Python 版本漂移** | 当前在 Python 3.10.19 验证；如需升级 Python 需重新验证 |
| **新增假包风险** | 如未来测试需要 mock import，注意不要恢复 `__path__=[]` 模式 |

---

## 假设

1. 当前 `.venv` 环境中的依赖版本保持稳定
2. 远程 provider（baostock 等）保持当前行为
3. 无外部 API key 时跳过项行为不变
4. Phase 19 的 `__path__=[]` 修复未引入回退

---

## 下一阶段入口条件

1. 无 — 本 phase 为独立稳定化回合，不构成下游依赖门槛
2. 如需推进产品功能，可直接在 Phase 21 基线之上开始
3. 推荐在每轮产品交付后执行 `source .venv/bin/activate && python -m pytest -q` 验证回归

---

## Git 提交

Commit SHA: `aec77f15693e86678666195c4851ed6e4bf65199` (当前 HEAD)
Branch: `xg_dev`
Changed files:
- `docs/ASTOCK_CURRENT_STATUS.md` — 更新验收基线为 786 passed, 9 skipped, 0 failed; 新增 Phase 21 行
- `skills/ecc-self-test/SKILL.md` — 无变更
- `tests/conftest.py` — 无变更（已验证已有 fixture 充分覆盖）

# Phase 39 端到端 UAT

| 状态：planned | 更新时间：2026-06-26 |

## 0. 前置依赖

- Phase 30-38 全部完成（模块级文档/schema/测试均已就绪）
- Phase 38 导航收敛已落地（顶层 7 模块 sidebar + 旧入口 redirect + deprecation banner）

## 1. Phase 目标

Phase 30-38 每个 phase 的任务均为模块级文档/schema/测试任务，缺少跨模块的端到端用户工作流验收。Phase 39 的目标是：

- 执行 6 个跨模块端到端 UAT 场景
- 每个场景记录执行步骤、通过/失败状态、root cause（如失败）
- UAT 结果写入 `docs/ASTOCK_CURRENT_STATUS.md`

## 2. UAT 场景

| 场景 | 步骤 | 通过标准 | 涉及 Phase |
|------|------|----------|------------|
| 完整研究链路 | 输入 symbol → AI Research → 生成报告 → 报告含数据来源/模型/时间/advisory 标记 | 报告可追溯，advisory-only 标记存在 | 30, 33, 37 |
| 研究→回测→模拟盘 | 研究报告 → 选择策略 → 回测 → 模拟盘试跑 | 回测含数据假设，模拟盘明确 paper 标签 | 30, 31, 32, 35 |
| 策略→交易 | 策略回测 → 优化 → 模拟盘下单 → 风控门 → 人工确认 | 风控拦截有 reason code，人工确认记录存在 | 30, 32, 35 |
| 龙头→候选池→交易 | Market Leaders 候选池 → 查看入池理由 → 进入交易页 | 候选股有可解释理由，交易页显示 capability 标签 | 30, 34, 35 |
| 数据→AI→报告归档 | 数据刷新 → AI Research → 报告归档 → 报告复查 | 数据 freshness/quality 可查，报告可检索复查 | 31, 33, 37 |
| Ops 审计追溯 | 任意操作 → Ops Dashboard 查询 TaskRun/AuditEvent | 每个关键动作有 audit 引用，失败有错误原因 | 37 |

## 3. 任务分解

| ID | 任务 | 产物 | 验收 |
|----|------|------|------|
| 39-01 | 编写端到端 UAT 场景表 | UAT 场景表 | 覆盖上述 6 个场景 |
| 39-02 | 为每个场景编写详细执行步骤 | 步骤清单 | 每步可复现 |
| 39-03 | 执行 UAT 场景 1-3（研究链路/回测模拟盘/策略交易） | 执行结果 | 通过/失败记录 |
| 39-04 | 执行 UAT 场景 4-6（龙头交易/数据AI归档/Ops审计） | 执行结果 | 通过/失败记录 |
| 39-05 | 更新当前状态文档 | `ASTOCK_CURRENT_STATUS.md` | 记录 UAT 结果 |

## 4. 测试命令

```bash
# 底层自动化测试（每个 UAT 场景需配合手工操作）
pytest tests/test_astock_web.py -q
pytest tests/test_astock_api.py -q
pytest tests/test_astock_graph_runtime.py -q
pytest tests/test_astock_backtest.py -q
pytest tests/test_astock_paper_trader.py -q
```

## 5. 完成标准

- 所有 6 个 UAT 场景至少执行一次并记录结果
- 失败场景必须有 root cause 分析和修复计划
- UAT 结果写入 `docs/ASTOCK_CURRENT_STATUS.md`

---

**来源**: `docs/ASTOCK_PRODUCT_OPTIMIZATION_ROADMAP.md` §12.1
**Commit SHA**: *(pending — Phase 39 启动后更新)*

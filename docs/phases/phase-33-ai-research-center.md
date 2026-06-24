# Phase 33 AI Research Center 需求与 Hermes 任务包

| 状态：planned | 更新时间：2026-06-24 |

## 0. 前置依赖

- Phase 31：data_assumption 字段、DataQualityTag（AI 研究引用的数据必须标注质量和假设）
- Phase 32：BacktestResult schema（AI 可复用回测结果作为上下文）

## 1. Phase 目标

把 AI Agent、A 股研究 runtime、研究页、报告中心、新闻/公告/研报解读收敛为 AI Research Center。保留原 TradingAgents core，所有 AI 输出默认 advisory-only。

## 2. 范围

后台模块：

- `tradingagents/astock/runtime.py`
- `tradingagents/astock/analyst.py`
- `tradingagents/astock/api/routes_ai_agent.py`
- `tradingagents/astock/api/routes_reports.py`
- `tradingagents/astock/reporting/ppt.py`

前台模块：

- `research.html`
- `ai_agent.html`
- `reports.html`

API：

- `POST /api/v1/ai/analyze`
- `GET /api/v1/reports/pptx`
- future `ResearchTask` / `ResearchAudit` endpoints

## 3. 5 分钟任务与可执行 brief

| ID | Hermes brief | DeepSeek allowed scope | Codex acceptance |
|---|---|---|---|
| 33-01 | 搜索 AI/report/research 入口。 | docs；源码只读。 | research/ai_agent/reports/runtime 覆盖。 |
| 33-02 | 定义 ResearchTask schema。 | model governance、API contracts。 | task_id/symbol/mode/status/snapshot 字段明确。 |
| 33-03 | 定义 ResearchAudit schema。 | model governance、data dictionary。 | model/prompt/snapshot/citation/generated_at 完整。 |
| 33-04 | 定义 advisory-only 输出要求。 | risk disclosure、model governance。 | AI 输出不得触发真实订单。 |
| 33-05 | 梳理 LLM 不可用降级。 | model governance、test plan。 | fail closed/degraded 行为明确。 |
| 33-06 | 梳理报告归档字段。 | data dictionary、release/change doc。 | markdown/json/ppt/web report 字段清晰。 |
| 33-07 | 更新 AI Research 效果图。 | progress plan / WebUI spec。 | 审计区和报告档案区明确。 |
| 33-08 | 更新模型治理文档。 | model governance。 | prompt version 和 provider 记录明确。 |
| 33-09 | 运行 research runtime 测试。 | phase evidence。 | `tests/test_astock_graph_runtime.py -q` 有结果。 |
| 33-10 | 运行 PPT 测试。 | phase evidence。 | `tests/test_astock_ppt.py -q` 有结果。 |

## 4. 测试命令

```bash
pytest tests/test_astock_graph_runtime.py -q
pytest tests/test_astock_graph_bridge.py -q
pytest tests/test_astock_ppt.py -q
pytest tests/test_astock_web.py -q
```

## 5. 完成标准

- 每个 AI 结论可追溯模型、prompt、输入数据快照和引用。
- AI 输出 advisory-only。
- 报告中心具备归档、复查、对比的产品边界。

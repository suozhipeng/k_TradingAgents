# Phase 33 — AI Research Center

## ResearchTask schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `symbol` | string | 标的 |
| `mode` | string | live_research / deterministic |
| `status` | enum | queued/running/success/failed/cancelled |
| `prompt_version` | string | LLM prompt 版本 |
| `provider` | string | 模型提供商 |
| `snapshot` | dict | 输入数据快照 |
| `result` | dict/null | 研究输出 |
| `error` | string/null | 错误信息 |

## ResearchAudit schema

| 字段 | 说明 |
|------|------|
| `advisory` | 固定 `True`，AI 输出不可触发订单 |
| `model` | 模型名称 |
| `prompt_text` | 完整 prompt |
| `input_snapshot` | 输入数据快照 |
| `citations` | 引用来源列表 |

## 完成标准

- 每个 AI 结论可追溯模型、prompt、输入数据快照和引用 ✅
- AI 输出 advisory-only ✅（`advisory=True`）

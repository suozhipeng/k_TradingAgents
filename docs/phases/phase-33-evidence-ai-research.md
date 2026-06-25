# Phase 33 — AI Research Center

## 交付物

| 任务 | 状态 | 文件 | 说明 |
|------|------|------|------|
| 33-01 ResearchContext schema | ✅ | `tradingagents/astock/schemas/research_context.py` | 结构化上下文包，取代 ad-hoc dict；含 DataSourceMeta provenance 元数据 |
| 33-02 ResearchTask wired to API | ✅ | `tradingagents/astock/api/routes_ai_agent.py` | `/ai/analyze` 返回 task_id、status、advisory=true、audit 信息 |
| 33-03 Advisory-only 强制 | ✅ | schema 层 + API 响应层 | `ResearchAudit.advisory=True` 默认；API 返回 `"advisory": True` |
| 33-04 LLM 降级结构化 | ✅ | `routes_ai_agent.py:_run_analysis` | LLM 不可用时返回 `status: degraded` + `llm_error` 字段 + context 仍返回 |
| 33-05 Report archive schema | ✅ | `tradingagents/astock/schemas/report_archive.py` | ReportItem + ReportArchive 统一 markdown/json/ppt/web 归档字段 |
| 33-06 文档更新 | ✅ | 本文件 + `ASTOCK_MODEL_GOVERNANCE.md` 已覆盖 Phase 33 要求 |

## 新增 schemas

### ResearchContext (`schemas/research_context.py`)

```
ResearchContext
├── symbol: str               # 目标标的
├── gathered_at: str          # 收集时间戳
├── stock_info: StockInfoData  # 股票基本信息 + provenance
├── market_summary: MarketSummaryData  # 市场概况 + provenance
└── kline_latest: KlineData   # 最新 K 线 + provenance
```

每个 data source 包裹 `DataSourceMeta(source, freshness, quality, note)` 用于审计。

### ReportArchive (`schemas/report_archive.py`)

```
ReportItem
├── report_id / report_type   # 唯一 ID + 格式（markdown/json/ppt/web）
├── symbol / title / summary  # 标的 + 标题 + 摘要
├── generated_at / advisory   # 时间戳 + 强制 advisory=True
├── content / content_path    # 全文内容/文件路径
├── research_conclusion       # 研究结论摘要（recommendation/confidence/summary）
├── citations / metadata      # 引用来源 + 可扩展元数据
```

## API 变化

### `POST /api/v1/ai/analyze` 新增 Phase 33 字段

```json
{
  "symbol": "600519.SH",
  "analysis_type": "full",
  "timestamp": "2026-06-25T15:00:00",
  "context": { /* 原有 ad-hoc context */ },
  "llm_analysis": "...",
  "task_id": "ai-ab91f1eb6b76",
  "status": "success|degraded",
  "advisory": true,
  "llm_error": null,
  "audit": {
    "audit_id": "audit-5ea943383cbd",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "prompt_version": "v1",
    "advisory": true,
    "generated_at": "..."
  }
}
```

## 降级策略

| LLM 状态 | API 响应 | 用户看到 |
|----------|----------|----------|
| LLM 正常 | `status: success` | 完整 AI 分析 |
| LLM 不可用 | `status: degraded` + `llm_error` | "LLM analysis unavailable" + 上下文数据 |
| 参数错误 | 400 | 错误信息 |

## 测试结果

```
pytest tests/test_astock_graph_runtime.py -q  →  14 passed
pytest tests/test_astock_graph_bridge.py -q  →  全部通过
pytest tests/test_astock_ppt.py -q           →  3 passed, 4 skipped (no pptx)
pytest tests/test_astock_web.py -q           →  全部通过
```

## Schema import 验证

```python
from tradingagents.astock.schemas import (
    ResearchContext, DataSourceMeta,
    ReportArchive, ReportItem, ReportFormat,
)
```

## 完成标准对照

| 标准 | 状态 |
|------|------|
| 每个 AI 结论可追溯模型、prompt、输入数据快照和引用 | ✅ (ResearchAudit + ResearchContext) |
| AI 输出 advisory-only | ✅ (schema + API 双 enforce) |
| 报告中心具备归档、复查、对比的产品边界 | ✅ (ReportArchive schema 定义) |

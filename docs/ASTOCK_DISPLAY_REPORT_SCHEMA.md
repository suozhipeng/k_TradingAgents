# A 股展示报告 Schema

## Purpose

`AStockGraphRuntime` now returns a stable display-oriented report object that
can be consumed by both the CLI and the future UI without touching the generic
financial graph path.

## Schema fields

### Core identity
- `symbol` / `ticker`: A 股标的代码
- `normalized_symbol`: 规范化后的标的代码
- `trade_date`: 分析日期
- `source`: 本次运行使用的入口来源
- `mode` / `runtime_mode`: 运行模式，当前固定为 `astock_research_bridge`
- `status`: `ok` / `partial` / `degraded`
- `decision_scope`: 当前固定为 `research_only`
- `actionable`: 当前固定为 `false`
- `execution_signal`: 当前固定为 `ResearchOnly`

### Analysis sections
- `section_results`: 五层 section 的统一展示结果
- `astock_sections`: 原始结构化 section payload
- `astock_analysis`: 顶层分析汇总
- `analyst_summary`: 顶层摘要，和 `summary` 保持一致

### Research chain views
- `bull_output`: Bull Researcher 的结构化输出
- `bear_output`: Bear Researcher 的结构化输出
- `research_manager_output`: Research Manager 的结构化输出
- `bull_view`: 可展示的 Bull 视图文本
- `bear_view`: 可展示的 Bear 视图文本
- `research_manager_conclusion`: Research Manager 的结论文本
- `investment_plan`: 最终研究计划
- `final_trade_decision`: 向后兼容的研究结论字段，不可作为执行信号

### Coverage and degradation
- `provider_coverage`: 每个 section 的来源与可用性
- `missing_data_notes`: 缺失/空数据说明
- `degradation_notes`: 降级/错误说明
- `runtime_trace`: 运行轨迹，给 UI / CLI 提供只读调试上下文
- `metadata`: 调试信息、状态键等

### Compatibility
- `to_dict()` 返回完整展示 schema
- `to_legacy_state()` 额外保留旧 graph-style state keys，方便现有 CLI/graph 代码继续运行
- `run_astock_research_bridge(...)` 仍可返回兼容字典，但其内部共享同一 runtime

## Example

```json
{
  "symbol": "600519.SH",
  "ticker": "600519.SH",
  "runtime_mode": "astock_research_bridge",
  "status": "partial",
  "analyst_summary": "A-share bridge payload assembled",
  "section_results": {
    "market": {
      "status": "ok",
      "source": "fake-market",
      "summary": "market snapshot ok",
      "has_data": true
    },
    "research": {
      "status": "empty",
      "source": "iwencai",
      "summary": "iwencai cookie missing",
      "has_data": false
    }
  },
  "bull_view": "Bull bridge output from the deterministic runtime helper.",
  "bear_view": "Bear bridge output from the deterministic runtime helper.",
  "research_manager_conclusion": "**Recommendation**: Hold",
  "provider_coverage": {
    "market": {"source": "fake-market", "status": "ok", "available": true},
    "research": {"source": "iwencai", "status": "empty", "available": false}
  },
  "missing_data_notes": ["research: iwencai cookie missing"],
  "degradation_notes": ["research [empty]: iwencai cookie missing"]
}
```

## Notes

- The schema is intentionally read-only and display-friendly.
- The current runtime stops at Research Manager.
- `final_trade_decision` must not be sent to order execution or stored as a completed trade decision.
- It does not include any QMT execution or order-placement semantics.
- Generic stock/crypto runtime outputs remain unchanged.
- The display order is identity, core summary, structured sections, research outputs, coverage, trace, then raw payload.

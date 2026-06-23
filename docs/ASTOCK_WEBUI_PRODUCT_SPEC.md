# A 股 WebUI 产品规范

| 更新时间：2026-06-23 |

本文补充 WebUI 页面级产品规范，用于把现有 WebUI 边界和重构方向转化为可开发、可验收的页面规则。详细代码边界和设计图仍以 `docs/ASTOCK_BOUNDARY_AND_UI_REFACTOR_PLAN.md` 为准；逐页验收证据以 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md` 为准。

## 1. 顶层信息架构

后续 WebUI 应收敛为以下顶层模块：

| 顶层模块 | 目标 | 页面形态 |
|---|---|---|
| Dashboard | 当前系统状态和关键入口 | 总览卡片、任务状态、能力标签 |
| AI Research Center | AI 投研、报告、新闻/公告/研报解读 | 顶部 tab |
| Strategy Lab | 策略、回测、优化、绩效、对比、动量轮动 | 顶部 tab |
| Market Leaders | 龙头、候选池、板块、资金线索、轮动回测 | 单入口 + 顶部 tab |
| Trading & Execution | paper、managed、live-ready 准入、订单和风控 | 模式标签 + 前置确认 |
| Data & Ops | 数据刷新、缓存、provider、任务、审计 | 健康页 + 任务页 |
| Portfolio Workbench | 组合风险和绩效归因 | 风险面板 + 归因报告 |

## 2. 页面状态

所有核心页面必须支持：

- loading：显示任务或数据加载中。
- empty：没有数据时给出下一步动作。
- degraded：provider、LLM、QMT 或缓存降级。
- error：显示错误码、错误分类和建议动作。
- stale：数据过期或使用缓存。
- mock / paper / managed / live-ready：能力等级清晰标注。

## 3. 能力标签规范

页面和关键卡片必须使用一致的能力标签：

| 标签 | 含义 |
|---|---|
| research | 仅研究分析，不可直接执行 |
| paper | 模拟盘或虚拟成交 |
| managed | 受控执行，需要风控和人工确认 |
| live-ready | 已通过准入 checklist 的真实执行能力 |
| mock | 占位或演示数据 |
| degraded | 降级数据或部分不可用 |

## 4. 关键页面验收

### 4.1 AI Research Center

- 输入区支持 symbol、日期、研究模式。
- 输出区展示模型、prompt 版本、数据快照和 advisory 标记。
- 报告可归档、复查、对比。

### 4.2 Strategy Lab

- 策略列表来自统一 registry。
- 回测结果显示指标、净值、交易明细、成本模型、数据假设。
- 优化和对比使用同一结果 schema。

### 4.3 Market Leaders

- 顶层只保留一个龙头相关入口。
- 内部 tab 覆盖动量总览、候选池、板块强弱、资金线索、轮动回测。
- 候选股显示入池理由、出池理由、来源和刷新时间。

### 4.4 Trading & Execution

- 页面顶部显示当前模式。
- paper、managed、live-ready 视觉和文案完全区分。
- 下单前显示风控结果、确认状态和审计引用。
- QMT 不可用时降级到 paper 或 disabled。

### 4.5 Data & Ops

- provider、DuckDB、cache、LLM、QMT 状态可见。
- 任务失败有错误码、时间和建议处理动作。
- 数据刷新结果可追溯到 source 和 snapshot。

## 5. 移动端与响应式

后续 WebUI 至少满足：

- 桌面端优先，适配 1366px 及以上。
- 平板/窄屏可纵向堆叠核心卡片。
- 表格在窄屏下支持横向滚动或摘要卡片。
- 交易确认类按钮在移动端不得因布局压缩造成误触。

## 6. 验收要求

每个 WebUI phase 必须提供：

- 入口路径。
- 页面状态覆盖。
- API 依赖和能力等级。
- mock/paper/managed/live-ready 标签。
- 空态、错误态、降级态截图或说明。
- 旧入口迁移策略。
- 逐页验收记录必须同步 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`。

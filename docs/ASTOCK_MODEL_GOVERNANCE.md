# A 股 AI 模型治理文档

| 更新时间：2026-06-23 |

本文定义 AI Research、advisory chain 和报告生成涉及的模型治理要求。目标是保留原 TradingAgents 底层 AI 分析能力，同时让新增 A 股产品能力具备可追踪、可复验、可降级的治理边界。

## 1. 治理对象

| 对象 | 示例 | 治理要求 |
|---|---|---|
| 模型 provider | OpenAI、其他 LLM provider、本地模型 | 记录 provider、模型、版本和调用模式 |
| prompt | research prompt、debate prompt、report prompt | 版本化、可追溯、可回滚 |
| 上下文数据 | 行情、财务、公告、新闻、研报、回测结果 | 保留 source、snapshot、freshness |
| 输出 | 研究报告、advisory、解释、摘要 | 标注 advisory，不直接触发真实交易 |
| 失败模式 | 超时、限流、空输出、幻觉风险 | fail closed 或降级到非 AI 输出 |

## 2. AI Research Task

后续 AI Research Center 应统一记录：

- task id。
- symbol / portfolio / topic。
- model provider 和 model name。
- prompt version。
- input snapshot ids。
- generated_at。
- output type。
- confidence / uncertainty note。
- advisory-only 标记。
- audit event id。

## 3. Prompt 版本管理

新增或修改 prompt 时必须记录：

- 适用模块。
- 变更原因。
- 输入字段。
- 输出 schema。
- 禁止输出内容。
- 回滚版本。
- 最小验证样例。

禁止把 prompt 调整作为“不可追踪的临时修复”直接进入生产路径。

## 4. 输出约束

AI 输出必须遵守：

- 不承诺收益。
- 不给出无风险结论。
- 不把研究结论直接变成真实订单。
- 不隐藏数据缺失、过期、fallback、低质量状态。
- 不覆盖风控门、人工确认和执行模式。

## 5. 降级策略

当 LLM provider 不可用时：

- research-only 页面显示 AI unavailable 或 degraded。
- 不生成新的交易建议。
- 可展示已有历史报告，但必须标注生成时间。
- 回测、数据页和模拟盘不应因 AI 不可用整体失效。

## 6. 验收要求

涉及 AI 的 phase 必须提供：

- 模型和 prompt 记录。
- 输入数据快照说明。
- 输出 schema 或报告样例。
- advisory-only 验证。
- provider 不可用时的 fail closed 或 degraded 行为。
- 与原 TradingAgents core 的兼容说明，不重写 core。

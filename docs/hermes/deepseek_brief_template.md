# DeepSeek 编码 Brief 模板

当 Hermes 将实现任务打包给 DeepSeek 时，使用本模板。

```text
Phase：
目标：

包含范围：
- ...

排除范围：
- ...

涉及文件 / 模块：
- ...

设计契约：
- ...

必须运行的测试：
- ...

验收标准：
1. ...
2. ...

需要更新的文档：
- ...

约束：
- ...

返回格式：
已修改文件：
行为摘要：
已运行测试：
测试结果：
开放风险：
假设：
```

## 仓库约束

- brief 必须保持在当前 active phase 边界内。
- 涉及 A 股策略、回测、优化器、风控指标、provider 链路或 WebUI 产品边界时，必须加载 `tradingagents-core`。
- 涉及新增策略时，必须遵守 `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md`。
- 只允许修改后来新增的 A 股层、WebUI、API、执行层或文档；不要改动原 TradingAgents 底层 AI 分析核心，除非用户明确批准。
- 代码或测试发生变化后，必须经过 Codex review gate 才能验收。
- phase 结论必须写入 `docs/phases/`，不要回写到 `.hermes/`。

# Codex Review Packet 模板

当 Hermes 将已实现工作交给 Codex 做独立 review gate 时，使用本模板。

```text
# Codex Review Packet

生成时间：
分支：
模式：

## Review 范围

### A. 待审查变更
- Commit：
- 文件：
- 声称行为：

### B. 工作区未提交变更
- 文件：
- 仍未 stage / commit 的原因：

### C. 验证证据
- 已运行测试：
- build / check 命令：
- 已知失败或跳过：

## Review 问题

1. 实现是否保持在当前 phase 边界内？
2. 已修改文件是否支持声称结论？
3. 测试是否覆盖本次触达的代码面？
4. 是否存在 scope drift、回归风险或文档不一致？
5. 是否误改了原 TradingAgents 底层 AI 分析核心？

## 期望 Codex 输出

Review 范围：
结论：accept | partial | fail
证据：
偏移或缺陷：
必须修正项：
```

## 仓库约束

- 静态验收和漂移检查优先使用 `ecc-readonly-review`。
- 需要执行回归时使用 `ecc-self-test`。
- 涉及项目整体架构、策略开发、回测、风控、数据链路或 WebUI 边界时，必须加载 `tradingagents-core`。
- Codex 返回 `accept` 后，只提交 review 通过的文件。

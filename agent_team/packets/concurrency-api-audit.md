# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：确认 TradingAgents A 股模块可安全支持多线程操作，优先保证功能正常运行并消除可复现资源竞争。
- 你负责的子目标：审计并修复 Flask app factory、调度器路由、后台服务和关闭生命周期的并发与资源所有权问题。
- 该子目标在整体方案中的位置：API 层创建并驱动后台资源，必须确保多 app、并发请求及关闭时无全局状态串扰。
- 上游 Skill：codex-model-routing-team。
- 上游阶段：并行审计与修复。
- 前置阶段门：无。

## 交付物

- 产物：必要的 API/调度并发安全修复及回归测试。
- 写入路径：仅 `tradingagents/astock/api/`、`tradingagents/astock/execution/scheduler/`、以及新建 `tests/test_astock_api_concurrency.py`。
- 返回格式：结论、证据/变更、验证、风险。

## 边界

- 可读取：整个仓库与现有测试。
- 可写入：上述写入路径。
- 禁止触碰：`tradingagents/astock/store/`、数据源适配器、Web 模板、脚本、依赖文件、现有其它测试文件。
- 文件所有权：上述路径由你独占。
- reserved slots：由主 Agent 记录，Worker 不修改。

## 背景与约束

- 已知事实：app-scoped services 与关闭 deadline 已实现；重点检查共享 registry、scheduler lookup、idempotent teardown、并发请求/关闭竞态。
- 用户偏好：功能正确性优先于吞吐；不能通过粗暴的全局锁让请求完全串行化。
- 关键约束：不运行会下单或修改外部数据的操作；保留既有路由行为。
- 与其他 Worker 的接口：存储与缓存由另一 Worker 独占；不要修改其路径。

## 验收

- 完成标准：可控多线程测试覆盖 app 隔离、并发请求或调度操作、关闭资源所有权，且没有竞态异常。
- 必须运行的验证：新增测试、相关 API/lifecycle 测试、`git diff --check`。
- 缺失信息时的处理：报告缺口，不猜测。

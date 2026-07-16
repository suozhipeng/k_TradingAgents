# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：确认 TradingAgents A 股模块可安全支持多线程操作，优先保证功能正常运行并消除可复现资源竞争。
- 你负责的子目标：审计并修复存储、缓存和数据任务管理器的线程安全边界。
- 该子目标在整体方案中的位置：数据层是 Flask 后台任务及调度器的共享依赖；必须先保证无竞态、无连接误用。
- 上游 Skill：codex-model-routing-team。
- 上游阶段：并行审计与修复。
- 前置阶段门：无。

## 交付物

- 产物：必要的并发安全代码修复及针对真实竞态的回归测试。
- 写入路径：仅 `tradingagents/astock/store/`、`tradingagents/astock/data_sources/tdx_cache.py`、以及新建 `tests/test_astock_store_concurrency.py`。
- 返回格式：结论、证据/变更、验证、风险。

## 边界

- 可读取：整个仓库与现有测试。
- 可写入：上述写入路径。
- 禁止触碰：`tradingagents/astock/api/`、Web 模板、脚本、依赖文件、现有其它测试文件。
- 文件所有权：上述路径由你独占。
- reserved slots：由主 Agent 记录，Worker 不修改。

## 背景与约束

- 已知事实：DuckDB 已有线程安全封装，DataJobManager 有两个线程池；不要仅凭静态判断，须用并发测试验证。
- 用户偏好：功能正确性优先于吞吐；禁止在关闭期造成 Store use-after-close。
- 关键约束：不运行会下单或修改外部数据的操作；保留既有 API 兼容性。
- 与其他 Worker 的接口：API/调度器由另一 Worker 独占；你的修复不得修改其目录。

## 验收

- 完成标准：并发读写/任务提交在可控测试中没有连接竞争、死锁或数据丢失；关闭语义清晰。
- 必须运行的验证：新增测试、相关既有 store 测试、`git diff --check`。
- 缺失信息时的处理：报告缺口，不猜测。

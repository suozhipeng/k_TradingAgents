# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：修复 TradingAgents 的数据库、后台和 Web，使本地 A 股工作台可运行、职责解耦且能安全处理并发操作。
- 你负责的子目标：诊断数据库启动、schema、DuckDB/PostgreSQL 抽象、数据任务持久化与线程安全问题；仅修复明确可复现且位于你所有权内的问题。
- 该子目标在整体方案中的位置：这是健康探针；其结果决定随后后台与 Web 任务的集成假设。
- 上游 Skill：codex-model-routing-team。
- 上游阶段：诊断与修复。
- 前置阶段门：无。

## 交付物

- 产物：简洁的根因报告、已验证的补丁（若需）、测试结果与剩余风险。
- 写入路径（如有）：仅 `tradingagents/astock/store/`、`tradingagents/astock/quality/`，及与数据库直接相关的既有测试文件。
- 返回格式：结论、证据/变更、验证、风险。

## 边界

- 可读取：全仓、文档、测试与运行日志。
- 可写入：上述写入路径。
- 禁止触碰：`tradingagents/astock/api/`、`tradingagents/astock/web/`、原始 `tradingagents/agents/`、`graph/`、`llm_clients/`、`dataflows/`。
- 文件所有权：数据库与质量目录由你独占；如问题需要 API/Web 改动，只报告精确建议，勿修改。
- reserved slots（由主 Agent 记录，Worker 不修改）：2。

## 背景与约束

- 本地产品入口是 `scripts/run_astock_api.py`，local-release 必须保持回环绑定、单进程、research/backtest only；不得放宽交易安全边界。
- 目标是正确并发控制与数据层解耦，不是启用真实交易。
- 现有用户改动包括项目级 skill 安装；不得撤销或覆盖它们。
- 与其他 Worker 的接口：报告 API 所需的存储契约或并发语义，但不要编辑 API/Web 文件。

## 验收

- 完成标准：至少复现并解释数据库相关启动/并发问题，或提供证明其当前可用的测试证据；所有修改都通过对应测试。
- 必须运行的验证：目标 pytest 测试；如可行，用隔离临时数据库创建 Flask app 并运行并发读写的最小验证。
- 缺失信息时的处理：报告缺口，不猜测。

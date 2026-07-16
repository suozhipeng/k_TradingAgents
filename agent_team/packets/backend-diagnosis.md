# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：修复 TradingAgents 的数据库、后台和 Web，使本地 A 股工作台可运行、职责解耦且能安全处理并发操作。
- 你负责的子目标：诊断并修复 Flask API 启动、蓝图注册、服务生命周期、后台任务/SSE 的边界和并发安全问题。
- 该子目标在整体方案中的位置：后台应只通过明确的 store/data facade/service 契约工作，不能把 Web 状态或真实交易能力混入 local-release。
- 上游 Skill：codex-model-routing-team。
- 上游阶段：诊断与修复。
- 前置阶段门：数据库健康探针已实体化；无需等待其结论，但不得编辑其所有权文件。

## 交付物

- 产物：根因报告、最小补丁（若需）、测试结果和对 Web/API 接口的影响。
- 写入路径（如有）：仅 `tradingagents/astock/api/`、`scripts/run_astock_api.py`、直接对应的 API 测试。
- 返回格式：结论、证据/变更、验证、风险。

## 边界

- 可读取：全仓、文档、测试与运行日志。
- 可写入：上述写入路径。
- 禁止触碰：`tradingagents/astock/store/`、`tradingagents/astock/quality/`、`tradingagents/astock/web/`、原始 `tradingagents/agents/`、`graph/`、`llm_clients/`、`dataflows/`。
- 文件所有权：API/启动脚本由你独占；若需要 store/web 变更，仅报告精确接口建议。
- reserved slots（由主 Agent 记录，Worker 不修改）：2。

## 背景与约束

- 本地入口必须维持 loopback、单进程、research/backtest only；不得开启真实交易、关闭授权保护或绕开风控。
- “多线程操作”意味着后台作业与请求不能共享不安全的可变状态、不能阻塞 Web 请求，并要使用受控的任务状态与清晰 API 契约；不是通过多 Flask worker 绕开单进程约束。
- 保留现有用户的 skill 安装文件。
- 与其他 Worker 的接口：保持 Web 可调用的 `/api/v1` envelope；只修改 API 所有权文件。

## 验收

- 完成标准：可创建测试 app、关键健康/API 路由工作、后台作业相关失败有可复现的修复或明确证据。
- 必须运行的验证：相关 pytest；必要时 Flask test client 的并发/隔离最小验证。
- 缺失信息时的处理：报告缺口，不猜测。

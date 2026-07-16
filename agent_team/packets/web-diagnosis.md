# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：修复 TradingAgents 的数据库、后台和 Web，使本地 A 股工作台可运行、职责解耦且能安全处理并发操作。
- 你负责的子目标：诊断并修复 Jinja2 Web 工作台的启动、页面路由、静态资源与 API 使用问题；只修改 Web 层。
- 该子目标在整体方案中的位置：Web 必须是 API 的薄客户端，不能持有数据库连接或直接调用执行/交易逻辑。
- 上游 Skill：codex-model-routing-team。
- 上游阶段：诊断与修复。
- 前置阶段门：数据库健康探针已实体化；无需等待其结论，但不得编辑其所有权文件。

## 交付物

- 产物：根因报告、最小 Web 补丁（若需）、测试结果和需要后端配合的契约建议。
- 写入路径（如有）：仅 `tradingagents/astock/web/`、直接对应的 Web 测试。
- 返回格式：结论、证据/变更、验证、风险。

## 边界

- 可读取：全仓、文档、测试与运行日志。
- 可写入：上述写入路径。
- 禁止触碰：`tradingagents/astock/api/`、`tradingagents/astock/store/`、`tradingagents/astock/quality/`、原始 `tradingagents/agents/`、`graph/`、`llm_clients/`、`dataflows/`。
- 文件所有权：Web 目录由你独占；若 API 契约有误，仅报告精确建议。
- reserved slots（由主 Agent 记录，Worker 不修改）：2。

## 背景与约束

- 唯一产品面是 Flask/Jinja2，入口为 `scripts/run_astock_api.py`。
- 保持 local-release research/backtest-only 安全边界；页面不得声称真实自动交易。
- 多线程/后台操作必须通过 API 的 task ID、SSE 或轮询呈现，不能直接操作数据库。
- 保留现有用户的 skill 安装文件。

## 验收

- 完成标准：Web 蓝图可被 app 注册，核心页面返回正常，页面使用的 API 调用符合统一 envelope。
- 必须运行的验证：相关 pytest；可用时在本地 test client 或浏览器 smoke 中验证。
- 缺失信息时的处理：报告缺口，不猜测。

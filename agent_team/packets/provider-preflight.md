# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：闭环本地 A 股工作台的剩余验证与运维缺口。
- 子目标：为 live provider 建立可重复 preflight 与运行指引；在当前凭证/网络可用时运行安全的只读验证，否则报告精确缺失项。
- 上游阶段：外部依赖验收。

## 交付物

- 写入：仅 `scripts/check_astock_live_research_env.py`、`scripts/verify_astock_live_pipeline.py`、`docs/03-operations.md`、`tests/test_astock_live_providers.py`。
- 返回：可用 provider、跳过/失败原因、命令与风险。

## 边界

- 严禁写入 `.env`、凭证、数据库业务数据，或执行任何交易操作。
- 只允许只读 research/provider 请求；不得伪造 live 验收。

## 验收

- 一条命令能明确列出 live 验收前提和缺失项。
- 文档与实际脚本的 provider 配置优先级一致。

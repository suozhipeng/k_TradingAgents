# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：闭环本地 A 股工作台的剩余验证与运维缺口。
- 子目标：处理 pyarrow/fastparquet、Pydantic backtest 与 Playwright 浏览器回归的可重复依赖和运行入口。
- 上游阶段：验证闭环。

## 交付物

- 写入：仅 `pyproject.toml`、`scripts/verify_local_release.sh`、`tests/test_local_release_browser.py`、`docs/`。
- 返回：变更、测试命令、无法运行时的明确原因。

## 边界

- 禁止写入应用源码、Store/API/Web 目录及现有 `agent_team/` 账本。
- 不得修改或泄露任何凭证；不需要真实 provider。
- 安装依赖只可在当前 `.venv`，并须同步项目可复现依赖声明。

## 验收

- parquet/Pydantic 可选测试不再因基础环境缺失跳过，或被明确迁移为可声明的 extra。
- 浏览器测试有明确的安装/运行路径，且能在当前环境执行或报告唯一阻塞。

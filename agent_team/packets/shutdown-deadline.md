# 任务身份

你是本任务的独立执行 Worker。禁止创建任何后台任务、线程或子 Agent。

## 目标与位置

- 总目标：闭环本地 A 股工作台的剩余验证与运维缺口。
- 子目标：为 API 关闭阶段加入受控 deadline，使不可协作的 provider 调用不会无限阻塞关闭，同时保持不发生 use-after-close。
- 上游阶段：后台可靠性。

## 交付物

- 写入：仅 `tradingagents/astock/api/lifecycle.py`、`tradingagents/astock/api/app_factory.py`、`tests/test_astock_lifecycle.py`。
- 返回：根因、最小补丁、验证、风险。

## 边界

- 不改 Store、Web、执行/交易边界；不改变 local-release 的单进程或安全语义。
- deadline 超时必须保守：不得关闭仍被后台任务使用的 store。

## 验收

- 协作任务关闭时正常 drain；不可协作任务不会无限等待，且不触发 store use-after-close。
- 用确定性测试验证，不依赖外部 provider。

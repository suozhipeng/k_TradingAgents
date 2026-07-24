# Handoff — TradingAgents xg_dev（冻结快照）

## Goal of next session

解除冻结后，先修复市场追踪板块的真实数据链路：`/api/v1/market/overview` 当前回退到 mock，导致四大指数展示为 0。目标是只从 Canonical DuckDB 读取指数 K 线，不再经过旧 Router/mock fallback；随后补充回归测试和浏览器验收。

## State of play

- **冻结时间**：2026-07-24 17:37 HKT。
- **冻结分支/工作树**：`fix/xg-dev-data-loop-v033`，`.worktrees/xg-integration`。
- **冻结基线**：提交 `1d4bb188451bf45d174faa3c33656da7784dfc4c`；与 `origin/xg_dev` 的 merge-base 为 `ae9c22f`。冻结时 `origin/xg_dev...HEAD` 为 `3 5`（远端主分支独有 3 个提交、当前集成分支独有 5 个提交）。
- **本次集成分支已有变更**：JSON Envelope 兼容、旧 Router 缩减、auth 测试 local-release skip、个股批量分析 API；详见 5 个分支独有提交和开发快照。
- **本机 Canonical DuckDB**：`~/.tradingagents/astock/astock.duckdb`，冻结时 18,100,224 bytes、`kline_bars` 共 66,794 行。它是运行时数据，未纳入 Git。
- **四大指数已仅写入本机 DB**：`000001.SH` 8,688 行、`399001.SZ` 8,596 行、`000300.SH` 5,955 行、`399006.SZ` 3,920 行；均最新至 2026-07-23。数据导入没有对应的源码提交。
- **服务状态**：已停止，5860 无监听进程；冻结期间不要重启服务或继续写入 DB。
- **已证实运行期问题**：K 线查询接口可从 DB 读取指数数据；但 `/api/v1/market/overview` 仍返回 `source=mock` / `is_mock=true`，市场摘要因此显示 0。这是未修复的产品问题。
- **发布证据需要复核**：`.hermes-workflow/evidence/local-release/overview.md` 中的 `LOCAL_RELEASE_READY` / G12 结论早于上述真实运行期问题，且 Codex 验收受沙箱端口限制影响；它不能作为当前正式发布签署。
- **不要复述为“265/265 全绿”**：最近一次完整 verifier 实测为 `262 passed, 3 failed`；其中一个失败是服务占用 DuckDB 锁，另外两个与 auth 配置有关。需要在停止服务的干净环境中重新建立基线。

## Open decisions

1. 保持市场总览 API 的现有响应契约，在 `routes_market_data.py` 内直接查询 Store，还是新增 V1.7 Repository 查询并迁移路由。优先后者，避免重新引入旁路。
2. `fix/xg-dev-data-loop-v033` 与 `xg_dev` 已分叉；恢复后先 rebase/merge 还是保持集成分支，必须先比较两侧 3/5 个提交，不要直接合并。
3. 指数导入需产品化为受控 refresh/seed 流程并加数据 lineage；不得继续用临时 Python 直写数据库。

## Skills to use

1. `systematic-debugging` — 追踪 `/market/overview` 到 mock fallback 的根因，先取证再修改。
2. `test-driven-development` — 先建立“DB 有四大指数时 overview 不得 mock/0”的回归测试。
3. `post-fix-self-review` — 检查 Flask Envelope、异常路径、重复 refresh 和 Store 并发锁。
4. `github-workflows` — 恢复后先核验分支祖先关系及远端状态，再集成到 `xg_dev`。

## Artifacts

- 开发快照：`.dev-snapshot-2026-07-24.md`
- 冻结分支：`fix/xg-dev-data-loop-v033`
- 主分支工作树：`/Users/fky/Desktop/Suozp/Code/k-codes/ai-lab/k_TradingAgents`（`xg_dev`；含用户已有未提交文件，冻结时不要改动）
- 核心待修路由：`tradingagents/astock/api/routes_market_data.py`
- 旧兼容 Router：`tradingagents/astock/data_sources/router.py`
- V1.7 DataFacade：`tradingagents/astock/data_sources/router_v17.py`
- 本地发布 Evidence：`.hermes-workflow/evidence/local-release/overview.md`
- 数据循环验证脚本：`scripts/verify_astock_data_loop.sh`

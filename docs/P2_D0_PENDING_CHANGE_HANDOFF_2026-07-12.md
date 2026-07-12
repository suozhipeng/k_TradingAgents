# P2-D0 待修改项交接清单（2026-07-12）

## 范围

本清单记录当前工作区尚未提交的 P2-D0 改动：为正式 React Data Hub 建立服务端数据刷新契约，并使真实行情刷新可以按本地缓存的最新 K 线增量写入。

## 已完成的待提交改动

| 范围 | 文件 | 内容 |
| --- | --- | --- |
| 服务端刷新契约 | `tradingagents/astock/api/routes_data_jobs.py` | 新增 `GET /api/v1/data/refresh/options`，服务端返回本地可用标的、支持周期、默认周期、刷新模式和估值开关。 |
| 增量行情刷新 | `tradingagents/astock/api/routes_data_jobs.py` | `POST /api/v1/data/jobs/refresh` 新增 `mode=incremental`；服务端从该标的/周期的最新 K 线向前重叠一个周期作为起点，通过既有 loader/store upsert 写入缓存。 |
| 参数校验 | `tradingagents/astock/api/routes_data_jobs.py` | 拒绝空周期、未知周期、非法模式、增量模式手工传入 `start`、以及 `start > end`。 |
| 返回语义 | `tradingagents/astock/api/routes_data_jobs.py` | K 线结果返回 `requested_start`、`requested_end`、`rows_upserted`；不伪造新增/更新/跳过的细分计数。 |
| 审计事件 | `tradingagents/astock/api/app_factory.py` | `DataJobManager` 接入 Store，刷新过程可写入审计事件；任务列表仍是进程内状态，重启后不承诺恢复。 |
| 可选依赖 | `pyproject.toml` | 新增 `astock-artifacts` extra：`python-pptx`、`pyarrow`。 |
| API 测试 | `tests/test_astock_api.py` | 覆盖服务端 options、非法刷新契约和单周期重叠式增量起点。 |
| 文档 | `docs/03-operations.md`、`docs/API_REFERENCE.md`、`docs/CHANGELOG.md` | 同步刷新、缓存、审计和返回字段的真实边界。 |

## 尚未完成 / 提交前门禁

1. `pyproject.toml` 尚未声明 Flask 与 Flask-Cors 运行时依赖；当前重建虚拟环境后 API 测试会因缺少 `flask` 失败。应先补齐依赖并重新安装，再运行：

   ```bash
   .venv/bin/pytest tests/test_astock_api.py tests/test_astock_store.py tests/test_astock_ppt.py
   ```

2. `uv.lock` 是工作区已有的独立修改（项目版本变更），本次不应覆盖或混入 P2-D0 提交。依赖声明确定后需由负责该 lock 变更的人统一重新生成/合并锁文件。

3. React/TypeScript 仍未接入上述契约；当前尚不能宣称 React 已成为正式产品面。下一阶段应以 `GET /data/refresh/options` 和刷新任务 API 驱动 Data Hub，并补齐前端测试、构建门禁、运行时 API 基址配置和正式路由。

4. 任务状态事件已可审计，但任务列表尚不具备重启恢复能力；在实现持久化 job 实体及恢复逻辑前，界面必须显示其进程内边界。

## 提交边界建议

建议形成单独的 P2-D0 提交，仅纳入本清单所列 API、测试、依赖 extra 与文档改动；显式排除 `uv.lock`。在 Flask 运行时依赖和测试验证完成前，不应提交。

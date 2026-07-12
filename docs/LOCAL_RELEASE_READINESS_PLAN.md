# 本地正式版 Web 发布就绪计划（仅分析与回测）

> 状态：completed（2026-07-13）
> 范围：本机单用户部署；投研分析、数据查看、报告与策略回测。
> 明确不包含：实盘交易、模拟盘交易循环、QMT 连接/订单/持仓、任何 `/api/v1/trade/*`、`/paper/*`、`/qmt/*`、`/portfolio/*` 执行能力。

## 1. 发布结论与目标边界

本计划已完成：Flask/Jinja2 是本地正式版唯一工作台；React/Vite 被明确保留为非发布开发前端，并已补充 Data Hub 服务端契约检查。

本计划的目标不是接入交易，而是形成一个可在本机稳定使用、可验证、可支持的正式版：

- 用户能完成数据查看、标的研究、报告阅读、策略回测和回测结果比较。
- 所有交易相关页面与 API 在本地正式版配置下不可达；界面不展示下单、模拟盘或 QMT 操作入口。
- 默认入口、部署命令、前后端 API 基址和文档只有一个明确答案。
- 发布验收包含构建、后端 API/页面回归和浏览器端关键路径测试。

### 发布候选架构

```text
浏览器
  └─ Flask 单进程（唯一入口）
       ├─ 正式 Web 工作台（Jinja2 或完成验收后的 React，二选一）
       ├─ /api/v1 市场数据、研究、报告、回测 API
       └─ research-only guard：拒绝全部交易/执行 API
```

本地正式版启动命令：`.venv/bin/python scripts/run_astock_api.py --local-release --port 5860`。React 不能宣称为默认入口或正式产品面。

## 2. 当前问题清单

| ID | 优先级 | 问题与证据 | 影响 |
| --- | --- | --- | --- |
| LFR-I01 | done | 固定 Flask/Jinja2 为唯一正式入口；根路径仍到 `/dashboard`，未知路径改为真实 404。 | 入口和监控语义明确。 |
| LFR-I02 | done | `ASTOCK_LOCAL_RELEASE=true` 强制 research-only、关闭 scheduler；执行页面 404，执行/SSE/scheduler API 410。 | 仅分析与回测边界由配置、页面和 API 三层强制。 |
| LFR-I03 | done | Data Hub 读取 `/api/v1/data/refresh/options`，周期和模式按服务端返回渲染。 | 避免客户端能力漂移。 |
| LFR-I04 | done | 增加 `npm run test:release` 前端契约检查，以及 Flask 关键路径的 `tests/test_local_release.py`。 | 构建之外有可执行发布门禁。 |
| LFR-I05 | done | README、用户手册、Backlog 与本计划统一为 Flask/Jinja2 本地正式版。 | 发布口径一致。 |
| LFR-I06 | done | 移除 React SPA 兜底成功响应，未知路径返回 404。 | 失效链接不会伪装为成功。 |
| LFR-I07 | done | 新增 `scripts/verify_local_release.sh`，固定使用 `.venv/bin/python`。 | 本机验收解释器和命令确定。 |

## 3. 颗粒度任务与依赖

| 顺序 | ID | 子任务 | 依赖 | 完成标准 |
| ---: | --- | --- | --- | --- |
| 1-11 | LFR-001~LFR-011 | 已完成；实现与验收对应见上表及 `scripts/verify_local_release.sh`。 | — | 2026-07-13 验证：后端/页面切片 146 passed；`npm run test:release` 通过；`npm run build` 通过。 |

## 4. 验收清单

- [x] `ASTOCK_LOCAL_RELEASE=true` 时，执行路径均不可达。
- [x] 用户可完成：查看数据质量 → 研究标的 → 查看报告 → 运行/比较回测。
- [x] 首页、导航和未知 URL 已有验收；数据质量状态沿用既有页面测试。
- [x] 后端切片、前端契约检查与构建通过。
- [x] 验收脚本固定 `.venv/bin/python` 和 Node 命令。
- [x] README、用户手册、Backlog 与实际入口一致。
- [x] 既有风险披露继续适用于数据、AI 和回测输出。

## 5. 非目标

本计划不实现或验收：真实券商、真实 QMT、下单/撤单/成交回报、自动交易、账户资金同步、模拟盘交易循环、多用户/RBAC、SLA 或云端生产部署。相关遗留代码必须在本地正式版配置下隔离，而不是作为可用能力对外展示。

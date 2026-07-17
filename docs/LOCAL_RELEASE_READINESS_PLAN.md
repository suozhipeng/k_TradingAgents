# 本地正式版 Web 发布就绪计划（仅分析与回测）

> 状态：产品实现 completed；运行前置条件待操作员验收（2026-07-17，v0.3.2）
> 范围：本机单用户部署；投研分析、数据查看、报告与策略回测。
> 明确不包含：实盘交易、模拟盘交易循环、QMT 连接/订单/持仓、任何 `/api/v1/trade/*`、`/paper/*`、`/qmt/*`、`/portfolio/*` 执行能力。

## 1. 发布结论与目标边界

本计划已完成：Flask/Jinja2 是本地正式版唯一工作台；React/Vite、Streamlit 及旧启动壳已从仓库产品面移除。

本计划的目标不是接入交易，而是形成一个可在本机稳定使用、可验证、可支持的正式版：

- 用户能完成数据查看、标的研究、报告阅读、策略回测和回测结果比较。
- 所有交易相关页面与 API 在本地正式版配置下不可达；界面不展示下单、模拟盘或 QMT 操作入口。
- 默认入口、部署命令、前后端 API 基址和文档只有一个明确答案。
- 发布验收包含构建、后端 API/页面回归和浏览器端关键路径测试。

### 发布候选架构

```text
浏览器
  └─ Flask 单进程（唯一入口）
       ├─ 正式 Web 工作台（Jinja2）
       ├─ /api/v1 市场数据、研究、报告、回测 API
       └─ research-only guard：拒绝全部交易/执行 API
```

本地正式版启动命令：`.venv/bin/python scripts/run_astock_api.py --port 5860`。这是唯一启动器，固定 local-release、固定单 worker、固定关闭 scheduler；服务默认仅绑定 `127.0.0.1`，由于本地模式免 Bearer 鉴权，启动器会拒绝 `0.0.0.0` 等非回环绑定。

## 2. 当前问题清单

| ID | 优先级 | 问题与证据 | 影响 |
| --- | --- | --- | --- |
| LFR-I01 | done | 固定 Flask/Jinja2 为唯一正式入口；根路径仍到 `/dashboard`，未知路径改为真实 404。 | 入口和监控语义明确。 |
| LFR-I02 | done | 唯一启动器固定 local-release，强制 research-only、关闭 scheduler；本地免鉴权仅开放产品 API allowlist，执行、通知、运维、管理和 SSE/scheduler API 410。 | 仅分析与回测边界由配置、页面和 API 三层强制。 |
| LFR-I03 | done | Data Hub 读取 `/api/v1/data/refresh/options`，周期和模式按服务端返回渲染。 | 避免客户端能力漂移。 |
| LFR-I04 | done | Flask 关键路径由本地测试验证；Playwright Chromium 冒烟已纳入 CI。 | 构建之外有可执行发布门禁。 |
| LFR-I05 | done | README、用户手册、Backlog 与本计划统一为 Flask/Jinja2 本地正式版。 | 发布口径一致。 |
| LFR-I06 | done | 移除 React SPA 兜底成功响应，未知路径返回 404。 | 失效链接不会伪装为成功。 |
| LFR-I07 | done | 新增 `scripts/verify_local_release.sh`，固定使用 `.venv/bin/python`。 | 本机验收解释器和命令确定。 |

## 3. 颗粒度任务与依赖

| 顺序 | ID | 子任务 | 依赖 | 完成标准 |
| ---: | --- | --- | --- | --- |
| 1-11 | LFR-001~LFR-011 | 已完成；实现与验收对应见上表及 `scripts/verify_local_release.sh`。 | — | 2026-07-15 验证：本地发布门禁 170 passed；离线非集成、非浏览器回归 1174 passed、7 skipped、9 deselected。 |

## 4. 验收清单

- [x] local-release 时，执行路径及未完成的 Ops Audit 页面均不可达；Settings 隐藏未完成通知渠道。
- [x] 用户可完成：查看数据质量 → 研究标的 → 查看报告 → 运行/比较回测。
- [x] 首页、导航和未知 URL 已有验收；数据质量状态沿用既有页面测试。
- [x] 后端切片通过；真实 Chromium Dashboard 冒烟由 CI 安装运行时并执行。
- [x] 验收脚本固定 `.venv/bin/python`；CI 负责安装浏览器运行时。
- [x] README、用户手册、Backlog 与实际入口一致。
- [x] 既有风险披露继续适用于数据、AI 和回测输出。

### 验证边界

本地正式版发布门禁是 `scripts/verify_local_release.sh`；完整离线回归和 Chromium 浏览器测试由 CI 执行。可复现的本机安装、Parquet/Pydantic gate 和浏览器运行路径见 [`LOCAL_RELEASE_VERIFICATION.md`](LOCAL_RELEASE_VERIFICATION.md)。安装 `.venv/bin/python -m pip install -e ".[local-release]"` 后，运行 `.venv/bin/python -m playwright install chromium` 和 `scripts/verify_local_release.sh --browser` 即可执行完整门禁。在空本地库中，先显式 `/api/v1/market/kline?symbol=600519.SH&interval=1d&refresh=1` 初始化；分钟线使用 `interval=1m|5m|15m|30m|60m`，同样会增量写入热库与永久仓库。真实 LLM 和有 cookie 的 Provider 验收不使用离线基线伪造通过，见用户手册的外部凭据前置条件。

已配置有效 `DEEPSEEK_API_KEY` 时，`tests/test_deepseek_reasoning.py::TestDeepSeekLiveStructuredOutput::test_v4_flash_returns_structured_output` 已于 2026-07-13 通过 live 验收。凭据只应由运行环境注入，禁止写入代码、文档或版本库。

## 5. 非目标

本计划不实现或验收：真实券商、真实 QMT、下单/撤单/成交回报、自动交易、账户资金同步、模拟盘交易循环、多用户/RBAC、SLA 或云端生产部署。相关遗留代码必须在本地正式版配置下隔离，而不是作为可用能力对外展示。

## 6. 投入正式使用前的操作员验收

本地正式版的代码范围已完成，但每台实际使用的机器仍须完成下列验收；未通过 P0 项不得将 AI 投研、网络行情或本地数据仓库宣称为可用。

| 优先级 | 验收项 | 操作与通过标准 |
| --- | --- | --- |
| P0 | LLM 凭据 | 轮换任何曾暴露或失效的 API key；只通过受控环境变量或未纳入版本控制的 `.env` 注入。运行 `scripts/check_astock_live_research_env.py`，再以显式授权运行真实、只读的 LLM smoke test；401/认证失败必须阻断发布。 |
| P0 | 行情 Provider | 对实际启用的 Provider 逐项执行 live research preflight 和只读网络验证，确认授权、网络、限流、时区及分钟线质量。离线 fixture 不能替代此验收。 |
| P0 | 本地数据保护 | 确认 `kline/kline.duckdb` 位于受控本地磁盘；在首次使用前完成一次备份、恢复和空库增量刷新演练，并记录备份目录与保留周期。 |
| P0 | 软件供应链 | 在发布流水线加入 lockfile 一致性及依赖漏洞扫描（例如 `pip-audit`）；当前 `pip check` 仅能验证已安装包的依赖关系，不能替代 CVE 扫描。 |
| P1 | 可运维性 | 配置日志轮转、磁盘空间检查、数据库健康检查以及 Provider 失败提示；长期运行时定期复查数据新鲜度和备份恢复能力。 |
| P1 | 文档一致性 | 每次版本发布时同步 `pyproject.toml`、README、CHANGELOG 和本计划中的版本、范围与验收结果。 |

### 部署边界

此验收只适用于回环绑定的单进程、本机单用户工作台。应用会拒绝 `WEB_CONCURRENCY > 1`，因为 SSE、后台任务和报告缓存仍是进程内状态。若要部署为公网、多用户或多进程服务，必须先引入统一身份认证与 RBAC、HTTPS、共享 Redis/任务队列、共享状态存储、监控告警和灾备演练；该场景不属于本地正式版的发布承诺。实盘或自动交易还必须另行建立券商订单生命周期、成交回报核对、组合级限额、独立审计与人工审批闭环。

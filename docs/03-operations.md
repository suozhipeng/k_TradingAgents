# 运维文档

> 合规、数据源、部署、在线研究、实盘交易和风险台账的整合文档。

## 目录

- [1. 合规与风险管理](#1-合规与风险管理)
- [2. 数据源管理](#2-数据源管理)
- [3. 部署指南](#3-部署指南)
- [4. 在线研究](#4-在线研究)
- [5. 实盘交易](#5-实盘交易)
- [6. 风险台账](#6-风险台账)

---

## 合规与风险管理

# A 股风险披露、合规边界与隐私声明

| 更新时间：2026-07-08 |

本文定义 TradingAgents-Astock 的风险披露、投资建议边界、数据风险和交易责任边界。它用于支持商用场景下的产品说明、页面提示和实盘前合规检查。

### 数据刷新与本地缓存

- 正式 Data Hub 通过 `GET /api/v1/data/refresh/options` 获取标的、周期与模式，前端不得自行硬编码周期或增量规则。
- `POST /api/v1/data/jobs/refresh` 支持 `range` 与 `incremental`：后者由服务端从本地该标的/周期的最新 bar 前推一个周期作为重叠刷新起点，再以 upsert 写入本地 Store。
- 刷新计划会对重复的 `symbols` 和 `intervals` 去重；每个 `symbol:interval` 在一次任务中只执行一次。超过 3 个 K 线请求时使用线程池并发拉取，但写入仍由 Store 的锁顺序化，避免破坏本地数据库一致性。
- 所有 provider 调用经过进程内共享的按源治理器：默认全局最多 5 条在途网络请求、单源最多 1 条、相邻请求最少间隔 0.25 秒；检测到 429/频率限制后，该源默认冷却 15 秒并继续尝试路由 fallback。可通过 `ASTOCK_NETWORK_MAX_CONCURRENCY`、`ASTOCK_PROVIDER_MAX_CONCURRENCY`、`ASTOCK_PROVIDER_MIN_INTERVAL_SECONDS` 和 `ASTOCK_PROVIDER_COOLDOWN_SECONDS` 调整；生产环境应从保守值逐步放宽。
- Data Hub 刷新请求可传入 `max_concurrency`（1～5，默认 5）与 `timeout_seconds`（1～3600，默认 300）。等待网络槽位、节流和整批刷新均有截止时间；到期的未完成项返回可重试的 `timeout`，不再无限等待；超时后迟到的 K 线结果不会再写入本地库。第三方 HTTP/SDK adapter 仍必须保留自身连接/读取超时。
- provider 主动返回超时时，刷新会在 deadline 内做指数退避重试：K 线默认最多重试 3 次，估值默认最多重试 2 次；可通过 `timeout_retries`（0～3）覆盖 K 线次数，或通过 `ASTOCK_KLINE_TIMEOUT_RETRIES`、`ASTOCK_VALUATION_TIMEOUT_RETRIES` 配置默认值。任务结果以 `retry_count` 记录实际重试次数。
- 单个标的请求失败不会中止整批刷新。任务结果的 K 线项返回 `status`、`requested_start`、`requested_end`、`rows_upserted`；失败项额外返回稳定的 `error.code`、受限长度的 `error.message` 与 `error.retryable`。当前错误码包括 `rate_limited`、`timeout`、`source_unavailable`、`network_error`、`no_data` 和 `unexpected_error`。调用方应以 `failure_count` 判断部分失败，不应只根据任务总状态判断数据完整性。
- 本地 DuckDB 是单写入分析库：网络和计算可并发，写入由 Store 锁批处理；需要多进程/多用户高并发写入时必须切换 PostgreSQL/TimescaleDB（连接池由 `PG_POOL_SIZE` 配置）。入库层兼容常见中英文行情字段和数值字符串；无法解析日期或 OHLC 的行会写入 `data_quarantine`（`rule_id=field_compatibility`、`severity=error`）并输出 `KLINE_FIELD_EXCEPTION` 结构化错误日志，同批有效数据继续写入，管理员可通过隔离记录手动修复和关闭。
- 刷新任务会持久化状态事件用于审计；任务列表本身仍是进程内视图，服务重启后不承诺恢复为可轮询任务。
- `rows_upserted` 是本次受影响行数，不等同于新增、更新或跳过的拆分计数；在没有数据库差分计数器前不得展示这些虚假明细。
- 用于回测的永久 K 线仓库默认是项目根目录的 `kline/kline.duckdb`（可用 `ASTOCK_PERMANENT_KLINE_DB_PATH` 覆盖）。交互查询完成日线增量刷新后会同步该仓库；若当日有日 K，则同样同步当日 5 分钟 K。首次同步会把热库中该标的/周期的完整已有序列回填，之后按永久库自身的最新 bar 重叠 upsert，因此短暂失败后的下一次查询能自动补齐。
- 分钟 K 的归档/清理只针对应用热库，默认仅预览；永久仓库不参与清理。只有在已确认永久库同步成功且归档文件校验通过时，才应以 `confirm_delete=true` 删除热库历史数据。可用 `ASTOCK_PERMANENT_KLINE_ENABLED=false` 显式关闭永久镜像（不建议用于回测环境）。
- 回测默认只读永久仓库，结果会记录 `permanent_local_duckdb` 数据来源；如确有需要才设置 `ASTOCK_BACKTEST_ALLOW_LIVE_FALLBACK=true` 允许网络回补。回测历史接口支持 `limit`、`offset`，列表页可使用 `include_curve=false` 避免传输完整净值曲线。
- `GET /api/v1/market/screener` 以单次窗口查询读取最近 120 根日 K，默认最多扫描 2,000 个标的（`scan_limit` 最大 5,000）。`/api/v1/tv/history` 单次最多返回 5,000 根 bar。
- 后台数据任务有有界等待队列（默认 `ASTOCK_DATA_JOB_MAX_QUEUED=100`）；队列饱和返回 HTTP 429。仪表盘表统计默认缓存 30 秒（`ASTOCK_DASHBOARD_STATS_TTL_SECONDS`）。可通过 `POST /api/v1/data/maintenance` 对热库和永久库执行 `CHECKPOINT + ANALYZE`。
- 历史回测默认不会访问外部停牌/涨跌停接口，确保本地数据可复现；需要该附加校验时，在回测请求中传入 `enable_external_constraints=true`，同一运行内会按标的和日期缓存。Alpha Vantage 使用共享连接与 Provider 限流器，超时由 `ASTOCK_ALPHA_VANTAGE_TIMEOUT_SECONDS` 控制（默认 15 秒）。
- 进程内 SSE、任务队列和 LLM 报告缓存仅适用于单 API worker。设置 `WEB_CONCURRENCY>1` 会输出告警；横向扩展前须提供共享 Redis/PostgreSQL 协调后端，避免事件和任务状态分裂。
- 已归档的分钟 K 写入按月 Parquet，并在热库创建 `kline_bars_cold` DuckDB 视图供审计和冷数据查询；永久回测库不清理这些分钟 K。
- 市场领先池刷新仅允许 `POST /api/v1/market/leading-pool/refresh`；`GET /market/leading-pool` 与 `GET /market/momentum` 保持只读，不再由 `refresh=1` 改变服务端状态。健康探针分为 `/api/v1/health/live`（进程存活）与 `/api/v1/health/ready`（实际探测热库和永久库）；旧 `/health` 保持为 readiness 兼容别名。
- 每个 API 响应携带 `X-Request-ID` 与 `X-Response-Time-Ms`。`GET /api/v1/ops/metrics` 可查看进程内请求量、平均延迟和数据任务状态。它用于单进程本地运维；横向扩展请接入集中式指标系统。
- DuckDB 恢复会先验证备份中存在受管表，再在单个事务内重建；任一表失败即回滚，不再出现部分恢复状态。CI 位于 `.github/workflows/ci.yml`，执行无外部密钥的后端测试与前端构建。
- 所有 API K 线写入路径（单标的刷新、Data Hub 批量任务、查询 fallback、TradingView fallback）均通过 Loader 同步到永久仓库；不再依赖某个查询接口的事后镜像。`GET /api/v1/kline` 与 `/api/v1/tv/history` 可传 `include_cold=true` 合并读取热库和 `kline_bars_cold` Parquet 视图。
- AI 主链与展示 LLM 使用进程级有界执行器，容量饱和会返回可重试错误；报告缓存通过 `ASTOCK_LLM_REPORT_CACHE_MAX_ENTRIES`（默认 100）限制容量并按 TTL 清理。`/ops/metrics` 以路由模板聚合，避免动态 ID 导致指标基数膨胀，且在启用认证时仅管理员可访问。
- 所有会产生副作用的 HTTP 写请求均可带 `Idempotency-Key`（8～128 位字母、数字、`. _ : -`）。同一 API 进程在 `ASTOCK_IDEMPOTENCY_TTL_SECONDS`（默认 300 秒）内对相同调用方、相同 key、相同请求体仅执行一次，并以原始响应重放；若同 key 对应不同请求或仍在执行中，返回 `409`。该保护是进程内机制，多 worker 部署前应替换为 Redis 之类的共享存储。
- 回测响应和持久化历史新增 `data_lineage` 与 `reproducibility`：记录数据源/质量、区间、bar 数、市场时区、回补与 mock 状态、策略类与状态、费用配置、运行版本和 `input_fingerprint`。使用相同输入指纹可定位同一可重现实验；没有设置 `GIT_SHA` 时版本字段为 `unknown`，生产发布应注入提交 SHA。
- 市场日期统一按 `Asia/Shanghai` 计算（可用 `ASTOCK_MARKET_TIMEZONE` 标注运行配置），避免海外服务器跨日后错误触发“当日”日线与 5 分钟线刷新。
- API 默认返回 CSP、`nosniff`、`no-referrer` 与最小权限 `Permissions-Policy` 响应头；会话 Cookie 使用 `HttpOnly` 与 `SameSite=Lax`，HTTPS 部署设置 `ASTOCK_COOKIE_SECURE=true`。通知 webhook 禁止私网/回环地址与重定向，并支持在 channel 配置 `signing_secret` 时发送 canonical JSON 的 `X-AStock-Signature: sha256=…`。邮件通知会 HTML 转义事件字段。

### 备份、恢复与发布演练

- 永久回测仓库 `kline/kline.duckdb` 与应用热库必须分别备份；分钟 Parquet 归档目录也必须纳入同一保留策略。恢复后先运行 `/api/v1/health/ready`，随机核对一个标的的日线、5 分钟线行数与最新时间，再恢复对外流量。
- 数据库结构变更应先在备份副本演练升级和回滚。迁移前记录版本与校验和；若回滚不可逆，使用恢复到迁移前备份而不是手工删表。
- 发布采用单实例灰度：先验证 readiness、`/ops/metrics`、日线增量刷新、回测输入指纹和 webhook 签名，再逐步扩容。出现 provider 错误率、队列饱和或延迟异常时，停止扩容并回滚到上一构建。
- 进行压测时使用 mock/provider stub 与独立数据库；重点覆盖并发 K 线查询、带相同 `Idempotency-Key` 的重试、数据任务队列饱和和回测超时，禁止以第三方免费行情源作为压测目标。

### 生产边界与容量控制

- Flask 对请求体实行 `MAX_CONTENT_LENGTH` 上限，默认 1 MiB（`ASTOCK_MAX_REQUEST_BYTES`）；API 按 API key 或源 IP 使用进程内固定窗口限流，默认每分钟 300 次（`ASTOCK_RATE_LIMIT_PER_MINUTE`）。健康检查不受此限制。多实例部署必须在网关或 Redis 实现共享限流，进程内限流只作为最后一道保护。
- SSE 客户端有 `ASTOCK_SSE_MAX_CLIENTS` 上限（默认 50），超过即返回 `429`；响应显式禁用代理缓冲。SSE、任务、幂等和缓存的进程内实现适用于单 worker。Docker 默认改为单 worker；扩容前必须迁移到 Redis Streams/队列和共享幂等存储。
- Router 内存缓存已具有线程锁与容量上限，文件缓存通过临时文件原子替换，避免并发读写产生半截 JSON。仍应通过缓存命中率、淘汰数、活跃 SSE 数、任务队列长度和 provider 错误率接入集中式指标平台。
- webhook 的签名请求包含 canonical JSON、`X-AStock-Signature`、`X-AStock-Timestamp` 和 `X-AStock-Event-ID`。接收方必须验证 HMAC、事件 ID 去重，并拒绝超过自身时钟窗口的时间戳；未配置 `signing_secret` 时不会生成签名。
- Compose 不再内置数据库密码，必须通过部署环境或 secret manager 提供 `PG_PASSWORD`、`CLICKHOUSE_PASSWORD` 和 `PGADMIN_PASSWORD`；PostgreSQL 与 ClickHouse 默认只暴露容器内部网络。生产环境还应固定镜像版本、启用镜像/SBOM 漏洞扫描、限制 CPU/内存、配置日志轮转与 TLS 反向代理/HSTS。
- Compose 同时要求显式设置 `CORS_ORIGIN`，不能将本地开发源带入生产。ClickHouse 健康检查直接读取容器内的 `CLICKHOUSE_PASSWORD`，避免密码与运行配置漂移。每个已认证写请求按 API key 保存的 `rate_limit` 执行；匿名请求使用全局默认值。

### 产品性质

TradingAgents-Astock 当前定位为：

```text
投研分析 + 策略验证 + 模拟盘 + 受控执行试运行平台
```

不是：

```text
完整自动实盘生产交易系统
```

系统输出的 AI 分析、策略结果、回测结果和 advisory chain 仅用于研究辅助、策略验证和风险提示，不构成确定性投资收益承诺。

### 投资建议边界

- AI 输出是研究辅助结论，不是保证盈利的交易建议。
- 回测结果不代表未来收益。
- 模拟盘结果不代表真实成交结果。
- managed/QMT 能力不等同于完整自动交易系统。
- 用户必须自行承担投资决策和交易风险。

### 数据风险

系统可能受到以下数据风险影响：

- provider 不可用。
- 数据延迟。
- 数据缺失。
- fallback 后数据口径变化。
- 复权方式不同导致结果差异。
- 停牌、涨跌停、ST、退市状态处理不完整。
- 新闻、公告、研报来源存在延迟或遗漏。

所有研究、回测和交易辅助页面必须尽量展示数据来源、更新时间和质量状态。

### AI 风险

AI 分析可能存在：

- 幻觉。
- 引用不完整。
- 对行情或公告理解错误。
- prompt 或模型版本变化导致结论变化。
- 上下文数据缺失导致判断偏差。

AI 结论必须保持 advisory，不得直接触发真实交易。

### 回测风险

回测可能存在：

- survivorship bias。
- look-ahead bias。
- 未来函数。
- 样本内过拟合。
- 成交假设过于乐观。
- 成本、滑点、涨跌停、停牌、T+1 未充分模拟。

所有 Strategy Lab 结果必须展示数据区间、成本模型、复权方式、benchmark 和是否样本外。

### 交易风险

真实或受控执行可能存在：

- 券商接口不可用。
- 订单拒绝、超时、部分成交。
- 本地状态与券商状态不一致。
- 行情延迟导致价格偏差。
- 风控配置错误。
- 人工确认错误。

系统必须提供 kill switch、风控门、人工确认和审计记录。未完成 live-ready checklist 前，不得对外宣称自动实盘生产能力。

### 页面提示要求

以下页面必须显示能力或风险提示：

| 页面/模块 | 必须提示 |
|---|---|
| AI Research | AI 结论仅供研究参考，显示模型、时间和数据来源 |
| Strategy Lab | 回测不代表未来收益，显示数据假设和成本模型 |
| Market Leaders | 候选池不构成买入建议，显示入池理由和数据来源 |
| Trading | 明确 research/paper/managed/live-ready 模式 |
| Paper | 虚拟资金、虚拟成交、非真实账户 |
| QMT/Managed | 需要人工确认和风控门 |
| Data & Ops | 数据延迟、fallback、provider 状态 |

### 商用前置条件

商用前必须具备：

- 明确产品说明和风险披露。
- 数据来源和授权边界清晰。
- 日志、审计、错误和故障处理机制。
- 实盘能力不夸大。
- 所有交易相关路径有人工确认和风控门。
- 对外材料不得承诺收益。

### 不做承诺

系统不承诺：

- 保证盈利。
- 保证数据实时无误。
- 保证 AI 结论正确。
- 保证回测收益可复现到实盘。
- 保证券商接口永远可用。

### 后续落地

- Phase 30：将风险披露接入实盘准入 checklist。
- Phase 31：将数据风险接入 Data Quality 标签。
- Phase 32：将回测风险接入 Strategy Lab 结果页。
- Phase 33：将 AI 风险接入 AI Research 报告页。
- Phase 35：将交易风险接入 Trading 页面和订单确认流程。

---

### 数据隐私声明

> 合并自 `03-ops/privacy.md`

#### 数据收集范围

TradingAgents-Astock 是本地部署的分析工具，默认不向任何第三方发送用户数据。本地存储包括 DuckDB 数据文件、缓存、配置文件、分析报告、决策日志和检查点。

发送到第三方的数据仅包括：LLM 请求（ticker、日期、上下文数据）、数据源请求（ticker、日期）、公开新闻/社交数据抓取。

#### API Key 安全

- API Key 存储在本地 `.env` 文件中，已加入 `.gitignore`
- 系统不收集、不上传、不记录 API Key

#### 用户权利

- 访问：所有本地数据可通过文件系统直接访问
- 删除：删除本地文件即可清除所有数据
- 导出：报告可通过 API 导出为 Markdown/JSON/PPT

#### 合规说明

本工具为本地部署的研究分析工具，不涉及用户账号体系和个人信息收集。如进入多用户部署或企业交付阶段，需重新评估并补充隐私合规文档。

---

## 数据源管理

# A 股数据源授权与使用边界

| 更新时间：2026-07-08（数据库模块 v1.0 已发布） |

本文记录 TradingAgents-Astock 核心功能使用外部数据源时的来源、用途、标注和使用边界。本文只用于指导数据接入、AI Research、回测和 WebUI 展示，不构成法律意见，也不扩展为完整法务审查文档。

### 数据源分类

| 类别 | 示例 | 用途 | 核心功能检查 |
|---|---|---|---|
| 行情 | mootdx、Tencent、EastMoney、Sina、akshare 聚合接口 | K 线、报价、板块、资金线索 | 授权、频率限制、延迟、缓存边界 |
| 基础资料 | akshare、交易所公开数据、F10 类信息 | 股票基础资料、行业、财务摘要 | 来源条款、再分发限制 |
| 新闻公告 | 公告、新闻、研报摘要 provider | AI Research 上下文 | 版权、摘要范围、引用要求 |
| 券商/QMT | QMT 本地接口 | managed execution、账户/订单联调 | 券商协议、使用场景、账号授权 |
| LLM provider | OpenAI/其他模型服务 | AI 分析与报告生成 | 输出使用条款、数据输入边界 |

### 产品标注要求

所有数据输出应尽量展示：

- `source`：数据来源。
- `provider`：具体 provider 或 fallback provider。
- `freshness`：数据更新时间或延迟状态。
- `quality`：normal / stale / partial / fallback / mock。
- `license_note`：必要时标注“需确认授权”。
- `snapshot_id`：进入回测、AI、交易建议前的数据快照引用。

### 禁止事项

在未确认授权前，不应：

- 对外宣称数据可商用再分发。
- 把第三方行情、新闻、研报全文作为产品卖点。
- 隐藏数据来源和更新时间。
- 把 fallback 数据误标为 primary source。
- 把 mock 或缓存数据误标为实时真实数据。

### 数据使用策略

后续开发应采用以下策略：

- UI 和 API 默认展示来源、更新时间、质量标签。
- AI Research 引用数据时保留 provider 和快照。
- 回测结果展示数据口径、复权方式和数据质量。
- 交易页只把数据作为辅助输入，不把不明来源数据作为自动执行依据。
- 对无法确认授权的数据，标记为 research-only。

### 与其他文档关系

- 字段定义、质量标签、数据血缘的完整规范见 `full_function_documentation.md` §7。
- API source/meta 要求见 `01-architecture.md`。
- 风险披露见 `03-operations.md`。
- 数据源检查必须进入 `04-development.md` 的验收证据。

### 验收要求

涉及新增数据源的 phase 必须提供：

- provider 名称和用途。
- 是否 primary / fallback / cache / mock。
- 是否可离线测试。
- 数据更新时间和质量标签。
- 授权状态记录：`unknown`、`research-only`、`commercial-approved`。
- 未确认授权时的产品限制。


---

> 以下内容合并自 `03-operations.md`（数据字典部分）

# A 股数据字典与数据血缘

| 更新时间：2026-07-08（数据库模块 v1.0 已发布） |

本文定义 A 股数据字段、数据来源、质量标签和血缘要求。它用于支撑 Data Quality & Bias Control、Strategy Lab、AI Research、Trading 和 Ops 的生产级数据可信闭环。

### 数据域

| 数据域 | 示例 | 主要使用模块 |
|---|---|---|
| 行情 | K 线、盘口、逐笔、成交量、涨跌幅 | Research、Strategy Lab、Trading |
| 基础资料 | 股票名称、交易所、上市日期、ST、退市状态 | Data & Ops、Strategy Lab |
| 估值/财务 | PE、PB、市值、营收、利润、资产负债 | Research、AI Research |
| 新闻 | 新闻标题、来源、发布时间、正文摘要 | AI Research |
| 公告 | 公告标题、类型、发布时间、原文链接 | AI Research |
| 研报 | 机构、评级、目标价、摘要、发布时间 | AI Research |
| 资金线索 | 龙虎榜、北向资金、主力资金 | Market Leaders |
| 回测结果 | trades、periods、metrics、equity curve | Strategy Lab |
| 交易状态 | 账户、订单、成交、持仓、风控结果 | Trading |
| 审计日志 | task run、audit event、数据快照 | Ops & Audit |

### 核心字段字典

#### SecurityMaster

| 字段 | 类型 | 说明 | 质量要求 |
|---|---|---|---|
| `symbol` | string | 标准 A 股代码，如 `600519.SH` | 必须标准化 |
| `raw_symbol` | string | provider 原始代码 | 可选 |
| `name` | string | 股票名称 | 不能为空 |
| `exchange` | enum | `SH` / `SZ` / `BJ` | 必填 |
| `list_date` | date | 上市日期 | 回测防 survivorship bias 必需 |
| `delist_date` | date | 退市日期 | 可选 |
| `is_st` | bool | 是否 ST | 策略/风控必需 |
| `status` | enum | `active` / `suspended` / `delisted` | 必填 |

#### KLineBar

| 字段 | 类型 | 说明 | 质量要求 |
|---|---|---|---|
| `symbol` | string | 标准代码 | 必填 |
| `trade_date` | date/datetime | 交易日期或时间 | 必填 |
| `frequency` | enum | `1m` / `5m` / `30m` / `60m` / `1d` / `1w` / `1M` | 必填 |
| `open` | float | 开盘价 | 非负 |
| `high` | float | 最高价 | `high >= low` |
| `low` | float | 最低价 | `low <= high` |
| `close` | float | 收盘价 | 非负 |
| `volume` | float | 成交量 | 非负 |
| `amount` | float | 成交额 | 非负 |
| `adjust` | enum | `none` / `qfq` / `hfq` | 必填 |
| `provider` | string | 数据来源 | 必填 |
| `quality` | enum | `ok` / `stale` / `partial` / `fallback` / `invalid` | 必填 |

#### BacktestResult

| 字段 | 类型 | 说明 |
|---|---|---|
| `result_id` | string | 回测结果 ID |
| `strategy_name` | string | 策略名称 |
| `params` | object | 策略参数 |
| `symbols` | list[string] | 标的列表 |
| `start_date` / `end_date` | date | 数据区间 |
| `benchmark` | string | benchmark |
| `cost_model` | object | 佣金、印花税、滑点 |
| `data_assumptions` | object | 复权、停牌、涨跌停、T+1、样本外状态 |
| `metrics` | object | return、Sharpe、drawdown、win rate 等 |
| `trades` | list[object] | 交易明细 |
| `equity_curve` | list[object] | 净值曲线 |
| `data_snapshot_id` | string | 数据快照 |

#### ResearchAudit

| 字段 | 类型 | 说明 |
|---|---|---|
| `research_id` | string | 研究任务 ID |
| `symbol_scope` | list[string] | 标的范围 |
| `model` | string | 模型名称 |
| `prompt_hash` | string | prompt 哈希 |
| `context_snapshot_id` | string | 输入上下文快照 |
| `citations` | list[object] | 引用来源 |
| `generated_at` | datetime | 生成时间 |
| `confirmation_status` | enum | `none` / `reviewed` / `rejected` |

### 数据血缘要求

每个数据对象必须能回答：

- 来源 provider 是什么？
- 是否来自 cache / DuckDB / live provider / mock？
- 何时生成或刷新？
- 是否发生 fallback？
- 是否有质量降级？
- 被哪些回测、研究、报告或交易动作使用？

### 数据质量标签

| 标签 | 含义 | 展示要求 |
|---|---|---|
| `ok` | 数据完整且新鲜 | 正常展示 |
| `stale` | 数据过期 | 黄色标记，禁止 live-ready |
| `partial` | 字段缺失但可降级使用 | 显示缺失字段 |
| `fallback` | 主源失败后使用备源 | 显示 fallback 轨迹 |
| `mock` | 模拟或测试数据 | 明确标记，不得用于实盘 |
| `invalid` | 数据不可信 | 阻断回测比较或交易执行 |

### 回测数据假设

每个回测必须记录：

- 数据来源和快照 ID。
- 复权方式。
- 是否包含退市/停牌/ST。
- 是否应用涨跌停不可成交。
- 是否应用 T+1。
- 成本模型和滑点。
- 是否样本外。
- 是否执行未来函数/look-ahead 检查。

### 刷新频率要求

| 数据域 | 生产口径刷新频率 | 说明 |
|---|---|---|
| 日 K | 每交易日收盘后 | 回测主数据 |
| 分钟 K | 盘中按需或定时 | 研究/交易辅助 |
| 估值 | 每交易日或 provider 更新后 | 允许延迟但必须标注 |
| 新闻/公告 | 按 provider 更新 | 必须保留发布时间 |
| 研报 | 按 provider 更新 | 必须保留机构和发布时间 |
| 订单/成交 | 交易动作后实时或轮询 | live-ready 前必须 reconciliation |

### 验收要求

- Phase 31 必须实现 DataQualityTag 和 BacktestDataAssumption 的文档/代码映射。
- Phase 32 必须让 BacktestResult 引用 data snapshot。
- Phase 33 必须让 ResearchAudit 引用 context snapshot。
- Phase 35 必须让订单和成交引用数据快照与审计事件。

---

## 部署指南

# A 股部署与运维文档

| 更新时间：2026-07-08 |

本文定义 TradingAgents-Astock 的环境、依赖、启动、健康检查、部署要求，以及产品指标与监控。本文只服务于研究、回测、模拟盘、受控执行和 WebUI 等核心功能。

### 环境分层

| 环境 | 用途 | 允许能力 | 禁止事项 |
|---|---|---|---|
| local | 本地开发、单元测试、文档验证 | research、paper、mock managed | 声明 live-ready |
| test | 集成测试、WebUI/API slice、provider fixture | research、paper、guarded live provider | 无说明直连真实交易 |
| staging | 受控演练、QMT 联调、回归验收 | research、paper、managed dry-run | 自动实盘 |
| production-like | 真实使用前演练环境 | research、paper、managed，live-ready 需单独准入 | 未通过 checklist 的真实交易 |

### 依赖清单

| 依赖 | 用途 | 生产级要求 |
|---|---|---|
| Python runtime | 后端、CLI、Agent runtime | 版本固定，可复现安装 |
| Flask WebUI | 产品页面和 API | 启动命令、端口、健康检查可记录 |
| PostgreSQL / ClickHouse | 生产级 OLTP + OLAP | Docker compose 部署，容器化 |
| DuckDB | 本地 OLAP 分析缓存 | 数据目录、备份、迁移边界明确 |
| akshare / mootdx / Tencent / EastMoney / Sina | A 股数据 provider | 记录来源、fallback、质量和授权边界 |
| LLM provider | AI Research | 记录模型、prompt、失败降级 |
| QMT | 受控执行 | 未通过准入前只允许 managed/dry-run 口径 |

### 环境变量与配置

后续开发不得把配置散落在代码中，至少需要记录：

- 数据库路径和缓存目录。
- provider 开关和 fallback 顺序。
- LLM provider、模型名称和超时配置。
- QMT 连接参数和 managed mode 开关。
- WebUI host、port、debug mode。
- 测试环境标记和 live dependency guard。

本文不要求记录密钥值、账号、隐私字段或密钥轮换策略；这些属于暂不纳入的安全与隐私文档。

### 启动顺序

标准启动流程应满足：

1. 检查 Python 环境和依赖版本。
2. 检查 DuckDB/cache 目录可读写。
3. 检查 provider 可用性，失败时标注 fallback 或 degraded。
4. 启动 Flask WebUI/API。
5. 需要时启动 Streamlit viewer。
6. 需要时启动 QMT managed/dry-run 联调。
7. 运行健康检查并记录结果。

### 健康检查

生产级健康检查至少覆盖：

- WebUI/API 是否可访问。
- DuckDB/store 是否可读。
- provider 是否可用、是否 fallback。
- LLM 是否可用，失败时是否 fail closed。
- QMT 是否 connected / disconnected / dry-run。
- 最近一次数据刷新时间。
- 最近一次任务失败原因。

### 核心数据恢复边界

当前项目应先定义以下备份恢复口径：

- DuckDB/cache 数据目录备份。
- 报告、回测结果、AI Research 结果归档。
- phase 文档和需求矩阵随 git 管理。
- 运行态任务和审计事件在 Phase 37 后统一进入 Ops/Audit。

本文不承诺恢复时间目标；恢复时间目标属于暂不纳入的 SLA 与故障分级。

### 验收要求

部署相关 phase 必须提供：

- 环境类型。
- 启动命令。
- 必需依赖。
- 健康检查结果。
- 已知 degraded 项。
- 回滚或恢复路径。
- 不涉及安全与隐私、SLA、用户角色/RBAC 的说明。

#### ### 验收证据（2026-06-26）

| 验收项 | 状态 | 证据 |
|--------|------|------|
| 环境分层定义 | ✅ 完成 | §1 明确定义 local/test/staging/production-like 四层及其允许/禁止能力 |
| 依赖清单完整 | ✅ 完成 | §2 列出 Python/Flask/Streamlit/DuckDB/provider/LLM/QMT 依赖及生产级要求 |
| 启动顺序文档化 | ✅ 完成 | §4 从环境检查→provider 可用性→Flask→Streamlit→QMT 共 7 步 |
| 健康检查覆盖范围 | ✅ 完成 | §5 覆盖 WebUI/DuckDB/provider/LLM/QMT/数据刷新/任务失败 7 项 |
| 数据恢复边界明确 | ✅ 完成 | §6 DuckDB/cache/报告/任务/审计的备份恢复口径已定义 |
| 环境变量配置纪要 | ✅ 完成 | §3 DB路径/cache/provider/LLM/QMT/WebUI/测试标记均需记录 |

---

### 产品指标与监控

> 合并自 `03-ops/ops-metrics.md`

#### 指标分层

| 指标层 | 目标 | 示例 |
|---|---|---|
| 产品价值指标 | 判断用户是否完成关键工作流 | 研究报告完成率、回测完成率 |
| 金融质量指标 | 判断数据和分析是否可信 | 数据新鲜度、provider 可用率 |
| 交易安全指标 | 判断交易路径是否安全 | 风控拦截率、人工确认率 |
| 系统运行指标 | 判断系统是否稳定 | API 错误率、任务失败率 |
| 审计完整性指标 | 判断关键动作是否可追溯 | 审计事件覆盖率、数据快照覆盖率 |

#### 告警需求

| 告警级别 | 场景 | 处理动作 |
|---|---|---|
| P0 | kill switch 触发、订单状态不一致、真实执行回报异常 | 阻断后续交易 |
| P1 | provider 主源不可用、数据严重延迟 | 降级或标红 |
| P2 | 单次 AI 生成失败、单次回测失败 | 页面提示并记录 |
| P3 | 非关键页面数据为空 | 记录日志，允许降级 |

#### 不做事项

- 不在文档阶段引入复杂监控系统选型
- 不要求立即接 Prometheus、Grafana 或外部告警平台
- 不把指标做成装饰性数字；没有采集来源的指标不得显示为真实值

---

## 在线研究

# A 股 live_research 环境配置

本文档说明 A 股 `live_research` runtime profile 的可运行环境。它的目标是让 Phase 09 A 股 advisory chain 使用真实 LLM client，而不是 deterministic verification 模式下的 `BridgeLLM`。

### 目标

启用真实 LLM 时必须同时保留以下安全约束：

- `actionable=false`
- `execution_signal=ResearchOnly`
- 缺少任一必要 live client 时 fail-closed，不能静默降级为 `BridgeLLM`

### 必需环境变量

至少需要在 `.env` 或当前 shell 中设置 provider、模型、runtime profile 和对应 API key：

```bash
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro
TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research
DEEPSEEK_API_KEY=your_real_key
```

可选配置：

```bash
TRADINGAGENTS_LLM_BACKEND_URL=https://api.deepseek.com
TRADINGAGENTS_OUTPUT_LANGUAGE=Chinese
TRADINGAGENTS_TEMPERATURE=0.0
```

### 推荐本地流程

## AStock API 安全配置

默认运行时，所有会改变状态的请求均要求 Bearer API key。写操作仅接受 `writer`、`operator` 或 `admin` 角色；展示型 `GET` 接口保持可访问，且不得返回通知凭据或 webhook 查询参数。

本机临时开发可显式设置 `ASTOCK_REQUIRE_AUTH=false`，但不得用于局域网或公网部署。测试环境通过 `ASTOCK_TESTING=1` 自动关闭该 gate。

通知渠道只允许公网 HTTP(S) 或 SMTP 目标，禁止私网/回环/保留地址，HTTP 请求不跟随重定向。渠道列表和创建/更新响应会移除密码、token、secret、API key 及 URL 查询参数；凭据只应通过受控写接口提交。

模拟盘展示以应用级 `PaperTrader` 为唯一状态源：`/trade/state`、`/paper/state`、`/paper/trades` 和首页概览读取同一份状态。状态变更（计划周期或手动订单）及快照读取必须受同一实例锁保护。计划周期按标的在线程池中处理，单标的处理默认 30 秒超时；超时必须发布 `cycle_error` 并继续处理其他标的。无可验证市场报价时，持仓按成本价估值并返回 `price_source=cost_basis`，不得伪造实时价格或浮盈亏。动量榜同时返回价格来源和龙头池来源，默认池/回退数据不得标记为实时行情。上述并发与异步 Store 调用回归由 2026-07-14 `tests/test_production_readiness_fixes.py` 验证（`13 passed in 3.28s`）。

1. 如有需要，复制环境变量模板：

```bash
cp .env.example .env
```

2. 填入上面的必需变量。

3. 在仓库内校验环境：

```bash
python3 scripts/check_astock_live_research_env.py
```

4. 通过 CLI 运行 A 股分析：

```bash
python3 -m cli.main run-analysis
```

当 ticker 是 A 股，并且 `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research` 时，CLI 会为以下角色构建真实 LLM client：

- Bull Researcher：quick-thinking 模型
- Bear Researcher：quick-thinking 模型
- Research Manager：deep-thinking 模型

Streamlit 只读 viewer 在 live runtime mode 下使用同一套配置路径。

### 校验行为

- `deterministic_verification` profile 允许缺少真实 LLM client，并使用 `BridgeLLM`。
- `live_research` profile 如果缺少 provider 配置或 API key，必须在分析开始前失败。
- `live_research` 运行不得回退到 `BridgeLLM`。

### 数据源说明

#### ### mootdx（通达信）

mootdx 0.11.7 已在本地验证通过，可连接通达信行情服务器获取实时 K 线和报价。无需额外配置。支持的 symbol 格式为不带后缀的数字代码，例如 `600519`；`AStockDataRouter` 会自动转换。

#### ### iwencai（问财）

pywencai 0.13.1 已安装，但需要设置 `ASTOCK_IWENCAI_COOKIE` 环境变量才能启用。

获取 iwencai cookie：

1. 用浏览器打开 https://iwencai.com 并登录账号。
2. 打开浏览器开发者工具，进入 Application / Storage。
3. 在 Cookies -> iwencai.com 下找到名为 `v` 或 `other_` 开头的 cookie 值。
4. 复制完整 cookie 字符串。
5. 设置环境变量：

```bash
export ASTOCK_IWENCAI_COOKIE="your_cookie_value_here"
```

也可以写入 `.env`：

```bash
ASTOCK_IWENCAI_COOKIE=your_cookie_value_here
```

配置后可启用语义搜索和机构预期查询能力。

### 当前主机状态

当前仓库已经把 `live_research` 路径接入 config、CLI 和 Streamlit。真实运行仍要求当前 shell 或 app 进程环境中存在匹配 provider 的有效 key。

live provider 的历史验证证据由 `tradingagents/astock/verification_provenance.py` 管理。这些记录是 provider 可用性溯源，不等同于当前网络环境仍可用；重新验证需要运行 live provider 测试并追加新的 dated provenance。

#### ### 2026-07-08 实测结果

- 使用显式环境变量 `TRADINGAGENTS_LLM_PROVIDER=deepseek`、`TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash`、`TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro`、`TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research`、`DEEPSEEK_API_KEY=<real key>` 后，`python3 scripts/check_astock_live_research_env.py` 校验通过
- `pytest -q tests/test_deepseek_reasoning.py -k live -m integration -vv` → `1 passed`
- `pytest -q tests/test_astock_live_providers.py -m integration -vv` → `7 passed, 1 skipped`
- `python3 scripts/verify_astock_live_pipeline.py` → `VERIFICATION PASSED`

#### ### 当前已知约束

- 默认仓库配置仍是 `llm_provider=openai`；若只设置 `DEEPSEEK_API_KEY` 而未切换 provider/model，`live_research` 会按设计 fail-closed
- Iwencai live 用例仍依赖 `ASTOCK_IWENCAI_COOKIE`；未配置时会跳过，不应记为失败
- Tencent live 路径在首次验收中出现过一次 `600519.SH` 瞬时失败，但单点复跑与全量复跑均已通过；当前更像上游波动而非稳定代码缺陷

---

## 实盘交易

# A 股实盘运行手册

| 更新时间：2026-07-08 |

本文定义 TradingAgents-Astock 从研究/模拟/受控执行进入实盘辅助运行时的操作手册。当前系统尚不等同于完整自动实盘生产系统；任何真实执行必须先通过 Phase 30 Live Trading Readiness。

### 运行模式

| 模式 | 含义 | 允许动作 |
|---|---|---|
| `research` | 只读研究和报告 | AI 分析、数据查询、报告生成 |
| `paper` | 模拟盘 | 虚拟订单、虚拟成交、模拟持仓 |
| `managed` | 受控执行口径 | 当前仅 mock/read-only；风控门 + 人工确认 + QMT 真实桥接属于 P3 准入后事项 |
| `live-ready` | 满足准入清单后的实盘准备状态 | 仅在 checklist 全部通过后允许标记 |

默认模式不得高于 `paper`；`managed` 当前仅作为 mock/read-only 边界展示，不代表已接真实券商。

当前仓库口径（2026-06-26）：

- `research`：只读研究。
- `paper`：当前 `/api/v1/trade/order`、`/api/v1/trade/state`、`/api/v1/paper/*` 的真实落点。
- `managed`：当前仅有 QMT mock/read-only 与受控执行设计，不等于已打通真实下单。
- `live-ready`：当前仍是准入目标，不是可默认切换到的可运行模式。

### 启动前检查

#### 环境检查

- `.env` 已配置必要 provider key。
- `TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE` 明确设置。
- live research 不允许回退到 `BridgeLLM`。
- WebUI 运行端口明确，避免 macOS AirPlay 占用 5000。
- DuckDB/store 可读写。

#### 数据检查

- provider 健康可见。
- 数据新鲜度可见。
- 关键数据源不可用时有 fallback 或降级策略。
- 回测/交易使用的数据快照可追溯。

#### 交易检查

- 当前模式明确显示。
- kill switch 状态可见。
- 风控门状态可见。
- paper/managed/live-ready 视觉和文案区分；当前 managed 必须显示 mock/read-only。
- QMT API/UI 不发起真实连接检查；不得把 mock 状态伪装成真实券商连接成功。
- 若页面允许切换 `live`/`managed` 文案，必须同时说明后端是否真正落到该执行链路。

### 实盘准入 checklist

进入 `live-ready` 前必须满足：

- 账户资金、持仓、可用资金、冻结资金状态可读取。
- 委托、成交、撤单、拒单、部分成交状态可读取。
- 本地订单与券商回报 reconciliation 可检测。
- kill switch 可启停并写审计。
- 最大单笔金额、最大持仓、最大日亏损、交易时段约束可执行。
- 所有交易动作有人工确认记录。
- 所有交易动作有 Audit Event。
- 数据快照和行情时间可追溯。
- 故障恢复和回滚流程已验证。

不满足任一项时，不得标记 `live-ready`。

### 1 Phase 30 结论

当前 Phase 30 的完成含义是：

- 已把 `research` / `paper` / `managed` / `live-ready` 的能力边界写清楚。
- 已确认当前 `trade/order` 和 `trade/state` 仍属 `paper`。
- 已确认 QMT 端点当前只能按 `managed` 的 mock/read-only 口径对外描述。
- 已确认真实 QMT 订单/委托查询为已知问题，当前暂不接入。

当前 Phase 30 不代表：

- 交易 API 已全部升级到标准 envelope。
- `/trade/order` 已支持真实 managed 或 live-ready 下单。
- QMT 真实账户、委托查询、成交、回报对账已经闭环（当前未闭环，暂不接入）。

### 日常运行流程

1. 检查 Data & Ops：provider、DuckDB、缓存、任务状态。
2. 检查系统模式：确认仍为预期的 research/paper/managed。
3. 运行 AI Research 或 Strategy Lab。
4. 如需交易，先进入 paper 或 managed。
5. 执行前检查 Risk Gate、kill switch、数据快照和人工确认。
6. 执行后检查订单状态、成交状态和 reconciliation。
7. 记录异常、失败和审计事件。

### 异常处理

| 异常 | 处理 |
|---|---|
| provider 主源失败 | fallback；若无可用备源，标记数据不可用 |
| 数据严重延迟 | 禁止 live-ready，允许 research 降级展示 |
| LLM 失败 | research 失败或降级，不产生交易动作 |
| Risk Gate 拦截 | 阻断订单，记录 reason code |
| kill switch 触发 | 阻断后续交易动作 |
| QMT 不可用 | 降级 paper 或阻断 managed |
| 订单状态不一致 | 停止后续交易，进入 reconciliation |
| DuckDB/store 不可用 | 阻断需要持久化的任务 |

### 回滚策略

- WebUI 页面异常：回退到上一个稳定模板或禁用入口。
- API schema 异常：保留兼容字段，不删除旧字段。
- 数据刷新异常：保留旧数据快照，标记 stale。
- 回测异常：标记结果 invalid，不进入策略对比。
- 交易异常：启用 kill switch，停止后续执行。

### 运行记录

每次 managed/live-ready 运行必须记录：

- 运行日期和模式。
- provider 状态。
- 数据快照。
- AI/策略输入。
- 风控结果。
- 人工确认。
- 订单/成交状态。
- 异常和处理结果。

### 验收要求

- Phase 30 必须把本 runbook 转成可执行 checklist。
- Phase 35 必须验证订单生命周期和 reconciliation。
- Phase 37 必须把运行记录接入 Ops & Audit。

---

## 风险台账

# A 股项目风险登记表

| 更新时间：2026-07-08（Phase 34-39 风险状态已更新 ✅） |

本文用于从项目经理视角持续跟踪 TradingAgents-Astock 核心功能开发风险。本文只覆盖当前纳入范围内的金融软件核心功能风险，不展开安全与隐私、SLA 与故障分级、用户角色/RBAC。

### 风险等级

| 字段 | 取值 | 说明 |
|---|---|---|
| 影响 | `H` / `M` / `L` | 对交易安全、数据可信、交付计划或用户误导的影响 |
| 概率 | `H` / `M` / `L` | 在后续 Phase 30-39 中发生的可能性 |
| 状态 | `open` / `mitigating` / `accepted` / `closed` | 当前处理状态 |

### 风险台账

| ID | 风险 | 类型 | 影响 | 概率 | 缓解措施 | 关联文档 | 状态 |
|---|---|---|---|---|---|---|---|
| R-001 | paper / managed / live-ready 能力边界被用户误解 | 交易 | H | M | 所有交易相关 API 和页面必须标注能力等级，live-ready 前必须通过 checklist | `01-architecture.md`, `03-operations.md`, `03-operations.md` | mitigating（Phase 30 已补能力定义 + Phase 35 done-with-exclusions） |
| R-002 | QMT 订单、成交、撤单、拒单和券商回报 reconciliation 未闭环 | 交易 | H | M | Phase 30/35 先补订单生命周期、reconciliation、风控前置门和审计引用；真实券商 reconciliation 明确 P3 暂不处理 | `BACKLOG.md`, `04-development.md`, `docs/phase-archive.md` | accepted（P3 暂不处理，产品定位非实盘） |
| R-003 | 回测结果存在 look-ahead、survivorship、停牌/涨跌停成交假设不清 | 回测 | H | M | Phase 31 已补数据假设、反偏差状态和回测可比性标记，后续持续维护 | `03-operations.md`, `04-development.md` | mitigating（Phase 31 已完成，需持续维护） |
| R-004 | 数据源 freshness、fallback、quality 不透明导致 AI/回测/交易误判 | 数据 | H | M | Phase 31 已补 data quality tag、freshness/quality/fallback 标记 | `03-operations.md` | mitigating（Phase 31 已完成，需持续维护） |
| R-005 | AI 输出缺少模型、prompt、输入快照和引用，无法复查 | AI | M | M | Phase 33 已统一 ResearchTask / ResearchAudit，AI 输出默认 advisory-only | `03-operations.md` | mitigating（Phase 33 已完成，需持续维护） |
| R-006 | Strategy Lab 整合时策略 registry、API、WebUI、优化器注册点漂移 | 策略 | M | H | Phase 32 已完成 Strategy Lab 统一入口 + BacktestResult schema + optimizer；强制遵守策略开发规范 | `02-user-guide.md`, `04-development.md` | closed（Phase 32 完成整合） |
| R-007 | WebUI 页面多入口、多语义导致用户心智混乱 | UI | M | H | Phase 38 已完成 7 模块顶层导航收敛 + 旧入口 redirect + deprecation banner | `02-user-guide.md` | closed（Phase 38 完成导航收敛） |
| R-008 | DuckDB/cache/schema 变化破坏历史回测、报告或页面兼容 | 数据迁移 | M | M | schema 变化必须补迁移、校验、cache 重建和回滚说明 | `04-development.md`, `BACKLOG.md` | open（数据库模块 v1.0 已内置迁移引擎） |
| R-009 | Phase 文档与真实代码状态漂移，导致后续开发依据不可靠 | 项目管理 | M | M | 已完成多次文档批量同步，当前状态已对齐；后续 phase 变更后需同步维护 | `../README.md`, `04-development.md` | closed（文档已对齐，后续维护模式下持续） |
| R-010 | 原 TradingAgents core 被误改，破坏底层 AI 分析能力 | 架构 | H | L | 保留原 core，新增 A 股能力只改后来新增模块，必要兼容修复需 ADR 记录 | `01-architecture.md` | open |

### 风险更新规则

- 每个 Phase 开始前必须检查本表是否有相关 open 风险。
- 每个 Phase 完成后必须更新风险状态，不能只在 phase 文档中分散描述。
- 新增高影响风险必须分配 `R-*` 编号，并关联需求 ID 或 phase。
- 风险状态变为 `closed` 时必须有测试、文档或实现证据。
- 如果风险属于安全与隐私、SLA 与故障分级、用户角色/RBAC，只登记为范围外触发条件，不进入当前核心功能开发。

### Phase 30-39 重点风险映射

| Phase | 重点风险 |
|---|---|
| Phase 30 Live Trading Readiness | R-001, R-002 |
| Phase 31 Data Quality & Bias Control | R-003, R-004, R-008 |
| Phase 32 Strategy Lab | R-006, R-008 |
| Phase 33 AI Research Center | R-005, R-010 |
| Phase 34 Market Leaders | R-004, R-007 |
| Phase 35 Trading & Execution | R-001, R-002, R-008 |
| Phase 36 Portfolio Risk & Attribution | R-003, R-004 |
| Phase 37 Ops & Audit | R-005, R-009 |
| Phase 38 Product Navigation Cleanup | R-007, R-009 |
| Phase 39 End-to-End UAT | R-009 |

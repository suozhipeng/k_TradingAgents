# TradingAgents `xg_dev` 开箱即用闭环修复与 Hermes 低 Token 自动化完整实施方案

**版本：V1.5 完整基础功能实施版**  
**目标分支：`xg_dev`**  
**建议集成分支：`fix/xg-dev-data-loop-v033`**  
**目标发布版本：`0.3.3`**  
**适用环境：macOS、本地单机 Hermes、Git Worktree、DuckDB**  
**更新时间：2026-07-23**  
**版本原则：完整保留 V1.2～V1.6 有效内容，只做增量补强，不删除既有实施细节**

---

## 0. 文档定位

> **实施状态：已全部实现**
> 
> 实施分支：`fix/xg-dev-data-loop-v033`  
> 工作树：`.worktrees/xg-integration`  
> 提交：`2ecb1d6` (HEAD)  
> 测试：242 项全部通过  
> 验收：5 步离线验证全部 PASS  
> 验收证据：`.hermes-workflow/evidence/final/acceptance.json`

本方案将以下三部分合并为一套完整、可执行、可验证的工程流程：

1. `TradingAgents xg_dev` 数据与 Web 修复实施方案；
2. Hermes 通过 Cron 调用 Kanban 自动推进开发与验证；
3. Agnes、DeepSeek、Codex 的低 Token 分工与配置。

最终形成：

```text
修复方案
  ↓
Hermes Cron 确定性控制器
  ↓
Kanban 持久任务状态机
  ↓
DeepSeek / Agnes / Codex 分工执行
  ↓
脚本化测试与机器证据
  ↓
独立验收
  ↓
0.3.3 READY-FOR-RELEASE
```

### 0.1 V1.2 相比 V1.1 的主要调整

- 合并修复方案、模型配置和 Cron/Kanban 实施步骤；
- 将模型 ID 改为“运行时探测”，避免写死账户中不存在的模型；
- DeepSeek 默认使用 `deepseek-v4-flash`，并要求通过 `/models` 再确认；
- Codex 优先通过 `hermes model` 配置 OpenAI Codex OAuth；使用 API Key 时以账户实际 `/v1/models` 返回值为准；
- Agnes 统一按 OpenAI-compatible Named Custom Provider 接入；
- 关闭 Kanban 自动分解，避免既定 PR-1～PR-6（含 PR-5A、PR-5B） 被重新拆解；
- Cron 改为 `--no-agent` 脚本模式，正常轮询不消耗模型 Token；
- 统一为一个 Hermes Gateway 承载当前项目 Dispatcher；
- 增加 Prompt Size 基线、Token 预算、Diff-only Review 和日志压缩；
- 增加 Controller、Evidence、Worktree、熔断和恢复协议；
- 将“模型判断”与“机器验收”分离，模型不能自行宣告发布成功。

### 0.2 V1.4 相比 V1.2 的增量升级

V1.4 不删减 V1.2 的模型配置、Profile、SOUL、Cron、Kanban、Controller、Evidence、Worktree、回滚和监控内容，只增量加入：

- 新增 `scripts/setup_local.sh`，实现一键创建虚拟环境、安装依赖和运行 Doctor；
- 新增 `scripts/start_local.sh`，实现一键启动、健康检查和自动打开浏览器；
- 将核心标准化和质量门禁前移到 PR-4，确保数据先清洗、后入库；
- 为 Bootstrap 增加单标的事务、失败回滚、Upsert、唯一键和任务幂等；
- 新增 `PR-5B Canonical Backtest`，明确回测只读取唯一 DuckDB，不直接调用 Provider；
- 增加回测结果持久化和重启后读取验收；
- 更新 Kanban 依赖、Evidence、Controller、测试脚本和最终发布门禁，使其覆盖 PR-5B；
- 将最终产品门禁升级为“安装 → Provider → 拉取 → 清洗 → 入库 → Web → 回测 → 重启持久化”。


### 0.3 V1.5 相比 V1.4 的增量升级

V1.5 将以下能力从“架构预留”提升为 `0.3.3` 发布必需的基础功能：

- 新增 `PR-5A 市场复盘与个股综合分析`，位于 Dashboard/K 线与回测之间；
- 新增市场指数、市场宽度、涨跌停、连板梯队、板块强度、市场情绪状态机；
- 新增技术面、基本面、估值面、资金面、消息面、板块联动和风险分析；
- 将“确定性事实计算”和“LLM 自然语言解释”严格分层；
- LLM 不可用时，结构化指标、风险规则和证据仍必须正常展示；
- 新增市场复盘及分析报告持久化，服务重启后仍可查询；
- 新增复盘 → 板块 → 个股分析 → 策略回测的 Web 串联路径；
- 补充 A 股基础回测规则、无未来函数规则、基准和可复现元数据；
- 将 Kanban、Controller、Evidence、测试和 Final Acceptance 从七阶段升级为八阶段；
- 最终产品门禁升级为“安装 → 数据闭环 → 市场复盘 → 个股分析 → 回测 → 重启持久化”。

---

# 第一部分：项目修复目标与架构

## 1. 当前问题判断

`xg_dev` 不是整体技术方向错误，而是开发顺序和验收标准失焦：

1. Web、API、调度、交易、通知等模块扩张过快；
2. 本地首次运行的数据初始化闭环没有完成；
3. `local-release` 依赖与真实 Provider 运行要求不一致；
4. Provider 初始化失败后应用仍可启动，导致“页面可打开但没有数据”；
5. 存在多个 DuckDB 路径，Dashboard、K 线和回测可能读取不同数据源；
6. 部分接口返回空数据，部分接口返回 mock，数据可信语义不一致；
7. Web 没有完整 Data Hub，用户不知道如何初始化和修复数据；
8. 数据质量治理主要集中在 K 线和估值，其他数据类型清洗不完整；
9. 测试数量不能替代“全新环境、空数据库、真实 Provider、浏览器闭环”验收。

## 2. 唯一主目标

在全新环境和空数据库条件下，用户执行一次安装并启动 Web 后，能够仅通过浏览器完成：

```text
环境检测
→ Provider 检测
→ 初始化指数和示例股票
→ 数据标准化
→ 数据质量检查
→ 写入唯一 DuckDB
→ Dashboard 显示真实数据
→ 查看 K 线
→ 生成市场复盘
→ 查看个股综合分析
→ 执行策略回测
→ 重启后继续读取复盘、分析和回测结果
```

在该闭环完成前，不继续开发外围功能。

### 2.1 开箱即用入口

全新环境的标准入口必须收敛为：

```bash
git clone <repository-url>
cd k_TradingAgents
git switch fix/xg-dev-data-loop-v033

./scripts/setup_local.sh
./scripts/start_local.sh
```

浏览器启动后：

```text
首次设置页
→ Provider 检测
→ 快速初始化
→ Dashboard
→ K 线
→ 市场复盘
→ 个股综合分析
→ 示例回测
```

用户不应被要求手工拼接多套安装命令、数据库路径或 Provider 初始化命令。

## 3. 最终验收标准

必须同时满足：

1. `pip install -e ".[local-release]"` 后基础 Provider 可导入；
2. 空库时 Dashboard 明确显示 `not_initialized`，而不是模糊“暂无数据”；
3. Web 提供 Data Hub 和快速初始化按钮；
4. 默认初始化至少包含 5 个主要指数和 3 个示例股票；
5. 每个成功标的至少写入 250 条日 K；
6. Dashboard 显示数据来源、质量状态和更新时间；
7. 系统重启后行情、复盘、分析和回测结果仍然存在；
8. 默认禁止隐式 mock；
9. API 能区分 `live/cache/fallback/stale/mock/unavailable`；
10. Dashboard、K 线、市场复盘、个股分析和回测使用同一个 Canonical DuckDB；
11. 市场复盘能够生成指数表现、市场宽度、情绪、板块和强弱标的；
12. 个股分析至少覆盖技术、基本面、估值、资金、消息、板块联动和风险；
13. LLM 不可用时，确定性指标和结构化分析仍可正常使用；
14. 每条模型解释必须关联事实 ID、数据截止时间和来源；
15. 至少一个策略使用真实本地 K 线完成回测；
16. 回测处理 A 股 T+1、100 股交易单位、费用、滑点、停牌和涨跌停约束；
17. 回测无未来函数，并记录策略版本、代码 SHA、参数和数据快照；
18. `setup_local.sh` 与 `start_local.sh` 在全新环境可执行；
19. 首次真实数据必须先标准化和核心质量检查，再进入 DuckDB；
20. Bootstrap 按单标的事务写入，重复执行不产生重复主键；
21. 回测只读取 Canonical DuckDB，不直接调用 Provider；
22. 复盘、分析和回测结果持久化，重启后仍可查询；
23. 复盘 → 板块 → 个股分析 → 回测的浏览器路径全部通过；
24. Unit、Integration、Browser、Live Provider 验收全部通过；
25. Codex 独立验收返回 `PASS`；
26. Controller 校验机器证据后才允许标记发布完成。

## 4. 修复期间冻结范围

暂停开发：

```text
QMT
模拟盘
自动交易
PostgreSQL
TimescaleDB
ClickHouse
SSE
Scheduler
Notifications
Alerts
多用户
RBAC
多 Worker Web 部署
新 Provider
新 Agent
无关页面
```

允许修改：

```text
pyproject.toml
scripts/
docs/
tests/
tradingagents/astock/api/
tradingagents/astock/data_sources/
tradingagents/astock/store/
tradingagents/astock/quality/
tradingagents/astock/web/
tradingagents/astock/backtest/
.github/workflows/
```

## 5. 数据库决策

### 5.1 当前版本只使用 DuckDB

Canonical 数据库：

```text
~/.tradingagents/astock/astock.duckdb
```

保存：

```text
security_master
trading_calendar
kline_bars
realtime_quotes
valuations
financial_indicators
capital_flows
news
announcements
research_reports
strategy_results
market_review_runs
market_review_snapshots
market_index_daily
market_breadth_daily
market_sentiment_daily
sector_performance_daily
limit_up_daily
limit_down_daily
limit_up_ladders
market_leaders_daily
stock_analysis_runs
stock_analysis_facts
stock_analysis_reports
stock_risk_signals
technical_indicator_snapshots
backtest_runs
backtest_trades
data_quality_results
data_quarantine
ingestion_runs
ingestion_run_items
```

### 5.2 当前不引入 SQLite 业务库

Hermes Kanban 自己使用 SQLite 保存任务状态，这是 Hermes 内部工作流数据，不是 TradingAgents 业务数据，不构成双库业务架构。

```text
~/.hermes/kanban/boards/tradingagents-xgdev/kanban.db
    └── Hermes 任务、依赖、事件、评论

~/.tradingagents/astock/astock.duckdb
    └── TradingAgents 行情、估值、研究、回测
```

禁止：

```text
第二个 K 线 DuckDB
SQLite 与 DuckDB 双写业务数据
local-release 自动切换 PostgreSQL
Provider 失败后默认生成假行情
```

## 6. 目标架构

```text
浏览器
  │
  ▼
Flask + Jinja2
  ├── Setup API
  ├── Dashboard API
  ├── Market Data API
  ├── Market Review API
  ├── Stock Analysis API
  ├── Research API
  └── Backtest API
          │
          ▼
AStockDataFacade
          │
          ▼
Provider Router
  ├── Mootdx
  ├── AkShare
  ├── Tencent
  └── BaoStock
          │
          ▼
字段标准化
          │
          ▼
核心标准化与质量门禁
  ├── 合法数据 → 单标的事务 Upsert → Canonical DuckDB
  └── 异常数据 → data_quarantine
          │
          ▼
~/.tradingagents/astock/astock.duckdb
  ├── Dashboard / Kline / Screening
  ├── Market Review → market_review_* / market_sentiment_daily
  ├── Stock Analysis → stock_analysis_* / stock_risk_signals
  └── Canonical Backtest → backtest_runs / backtest_trades
```

---

# 第二部分：模型分工与 Token 策略

## 7. 模型分工决策

| 模型 | 主要职责 | 不承担的职责 |
|---|---|---|
| DeepSeek | Orchestrator、任务整理、上下文压缩、小补丁、文档、前端小改动、失败归类 | 数据库核心迁移、最终验收 |
| Agnes | 跨文件主实现、Python/Flask/DuckDB、Provider、Data Hub、普通 Review | 自己给自己最终 PASS、改变任务范围 |
| Codex | 高风险 Gate、架构方向、数据库/API Review、最终 Acceptance | 日常扫描、普通文档、小补丁、Cron 轮询 |
| 无模型脚本 | Cron、状态检查、测试、Git SHA、数据库行数、日志摘要、Evidence 校验 | 代码设计和模糊判断 |

推荐调用次数占比：

```text
DeepSeek：55%～70%
Agnes：25%～35%
Codex：5%～10%
```

## 8. 模型 ID 规则

### 8.1 DeepSeek

当前优先：

```text
deepseek-v4-flash
```

执行探测：

```bash
curl -sS https://api.deepseek.com/models \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Accept: application/json"
```

确认实际返回后再写入 Hermes。

默认使用非思考模式；仅在第二次小补丁失败或字段映射存在歧义时，临时提高推理强度。

### 8.2 Agnes

不猜模型名，执行：

```bash
curl -sS "${AGNES_BASE_URL%/}/models" \
  -H "Authorization: Bearer $AGNES_API_KEY" \
  -H "Accept: application/json"
```

记录：

```bash
export AGNES_MODEL_ID="<接口实际返回的模型ID>"
```

### 8.3 Codex

优先方式：

```bash
hermes -p xg-gate-codex model
hermes -p xg-accept-codex model
```

选择 Hermes 内置的 **OpenAI Codex**，完成 OAuth 或当前可用认证。

使用 OpenAI API Key 时执行：

```bash
curl -sS https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Accept: application/json"
```

只使用账户实际返回且 Hermes 支持的 Codex 模型，不在文档中强制写死某个模型 ID。

## 9. 推理强度策略

| Profile | 默认推理 | 临时提升条件 |
|---|---|---|
| DeepSeek Orchestrator | `none` | 不提升 |
| DeepSeek Patch | `none` | 第二次定位困难时 `low` |
| Agnes Implement | Provider 默认或 `low` | 数据库/并发复杂实现可 `medium` |
| Agnes Review | `low` | 普通 Review 不提升 |
| Codex Gate | `low` | PR-2/3/4/6 可 `medium` |
| Codex Acceptance | `medium` | PR-2/4/6/Final 可 `high` |

禁止把所有 Profile 默认设置为 `high` 或 `xhigh`。

## 10. Token 控制基线

建议配置：

| Profile | `max_turns` | `context_file_max_chars` | `file_read_max_chars` | `tool_output.max_bytes` |
|---|---:|---:|---:|---:|
| Orchestrator DeepSeek | 18 | 12,000 | 60,000 | 30,000 |
| Patch DeepSeek | 36 | 12,000 | 70,000 | 35,000 |
| Implement Agnes | 65 | 15,000 | 90,000 | 40,000 |
| Review Agnes | 28 | 10,000 | 60,000 | 30,000 |
| Gate Codex | 18 | 10,000 | 50,000 | 25,000 |
| Acceptance Codex | 24 | 12,000 | 70,000 | 35,000 |

这些不是模型 API 强制额度，而是工作流预算。

## 11. 必须执行的 Token 节省措施

1. Cron 使用 `--no-agent`；
2. `kanban.auto_decompose=false`；
3. 关闭自动标题模型；
4. 不使用嵌套 delegate swarm；
5. 同一时间只允许一个实现任务运行；
6. Review 只读取任务合同、Diff、测试摘要和 Evidence；
7. 成功日志只保存统计；
8. 失败日志只保留关键错误和最后 120 行；
9. Task Body 不复制完整修复方案；
10. `.hermes.md` 控制在约 12,000 字符以内；
11. 单任务生产文件优先不超过 5 个，硬上限 8 个；
12. Codex 不参与 Cron 状态轮询；
13. Agnes Review 不修代码；
14. Codex Acceptance 不修代码；
15. 第二次相同失败立即阻塞；
16. 禁止自动跨角色模型 fallback；
17. 使用 `hermes prompt-size --json` 建立固定提示词基线；
18. 关闭无关 Skills 和 Toolsets，降低每轮固定 Prompt 成本。

---

# 第三部分：Hermes 初始化与 Profile 配置

## 12. 定义本地路径

在终端执行并替换实际目录：

```bash
export XG_REPO="/Users/<你的用户名>/Projects/k_TradingAgents"
export XG_BOARD="tradingagents-xgdev"
export XG_INTEGRATION_BRANCH="fix/xg-dev-data-loop-v033"
export XG_PLAN="$XG_REPO/docs/TradingAgents_xg_dev_修复与Hermes低Token自动化实施方案_V1.6.1.md"
```

确认：

```bash
test -d "$XG_REPO/.git" || { echo "XG_REPO 不是 Git 仓库"; exit 1; }
cd "$XG_REPO"
git status --short
```

## 13. 备份 Hermes 和仓库状态

```bash
HERMES_BACKUP="$HOME/hermes-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$HERMES_BACKUP"

cp -R "$HOME/.hermes" "$HERMES_BACKUP/.hermes" 2>/dev/null || true
cp -R "$HOME/.codex" "$HERMES_BACKUP/.codex" 2>/dev/null || true

cd "$XG_REPO"
git status --short > "$HERMES_BACKUP/repo-status.txt"
git rev-parse HEAD > "$HERMES_BACKUP/repo-head.txt"

echo "Backup: $HERMES_BACKUP"
```

更新并检查 Hermes：

```bash
hermes update --check
hermes config migrate
hermes config check
hermes doctor
hermes dump
```

不要在仓库有未提交关键修改时直接执行可能改变 Hermes 源码安装的操作。

## 14. 创建六个 Profile

```bash
hermes profile create xg-orchestrator-ds --clone \
  --description "TradingAgents xg_dev 修复总控。只管理 Kanban、依赖、证据和阶段推进，不修改生产代码。"

hermes profile create xg-patch-ds --clone \
  --description "使用 DeepSeek 完成低风险小补丁、测试、文档和前端模板，严格受文件白名单约束。"

hermes profile create xg-implement-agnes --clone \
  --description "使用 Agnes 完成跨文件 Python、Flask、DuckDB、Provider、Web 和 CI 实现。"

hermes profile create xg-review-agnes --clone \
  --description "使用 Agnes 只读审查普通实现、测试覆盖和页面行为，不修改生产代码。"

hermes profile create xg-gate-codex --clone \
  --description "使用 Codex 检查高风险任务方向、范围、数据库边界和 API 契约，不实现代码。"

hermes profile create xg-accept-codex --clone \
  --description "使用 Codex 根据 Diff、测试和机器证据执行独立验收，只输出 PASS 或 FAIL。"
```

检查：

```bash
hermes profile list
hermes profile show xg-orchestrator-ds
hermes profile show xg-implement-agnes
```

本文后续统一使用：

```text
hermes -p <profile> <command>
```

即使 Shell Alias 未刷新，也能稳定执行。

## 15. 配置 DeepSeek Profiles

编辑：

```text
~/.hermes/profiles/xg-orchestrator-ds/.env
~/.hermes/profiles/xg-patch-ds/.env
```

写入：

```dotenv
DEEPSEEK_API_KEY=<你的Key>
```

推荐先使用交互式模型配置：

```bash
hermes -p xg-orchestrator-ds model
hermes -p xg-patch-ds model
```

选择 DeepSeek，并使用 `/models` 返回的 `deepseek-v4-flash`。

若手工配置，核心结构：

```yaml
model:
  provider: deepseek
  default: deepseek-v4-flash
```

## 16. 配置 Agnes Named Custom Provider

分别编辑：

```text
~/.hermes/profiles/xg-implement-agnes/.env
~/.hermes/profiles/xg-review-agnes/.env
```

写入：

```dotenv
AGNES_API_KEY=<你的AgnesKey>
```

在两个 Profile 的 `config.yaml` 中加入：

```yaml
custom_providers:
  - name: agnes
    base_url: "<AGNES_BASE_URL，通常以 /v1 结束>"
    key_env: AGNES_API_KEY
    api_mode: chat_completions

model:
  provider: custom:agnes
  default: "<AGNES_MODEL_ID>"
```

更稳妥的方法：

```bash
hermes -p xg-implement-agnes model
hermes -p xg-review-agnes model
```

选择：

```text
Custom endpoint
```

依次输入 Agnes Base URL、API Key 和真实模型 ID，让 Hermes 自动写入当前版本支持的配置结构。

## 17. 配置 Codex Profiles

推荐执行：

```bash
hermes -p xg-gate-codex model
hermes -p xg-accept-codex model
```

选择：

```text
OpenAI Codex
```

完成 OAuth 后，不手动覆盖 Hermes 写入的：

```text
provider
base_url
api_mode
auth state
```

若使用 OpenAI API Key，则将 Key 放入两个 Profile 的 `.env`：

```dotenv
OPENAI_API_KEY=<你的OpenAIKey>
```

并以 `/v1/models` 实际可用模型为准。

## 18. 通用低 Token 配置

以下配置合并到每个 Profile 的 `config.yaml`，具体值按前表调整：

```yaml
agent:
  max_turns: 36
  api_max_retries: 1
  reasoning_effort: none

compression:
  enabled: true
  threshold: 0.45
  target_ratio: 0.20
  protect_last_n: 14
  protect_first_n: 2
  hygiene_hard_message_limit: 1200

context:
  engine: compressor

context_file_max_chars: 12000
file_read_max_chars: 70000

tool_output:
  max_bytes: 35000
  max_lines: 1200
  max_line_length: 1200

auxiliary:
  title_generation:
    enabled: false

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 1500
  user_char_limit: 800
  write_approval: true

tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
  warn_after:
    exact_failure: 2
    same_tool_failure: 3
    idempotent_no_progress: 2
  hard_stop_after:
    exact_failure: 3
    same_tool_failure: 5
    idempotent_no_progress: 3

terminal:
  backend: local
  cwd: "/Users/<你的用户名>/Projects/k_TradingAgents"
```

配置后必须执行：

```bash
for p in \
  xg-orchestrator-ds \
  xg-patch-ds \
  xg-implement-agnes \
  xg-review-agnes \
  xg-gate-codex \
  xg-accept-codex
do
  hermes -p "$p" config check || exit 1
  hermes -p "$p" doctor || exit 1
done
```

如果当前 Hermes 版本拒绝某个键：

1. 不强行启动；
2. 执行 `hermes -p <profile> config migrate`；
3. 执行 `hermes -p <profile> config show`；
4. 查当前版本帮助或 Dashboard 配置界面；
5. 删除不受支持的键后重新 `config check`。

## 19. Orchestrator 专用配置

`xg-orchestrator-ds/config.yaml` 增加：

```yaml
agent:
  max_turns: 18
  api_max_retries: 1
  reasoning_effort: none

kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
  auto_decompose: false
  auto_decompose_per_tick: 1
  orchestrator_profile: xg-orchestrator-ds
  default_assignee: xg-orchestrator-ds
  failure_limit: 2
  dispatch_stale_timeout_seconds: 14400

dashboard:
  kanban:
    default_tenant: tradingagents-xgdev
    lane_by_profile: true
    include_archived_by_default: false
    render_markdown: true

cron:
  script_timeout_seconds: 300
  wrap_response: false

auxiliary:
  title_generation:
    enabled: false
  compression:
    provider: deepseek
    model: deepseek-v4-flash
    reasoning_effort: none
    timeout: 120
  triage_specifier:
    provider: deepseek
    model: deepseek-v4-flash
    reasoning_effort: none
    timeout: 60
  kanban_decomposer:
    provider: deepseek
    model: deepseek-v4-flash
    reasoning_effort: none
    timeout: 60
  profile_describer:
    provider: deepseek
    model: deepseek-v4-flash
    reasoning_effort: none
    timeout: 30
  mcp:
    provider: deepseek
    model: deepseek-v4-flash
    reasoning_effort: none
    timeout: 30
```

虽然配置了 `kanban_decomposer`，但 `auto_decompose=false`，正常修复流程不会自动调用它。

## 20. Agnes 和 Codex 配置差异

### Agnes Implement

```yaml
agent:
  max_turns: 65
  api_max_retries: 1
  reasoning_effort: low

context_file_max_chars: 15000
file_read_max_chars: 90000

tool_output:
  max_bytes: 40000
  max_lines: 1400
  max_line_length: 1400

compression:
  enabled: true
  threshold: 0.42
  target_ratio: 0.20
  protect_last_n: 16
  protect_first_n: 3
```

### Agnes Review

```yaml
agent:
  max_turns: 28
  api_max_retries: 1
  reasoning_effort: low

context_file_max_chars: 10000
file_read_max_chars: 60000

tool_output:
  max_bytes: 30000
  max_lines: 1000
```

### Codex Gate

```yaml
agent:
  max_turns: 18
  api_max_retries: 1
  reasoning_effort: low

context_file_max_chars: 10000
file_read_max_chars: 50000

tool_output:
  max_bytes: 25000
  max_lines: 800
```

### Codex Acceptance

```yaml
agent:
  max_turns: 24
  api_max_retries: 1
  reasoning_effort: medium

context_file_max_chars: 12000
file_read_max_chars: 70000

tool_output:
  max_bytes: 35000
  max_lines: 1200
```

最终发布验收在当前会话临时使用高推理，不作为长期默认。

---

# 第四部分：角色约束与项目上下文

## 21. SOUL.md 角色约束

### 21.1 `xg-orchestrator-ds/SOUL.md`

```markdown
你是 TradingAgents xg_dev 修复工作流总控。

职责：
1. 只读取 Kanban、Git 状态和机器证据。
2. 按 PR-1、PR-2、PR-3、PR-4、PR-5、PR-5A、PR-5B、PR-6 顺序推进。
3. 不修改生产代码。
4. 不改变既定架构和范围。
5. 不创建方案外功能任务。
6. 一次只允许一个实现任务运行。
7. 不信任自然语言“已完成”，只信任测试、Git SHA 和 Evidence JSON。
8. 第二次相同失败后 BLOCKED。
9. 无状态变化时保持简短或静默。
```

### 21.2 `xg-patch-ds/SOUL.md`

```markdown
你是受文件白名单约束的小补丁实现者。

规则：
1. 只修改 allowed_files。
2. 禁止自主重构。
3. 禁止增加数据库、Provider 和技术栈。
4. 先读取 Task Contract，再读取最少必要文件。
5. 修改前记录 git status 和 HEAD。
6. 修改后运行 required_commands。
7. 只允许一次定向修正。
8. 完成时写 Evidence JSON。
9. 必须调用 kanban_complete 或 kanban_block。
```

### 21.3 `xg-implement-agnes/SOUL.md`

```markdown
你是 TradingAgents xg_dev 主实现者。

规则：
1. Task Contract 是唯一范围来源。
2. 只修改 allowed_files。
3. 不修改冻结模块。
4. 不增加第二数据库。
5. 不引入 SQLite/DuckDB 业务双写。
6. 不用 mock 掩盖 Provider 失败。
7. 数据写入必须经过标准化和质量门禁。
8. 测试失败修正不得扩大范围。
9. 完成必须提交 Git 并写 Evidence。
10. 必须调用 kanban_complete 或 kanban_block。
```

### 21.4 `xg-review-agnes/SOUL.md`

```markdown
你是只读代码审查者。

规则：
1. 不修改文件。
2. 只读取 Task Contract、Git Diff、测试摘要和 Evidence。
3. 不重新扫描整个仓库。
4. Findings 分为 BLOCKER、MAJOR、MINOR。
5. 只报告可复现问题。
6. 无 BLOCKER 和 MAJOR 才允许 PASS。
7. 输出结构化 Verdict。
```

### 21.5 `xg-gate-codex/SOUL.md`

```markdown
你是高风险方向门禁。

只检查：
1. 是否服务数据闭环。
2. 文件范围是否可控。
3. 是否引入第二数据库。
4. 是否存在隐式 mock。
5. 是否修改冻结模块。
6. API 契约是否完整。
7. 验收命令是否可执行。
8. 回滚是否明确。

不实现代码。输出 PASS 或 FAIL，理由最多 8 条。
```

### 21.6 `xg-accept-codex/SOUL.md`

```markdown
你是独立发布验收者。

规则：
1. 不修改代码。
2. 不信任实现者自述。
3. 只根据 Contract、Diff、测试结果、Evidence 和数据库检查判断。
4. head_sha 必须等于当前分支 HEAD。
5. allowed_files 必须通过。
6. blocking_issues 必须为空。
7. 默认 mock 必须关闭。
8. 只能存在一个 Canonical DuckDB。
9. Bootstrap、Browser、Backtest 必须通过。
10. 输出严格 JSON，只允许 PASS 或 FAIL。
```

## 22. 项目 `.hermes.md`

在仓库根目录创建：

```markdown
# TradingAgents xg_dev Recovery

## Goal

完成 Provider → 标准化 → 质量检查 → 单一 DuckDB → API → Web → 市场复盘 → 个股分析 → 回测。

## Canonical database

~/.tradingagents/astock/astock.duckdb

## Prohibited

- 第二个 K 线 DuckDB
- SQLite/DuckDB 业务双写
- local-release PostgreSQL
- 默认 mock
- 自动交易扩展

## Frozen

- QMT
- Paper Trading
- Scheduler
- Notifications
- Alerts
- SSE
- RBAC
- 多用户
- 新 Provider

## Source of truth

docs/TradingAgents_xg_dev_修复与Hermes低Token自动化实施方案_V1.6.1.md

## Task rules

- 只修改 allowed_files
- 单任务最多 8 个生产文件
- 第二次相同失败 BLOCKED
- 验收只接受机器证据
```

不要同时维护内容重复的大型 `AGENTS.md`、`.hermes.md` 和 `CLAUDE.md`。

## 23. 低 Token 上下文包

创建：

```bash
mkdir -p "$XG_REPO/.hermes-workflow"/{context,contracts,evidence,logs,review,manifests}
```

文件：

```text
.hermes-workflow/context/PROJECT_BRIEF.md
.hermes-workflow/context/REPO_MAP.md
.hermes-workflow/context/QUALITY_GATES.md
.hermes-workflow/context/API_CONTRACT.md
```

约束：

- `PROJECT_BRIEF.md`：不超过 100 行；
- `REPO_MAP.md`：不超过 150 行；
- `QUALITY_GATES.md`：只保存确定性门禁；
- `API_CONTRACT.md`：只保存 Setup、Bootstrap、Dashboard、Market Review、Stock Analysis、Backtest 契约；
- 不复制完整源码；
- 不保存完整成功测试日志；
- 动态 SHA 和当前任务放在 Prompt 末尾，保持 DeepSeek 固定前缀稳定。

## 24. Prompt 大小基线

执行：

```bash
for p in \
  xg-orchestrator-ds \
  xg-patch-ds \
  xg-implement-agnes \
  xg-review-agnes \
  xg-gate-codex \
  xg-accept-codex
do
  hermes -p "$p" prompt-size --json \
    > "$XG_REPO/.hermes-workflow/manifests/prompt-size-$p.json"
done
```

检查固定 Prompt 中占比最大的：

```text
Skills index
Tool schemas
Memory
SOUL.md
.hermes.md
其他自动上下文文件
```

未使用的 Skills 和 Toolsets 应在对应 Profile 中关闭。

---

# 第五部分：Git、Worktree 与 Kanban 初始化

## 25. 冻结代码并创建集成分支

默认采用 **单一集成分支 + 单一持久 Worktree + 阶段串行提交**。这是 V1.2 推荐模式：

```text
xg_dev
  ↓
fix/xg-dev-data-loop-v033
  ↓
.worktrees/xg-integration
  ├── PR-1 阶段提交
  ├── PR-2 阶段提交
  ├── PR-3 阶段提交
  ├── PR-4 阶段提交
  ├── PR-5 阶段提交
  ├── PR-5A 阶段提交
  ├── PR-5B 阶段提交
  └── PR-6 阶段提交
        ↓
最终一次 PR → xg_dev
```

优点：

- 不需要 Cron 自动合并八个阶段分支；
- 不产生阶段 Worktree 之间的依赖漂移；
- Review 只使用每阶段的 `base_sha → head_sha`；
- Kanban Parent 依赖即可保证串行；
- Token 和运维复杂度最低；
- 最终仍保留八组清晰提交和八份 Acceptance Evidence（PR-1、PR-2、PR-3、PR-4、PR-5、PR-5A、PR-5B、PR-6）。

执行：

```bash
cd "$XG_REPO"
git switch xg_dev
git pull --ff-only

git tag "backup/xg-dev-before-data-fix-20260722"
git push origin "backup/xg-dev-before-data-fix-20260722"

git branch "$XG_INTEGRATION_BRANCH" xg_dev
mkdir -p "$XG_REPO/.worktrees"

git worktree add \
  "$XG_REPO/.worktrees/xg-integration" \
  "$XG_INTEGRATION_BRANCH"
```

`.gitignore` 增加：

```gitignore
.worktrees/
.hermes-workflow/logs/
```

Evidence、Contract 和 Manifest 建议提交；大日志不提交。

### 可选严格隔离模式

只有出现以下情况才为单个阶段建立独立 Worktree：

- PR-2 数据迁移需要危险实验；
- PR-4 Bootstrap 并发修改范围扩大；
- 同一阶段需要两种实现方案做 A/B 比较；
- 人工要求每阶段单独 GitHub PR。

即使使用独立 Worktree，也一次只运行一个 Implementation Worker，并在下阶段开始前合并回 Integration Branch。

## 26. 初始化 Kanban Board

使用 Orchestrator Profile：

```bash
hermes -p xg-orchestrator-ds kanban init

hermes -p xg-orchestrator-ds kanban boards create tradingagents-xgdev \
  --name "TradingAgents xg_dev Recovery" \
  --description "数据闭环、DuckDB、Provider、Data Hub 与 Web 修复" \
  --switch
```

确认：

```bash
hermes -p xg-orchestrator-ds kanban boards show
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" list --json
```

## 27. 推荐工作区

所有默认任务统一使用：

```text
dir:$XG_REPO/.worktrees/xg-integration
```

每个阶段开始时由确定性脚本记录：

```text
phase
base_sha
branch
worktree
allowed_files
```

每个阶段完成时记录 `head_sha`。下一阶段以当前 `head_sha` 作为新的 `base_sha`。

禁止：

- 两个 Implementation Worker 同时修改该 Worktree；
- Review Worker 修改文件；
- Acceptance Worker 修改文件；
- Controller 在 Worktree 有未提交变更时推进阶段。

## 28. 八阶段顺序

```text
PR-1 运行基础
  ↓
PR-2 单一 DuckDB
  ↓
PR-3 Provider 与真实数据语义
  ↓
PR-4 Setup 与 Bootstrap
  ↓
PR-5 Data Hub、Dashboard 与 K 线
  ↓
PR-5A 市场复盘与个股综合分析
  ↓
PR-5B Canonical Backtest 闭环
  ↓
PR-6 扩展数据质量、CI 与发布门禁
  ↓
Final Offline + Live + Browser Acceptance
```

同一时间只允许一个 Implementation Task 处于 `running`。Kanban 依赖关系负责顺序推进，不依赖模型自行记忆阶段。

---

# 第六部分：PR-1～PR-6（含 PR-5A、PR-5B）修复任务

## 29. PR-1：运行基础

### 目标

- 修复 `local-release` 最小 Provider 依赖；
- 增加 `scripts/astock_doctor.py`；
- 增加 `scripts/setup_local.sh`；
- 增加 `scripts/start_local.sh`；
- 统一安装文档；
- 全新虚拟环境可诊断；
- 空库启动后自动进入首次设置页。

### 允许文件

```text
pyproject.toml
scripts/astock_doctor.py
scripts/setup_local.sh
scripts/start_local.sh
tests/test_astock_local_release_dependencies.py
tests/test_astock_local_startup.py
docs/02-user-guide.md
README.md
```

### 建议依赖

```toml
local-release = [
    "duckdb>=1.5.0",
    "pyarrow>=24.0.0",
    "akshare>=1.18.0",
    "mootdx>=0.11.7",
    "baostock>=0.9.3",
    "playwright>=1.52.0",
    "pytest>=8.0",
]

research-providers = [
    "pywencai>=0.13.0",
]
```

实际版本应以当前项目兼容性测试为准，不盲目升级到不兼容版本。

### Doctor 检查

```text
Python 版本
DuckDB
AkShare
Mootdx
BaoStock
数据库目录可写
当前数据库路径
表是否初始化
K 线行数
标的数量
mock 开关
旧第二数据库
Provider 探测
LLM Key
backend.json 冲突
```

### 一键脚本职责

`setup_local.sh` 必须：

```text
检查 Python 3.12
→ 创建 .venv
→ 升级 pip
→ 安装 local-release
→ 创建数据目录
→ 运行 Doctor
→ 输出下一步命令
```

`start_local.sh` 必须：

```text
检查 .venv 和依赖
→ 运行快速 Doctor
→ 启动 Flask
→ 等待 /health
→ 自动打开浏览器
```

### 验收

```bash
rm -rf .venv
./scripts/setup_local.sh
./scripts/start_local.sh
.venv/bin/python scripts/astock_doctor.py
.venv/bin/pytest \
  tests/test_astock_local_release_dependencies.py \
  tests/test_astock_local_startup.py -v
git diff --check
```

### 模型分配

```text
实现：DeepSeek Patch
Review：Agnes Review
Acceptance：Codex low
```

## 30. PR-2：单一 DuckDB

### 目标

- local-release 只使用：

```text
~/.tradingagents/astock/astock.duckdb
```

- 禁止遗留配置静默切换 PostgreSQL；
- 停用第二个 K 线 DuckDB 正式查询；
- 增加安全迁移脚本。

### 允许文件

```text
tradingagents/astock/api/__init__.py
tradingagents/astock/api/app_factory.py
tradingagents/astock/store/backend.py
scripts/migrate_astock_single_db.py
tests/test_astock_single_database.py
.env.example
```

### 强制配置

```python
ASTOCK_PERMANENT_KLINE_ENABLED = False
ASTOCK_MOCK_DATA_ENABLED = False
ASTOCK_DB_BACKEND = "duckdb"
ASTOCK_DB_PATH = "~/.tradingagents/astock/astock.duckdb"
```

### 迁移规则

1. 先备份；
2. `--dry-run`；
3. 按主键 Upsert；
4. 标准化；
5. 质量检查；
6. 异常进入隔离表；
7. 比较行数、标的、时间范围和重复数；
8. 不删除旧数据库。

### 验收

```bash
.venv/bin/pytest tests/test_astock_single_database.py -v
.venv/bin/python scripts/migrate_astock_single_db.py --dry-run
git diff --check
```

### 模型分配

```text
Gate：Codex medium
实现：Agnes
Review：Agnes Review
Acceptance：Codex high
```

## 31. PR-3：Provider 与真实数据语义

### 目标

- Provider 独立加载；
- 每个 Provider 独立捕获缺依赖、配置、超时、限流和解析错误；
- 单 Provider 探测 3 秒，整体 10 秒，缓存 60 秒；
- 修复健康检查异常日志变量；
- 默认禁止生成假行情。

### 状态

```text
available
degraded
unconfigured
missing_dependency
timeout
rate_limited
unavailable
```

### 最低真实 Provider 可用标准

Provider 不能只通过 `import` 判定可用，至少验证：

```text
symbol = 600519.SH
interval = 1d
返回记录 >= 5
source != mock
close > 0
bar_time 非空
整体请求 <= 10 秒
```

健康检查只允许轻量探测，不得下载完整历史数据。

### Mock 规则

仅在以下条件允许：

```text
ASTOCK_MOCK_DATA_ENABLED=true
```

或显式测试参数：

```text
?mock=1
```

返回必须包含：

```json
{
  "source": "mock",
  "quality": "mock",
  "is_real_data": false
}
```

### 允许文件

```text
tradingagents/astock/api/routes_data_health.py
tradingagents/astock/api/routes_market_data.py
tests/test_astock_provider_health_isolation.py
tests/test_astock_no_implicit_mock.py
```

### 验收

```bash
.venv/bin/pytest \
  tests/test_astock_provider_health_isolation.py \
  tests/test_astock_no_implicit_mock.py -v
git diff --check
```

### 模型分配

```text
Gate：Codex medium
实现：Agnes
Review：Agnes Review
Acceptance：Codex high
```

## 32. PR-4：Setup、Bootstrap、核心清洗与事务入库

### 目标

新增：

```http
GET /api/v1/setup/status
POST /api/v1/setup/bootstrap
GET /api/v1/setup/jobs/<job_id>
```

状态：

```text
ready
empty
degraded
blocked
migrating
refreshing
```

默认标的：

```text
000001.SH 上证指数
399001.SZ 深证成指
000300.SH 沪深300
399006.SZ 创业板指
600519.SH 贵州茅台
000858.SZ 五粮液
000001.SZ 平安银行
```

默认参数：

```text
interval = 1d
start = 最近三年
capabilities = kline, valuation
```

任务状态：

```text
queued
→ validating_environment
→ fetching
→ normalizing
→ quality_checking
→ writing
→ verifying
→ completed/partial/failed
```

必须复用已有 `DataJobManager`，不能新建第二套任务线程系统。

### 核心清洗必须在首次写库前完成

首次真实数据进入 Canonical DuckDB 前必须完成：

```text
symbol 标准化
provider_symbol 记录
bar_time 标准化
OHLC 数字转换
OHLC 完整性检查
volume 非负检查
主键去重
日期合法性检查
数据排序
source / fetched_at / as_of 记录
ingestion_run_id 记录
异常数据隔离
```

顺序必须是：

```text
Provider Raw Response
→ Normalize
→ Core Quality Gate
→ Transactional Upsert
→ Post-write Verification
```

禁止“先写库、后续 PR 再补清洗”。

### 单标的事务和失败隔离

每个标的单独执行：

```text
创建 ingestion_run_item
→ 获取数据
→ 标准化
→ 质量检查
→ BEGIN TRANSACTION
→ Upsert kline_bars
→ 写质量统计
→ 更新 ingestion_run_item
→ COMMIT
```

单标的失败：

```text
ROLLBACK 当前标的
→ 记录 Provider 尝试顺序和错误
→ 继续下一个标的
```

禁止使用一个覆盖全部标的的大事务。

### 幂等与唯一键

K 线唯一键：

```text
symbol + interval + bar_time
```

建议约束：

```sql
UNIQUE(symbol, interval, bar_time)
```

Bootstrap Job 幂等键：

```text
bootstrap:{symbol_set_hash}:{start}:{end}:{interval}
```

用户连续点击不得创建重复任务或重复数据。

### 允许文件

```text
tradingagents/astock/api/routes_setup.py
tradingagents/astock/api/blueprint_registry.py
tradingagents/astock/api/app_hooks.py
tradingagents/astock/store/loader.py
tradingagents/astock/store/ 事务或 Repository 相关文件（Task Contract 精确列出）
tradingagents/astock/quality/ 核心质量规则文件（Task Contract 精确列出）
已有 DataJobManager 相关文件（Task Contract 精确列出）
tests/test_astock_setup_status.py
tests/test_astock_setup_bootstrap.py
tests/test_astock_bootstrap_idempotency.py
tests/test_astock_transactional_ingest.py
```

### 成功标准

```text
至少一个真实 Provider 成功
至少四个指数写入成功
至少一个示例股票写入成功
每个成功标的至少 250 条日 K
重复主键数量 == 0
隔离记录和质量统计可查询
```

单标的失败不得中断其他标的。

### 验收

```bash
.venv/bin/pytest \
  tests/test_astock_setup_status.py \
  tests/test_astock_setup_bootstrap.py \
  tests/test_astock_bootstrap_idempotency.py \
  tests/test_astock_transactional_ingest.py -v
git diff --check
```

### 模型分配

```text
Gate：Codex medium
实现：Agnes
Review：Agnes Review
Acceptance：Codex high
```

## 33. PR-5：Data Hub、Dashboard 与 K 线展示

### 目标

新增：

```text
/data_hub
tradingagents/astock/web/templates/ops/data_hub.html
tradingagents/astock/web/static/js/data-hub.js
```

页面显示：

```text
数据库状态
Provider 状态
快速初始化
自定义初始化
任务进度
数据库统计
隔离数据统计
最近刷新任务
旧数据库迁移提示
```

Dashboard 空库状态：

```text
本地行情库尚未初始化
当前没有可展示的真实行情
[前往数据中心]
```

首次访问 `/` 时必须调用 `/api/v1/setup/status`。若 `state == empty`，自动跳转：

```text
/data_hub?first_run=1
```

K 线页面必须显示：

```text
symbol
interval
latest_bar_time
source
quality
row_count
```

并只从 Canonical DuckDB 读取。

首页首次加载只允许轻量调用：

```text
/setup/status
/dashboard/overview
/data/health?cached=1
```

不得自动：

```text
请求 LLM
下载完整行情
自动回测
自动写库
分析所有自选股
```

### 允许文件

```text
tradingagents/astock/web/blueprints/ops_bp.py
tradingagents/astock/web/templates/ops/data_hub.html
tradingagents/astock/web/static/js/data-hub.js
tradingagents/astock/web/templates/base.html
tradingagents/astock/web/templates/dashboard.html
tradingagents/astock/api/routes_dashboard.py
相关 Browser Tests
```

### 模型分配

```text
主实现：Agnes
小型模板/JS 修正：DeepSeek Patch
Review：Agnes Review
Acceptance：Codex medium
```


## 33A. PR-5A：市场复盘与个股综合分析

### 目标

将市场复盘和个股综合分析作为 `0.3.3` 基础功能，而不是后续扩展。形成：

```text
Canonical DuckDB 真实数据
→ 确定性指标和结构化事实
→ 市场情绪与风险规则
→ 可选 LLM 解释
→ 复盘/分析持久化
→ Web 展示
→ 一键进入回测
```

### 33A.1 市场复盘最小功能

指数至少覆盖：

```text
000001.SH 上证指数
399001.SZ 深证成指
399006.SZ 创业板指
000300.SH 沪深300
000688.SH 科创50
000905.SH 中证500
000852.SH 中证1000
```

每个指数计算：

```text
开盘、收盘、涨跌幅、振幅
成交额、成交额环比
5 日和 20 日涨跌幅
MA5 / MA10 / MA20 趋势
相对强弱
数据来源和更新时间
```

市场宽度至少计算：

```text
上涨家数
下跌家数
平盘家数
上涨比例
涨幅 >= 5% 数量
跌幅 <= -5% 数量
创新高数量
创新低数量
全市场中位数涨跌幅
```

情绪至少计算：

```text
涨停数量
跌停数量
首板数量
二板数量
三板及以上数量
最高连板高度
炸板数量
炸板率
昨日涨停平均表现
昨日连板平均表现
赚钱效应评分
亏钱效应评分
```

情绪周期必须由确定性状态机产生：

```text
冰点
修复
启动
发酵
高潮
分化
退潮
```

状态机的输入、阈值和版本必须保存。LLM 只能解释状态机结果，不得直接决定市场周期。

板块复盘至少包含：

```text
行业涨跌幅排行
概念涨跌幅排行
行业/概念成交额排行
资金流入和流出排行
板块涨停数量
板块强度
板块持续性
板块轮动
```

强弱标的至少包含：

```text
涨停梯队
成交额前列
换手率前列
量比前列
创新高和创新低
趋势强势股
高位风险股
跌停股
炸板股
异常放量股
```

当对应 Provider 不支持某项数据时必须返回：

```text
data_state = unavailable
```

不得使用 mock 补齐正式复盘。

### 33A.2 个股综合分析最小功能

分析维度：

```text
technical
fundamental
valuation
capital_flow
news
sector
sentiment
risk
```

技术面至少包含：

```text
趋势方向
MA5 / MA10 / MA20 / MA60
MACD
RSI
KDJ
布林带
ATR
成交量和换手率
量价关系
支撑位和压力位
突破/跌破状态
回撤风险
```

基本面至少包含：

```text
营业收入
净利润
扣非净利润
营收增长率
利润增长率
ROE
毛利率
净利率
资产负债率
经营现金流
每股收益
财务趋势
```

估值面至少包含：

```text
PE
PB
PS
股息率
总市值
流通市值
历史估值分位
行业估值分位
```

资金面按数据可用性提供：

```text
主力资金
超大单、大单、中单、小单
北向资金
融资余额
成交额
换手率
资金连续性
```

消息面至少处理：

```text
新闻
公告
业绩预告
业绩快报
股东增减持
回购
解禁
监管问询
重大合同
诉讼
风险提示
研报
```

板块和市场联动至少计算：

```text
所属行业和概念
板块强度和排名
同板块领涨股
与主要指数相关性
与行业指数相关性
相对强弱
市场情绪适配度
```

### 33A.3 确定性事实与 LLM 分层

强制链路：

```text
DuckDB 真实数据
→ Deterministic Calculators
→ Structured Facts
→ Risk Rules
→ Optional LLM Interpretation
→ Persistent Report
```

禁止：

```text
只输入股票代码
→ 让 LLM 凭记忆生成分析
```

事实记录必须包含：

```text
fact_id
dimension
metric
value
unit
as_of
source
quality_tag
calculation_version
data_hash
ingestion_run_id
```

模型解释必须包含：

```text
content_type = model_interpretation
based_on_fact_ids
model_provider
model_id
prompt_version
generated_at
```

LLM 不可用、超时或额度不足时：

- 技术指标、财务指标、估值、资金、新闻、板块和风险规则仍须正常展示；
- API 返回 `interpretation_state=unavailable`；
- 不得将整个分析任务标记为失败；
- 不得自动切换到未批准模型；
- 不得生成没有事实引用的替代结论。

### 33A.4 数据完整性门禁

正式生成市场复盘前至少满足：

```text
trade_date 为有效交易日
至少 5 个主要指数成功
上涨 + 下跌 + 平盘 > 0
至少一个行业或概念板块来源成功
涨跌停数据可用，或明确标记 unavailable
正式数据 source != mock
```

正式生成个股分析前至少满足：

```text
日 K >= 120 条
最新交易日有效
技术指标可计算
至少一个基本面或估值来源可用
数据截止时间明确
source != mock
```

数据不足时：

```json
{
  "data_state": "insufficient_data",
  "missing_capabilities": ["fundamental"],
  "conclusion": null
}
```

不得输出确定性的看多、看空或买卖结论。

### 33A.5 数据表

全部写入 Canonical DuckDB：

```text
market_review_runs
market_review_snapshots
market_index_daily
market_breadth_daily
market_sentiment_daily
sector_performance_daily
limit_up_daily
limit_down_daily
limit_up_ladders
market_leaders_daily
stock_analysis_runs
stock_analysis_facts
stock_analysis_reports
stock_risk_signals
technical_indicator_snapshots
```

建议唯一键：

```text
market_review_runs:
  UNIQUE(review_date, market, calculation_version)

market_breadth_daily:
  UNIQUE(trade_date, market)

sector_performance_daily:
  UNIQUE(trade_date, sector_type, sector_code)

stock_analysis_facts:
  UNIQUE(run_id, dimension, metric)

stock_analysis_reports:
  UNIQUE(run_id, report_version)
```

重复生成相同日期复盘时使用 Upsert 或返回已有结果，不得产生不可控重复快照。

### 33A.6 市场复盘 API

```http
GET  /api/v1/market-review/status
POST /api/v1/market-review/generate
GET  /api/v1/market-review/latest
GET  /api/v1/market-review/dates
GET  /api/v1/market-review/<trade_date>
GET  /api/v1/market-review/<trade_date>/breadth
GET  /api/v1/market-review/<trade_date>/sentiment
GET  /api/v1/market-review/<trade_date>/sectors
GET  /api/v1/market-review/<trade_date>/leaders
```

生成请求：

```json
{
  "trade_date": "2026-07-22",
  "market": "CN_A",
  "use_llm": true,
  "force_refresh": false
}
```

状态机：

```text
queued
→ validating
→ loading_market_data
→ calculating_breadth
→ calculating_sentiment
→ calculating_sectors
→ selecting_leaders
→ generating_summary
→ persisting
→ completed / partial / failed
```

### 33A.7 个股分析 API

```http
POST /api/v1/analysis/stocks
GET  /api/v1/analysis/stocks/<symbol>/latest
GET  /api/v1/analysis/stocks/<symbol>/history
GET  /api/v1/analysis/runs/<run_id>
GET  /api/v1/analysis/runs/<run_id>/facts
GET  /api/v1/analysis/runs/<run_id>/report
```

请求：

```json
{
  "symbol": "600519.SH",
  "as_of": "2026-07-22",
  "dimensions": [
    "technical",
    "fundamental",
    "valuation",
    "capital_flow",
    "news",
    "sector",
    "risk"
  ],
  "use_llm": true
}
```

响应必须包含：

```json
{
  "symbol": "600519.SH",
  "as_of": "2026-07-22",
  "data_state": "ready",
  "data_cutoff": "2026-07-22T15:00:00+08:00",
  "conclusion": {
    "trend": "neutral",
    "sentiment": "warm",
    "risk_level": "medium"
  },
  "technical": {},
  "fundamental": {},
  "valuation": {},
  "capital_flow": {},
  "news": {},
  "sector": {},
  "risks": [],
  "evidence": [],
  "data_sources": [],
  "quality": {},
  "interpretation_state": "available",
  "generated_at": ""
}
```

### 33A.8 Web 页面和串联路径

新增：

```text
/market_review
/market_review/<trade_date>
/analysis
/analysis/<symbol>
```

市场复盘页面模块：

```text
市场总览
指数表现
市场宽度
涨跌停统计
连板梯队
情绪周期
行业和概念排行
资金方向
强势股和风险股
今日主线
今日风险
明日观察项
```

个股分析页面模块：

```text
综合结论
数据截止时间
技术面
基本面
估值面
资金面
消息面
所属板块
风险提示
事实证据
数据来源和质量
历史分析记录
回测入口
```

必须打通：

```text
市场复盘
→ 查看强势板块
→ 选择板块股票
→ 打开个股分析
→ 选择回测策略
→ 查看回测结果
```

### 33A.9 允许文件

Task Contract 必须进一步细化到具体文件。允许目录：

```text
tradingagents/astock/review/
tradingagents/astock/analysis/
tradingagents/astock/quality/
tradingagents/astock/store/
tradingagents/astock/api/routes_market_review.py
tradingagents/astock/api/routes_analysis.py
tradingagents/astock/web/blueprints/
tradingagents/astock/web/templates/market_review/
tradingagents/astock/web/templates/analysis/
tradingagents/astock/web/static/js/
tests/test_astock_market_*.py
tests/test_astock_stock_analysis_*.py
```

单个 Implementation Task 仍以不超过 8 个生产文件为硬限制。

### 33A.10 任务拆分

```text
FIX-5A01 Schema 与 Repository
FIX-5A02 指数和市场宽度
FIX-5A03 涨跌停与连板梯队
FIX-5A04 板块强度与轮动
FIX-5A05 市场情绪状态机
FIX-5A06 市场复盘 API
FIX-5A07 市场复盘 Web
FIX-5A08 个股结构化指标
FIX-5A09 个股风险规则
FIX-5A10 LLM 解释与事实引用
FIX-5A11 个股分析 API
FIX-5A12 个股分析 Web
FIX-5A13 持久化、幂等与重启读取
FIX-5A14 Integration、Browser 与 Acceptance Evidence
```

模型分配：

```text
高风险 Gate：Codex medium
Schema/计算/状态机/API：Agnes
模板和小型 JS：DeepSeek Patch
普通 Review：Agnes Review
最终 Acceptance：Codex high
```

### 33A.11 验收

新增测试：

```text
tests/test_astock_market_review_schema.py
tests/test_astock_market_breadth.py
tests/test_astock_market_sentiment.py
tests/test_astock_limit_up_ladder.py
tests/test_astock_sector_performance.py
tests/test_astock_market_review_api.py
tests/test_astock_market_review_persistence.py
tests/test_astock_stock_analysis_facts.py
tests/test_astock_stock_analysis_api.py
tests/test_astock_stock_analysis_no_llm.py
tests/test_astock_stock_analysis_lineage.py
tests/test_astock_market_review_browser.py
tests/test_astock_stock_analysis_browser.py
```

执行：

```bash
.venv/bin/pytest \
  tests/test_astock_market_review_schema.py \
  tests/test_astock_market_breadth.py \
  tests/test_astock_market_sentiment.py \
  tests/test_astock_limit_up_ladder.py \
  tests/test_astock_sector_performance.py \
  tests/test_astock_market_review_api.py \
  tests/test_astock_market_review_persistence.py \
  tests/test_astock_stock_analysis_facts.py \
  tests/test_astock_stock_analysis_api.py \
  tests/test_astock_stock_analysis_no_llm.py \
  tests/test_astock_stock_analysis_lineage.py -v

.venv/bin/pytest \
  tests/test_astock_market_review_browser.py \
  tests/test_astock_stock_analysis_browser.py -v

git diff --check
```

Acceptance 必须验证：

```text
复盘只使用真实数据
日期与交易日匹配
重复生成不产生重复结果
市场宽度计算正确
情绪状态机可重复
涨跌停梯队和板块排名正确
分析事实来自 Canonical DuckDB
LLM 不可用时结构化分析仍可用
模型解释引用事实 ID
报告记录数据截止时间
复盘和报告重启后仍可查询
分析页面可进入回测
```


## 33B. PR-5B：Canonical Backtest 闭环

### 目标

形成：

```text
Web 选择标的和策略
→ Canonical DuckDB 读取 K 线
→ 运行回测
→ 保存 backtest_runs
→ 保存 backtest_trades
→ Web 展示结果
→ 重启后仍可查询
```

### 默认验收策略

```text
标的：600519.SH
周期：日线
区间：最近至少 250 个交易日
策略：MA5 上穿 MA20 买入，MA5 下穿 MA20 卖出
初始资金：100000
手续费：0.0003
滑点：0.001
```

### A 股基础交易规则

最小回测引擎必须处理：

```text
T+1 卖出约束
最小交易单位 100 股
买卖双向佣金
最低佣金可配置
卖出印花税
滑点
停牌不可成交
涨停时买入不可成交
跌停时卖出不可成交
复权模式显式记录
```

无未来函数规则：

```text
t 日收盘产生的信号，最早在 t+1 可交易时点成交
财务数据按真实披露时间可见
新闻和公告按发布时间可见
禁止使用未来复权信息生成当期信号
历史成分股回测不得用当前成分回填
```

基准至少支持：

```text
沪深300
中证500
上证指数
买入并持有
```

基础指标至少包括：

```text
累计收益率
年化收益率
基准收益率
超额收益率
最大回撤
夏普比率
索提诺比率
胜率
盈亏比
交易次数
换手率
最长回撤周期
```

每次回测必须保存：

```text
strategy_id
strategy_version
code_commit_sha
data_snapshot_time
data_hash
parameters
fee_model
slippage_model
benchmark
price_adjustment
random_seed
```


### 强制约束

```text
输入 K 线 >= 250
source != mock
数据库路径 == Canonical DuckDB
回测状态 == completed
最终净值为有限数
交易次数 >= 0
结果写入 backtest_runs
交易明细写入 backtest_trades
重启后结果仍存在
```

回测不得：

```text
直接调用 Provider
读取第二数据库
使用 mock
静默切换内存 fixture
只在页面显示而不持久化
```

### 允许文件

```text
tradingagents/astock/backtest/ 相关实现文件（Task Contract 精确列出）
tradingagents/astock/api/ 回测路由文件（Task Contract 精确列出）
tradingagents/astock/web/ 回测页面文件（Task Contract 精确列出）
tests/test_astock_backtest_canonical_store.py
tests/test_astock_backtest_api.py
tests/test_astock_backtest_no_lookahead.py
tests/test_astock_backtest_astock_rules.py
tests/test_astock_backtest_reproducibility.py
tests/test_astock_backtest_browser.py
```

### 验收

```bash
.venv/bin/pytest \
  tests/test_astock_backtest_canonical_store.py \
  tests/test_astock_backtest_api.py -v
.venv/bin/pytest tests/test_astock_backtest_browser.py -v
git diff --check
```

### 模型分配

```text
Gate：Codex medium
实现：Agnes
Review：Agnes Review
Acceptance：Codex high
```

## 34. PR-6：扩展数据质量、CI 与发布门禁

### 数据元信息

```text
source
provider_symbol
fetched_at
as_of
quality_tag
raw_hash
ingestion_run_id
```

`quality_tag`：

```text
normal
fallback
partial
stale
degraded
mock
```

PR-4 已完成核心 K 线门禁；PR-6 继续补充并固化以下扩展规则：

1. 标的标准化；
2. 时间非空；
3. OHLC 为有限数；
4. 高低价完整性；
5. 成交量非负；
6. 主键去重；
7. 日期不超过市场日期；
8. 非停牌数据不全为零；
9. 写入前排序；
10. 写入后核对行数和范围；
11. 使用 Upsert，不简单 Append。

扩展新闻、公告和研报清洗：

```text
HTML/脚本清理
时间解析
URL 标准化
内容去重
字符编码检查
公告 ID 去重
PDF URL 校验
机构/评级标准化
空报告隔离
```

### 验收脚本

新增：

```text
scripts/verify_astock_data_loop.sh
```

流程：

```text
临时 HOME
空 DuckDB
启动 Flask
setup/status == empty
Fixture Bootstrap
核心清洗前置检查
单标的事务与幂等检查
Dashboard
K 线
市场复盘
个股结构化分析
无 LLM 降级分析
复盘与分析持久化
Canonical Backtest
A 股交易规则与无未来函数
回测结果持久化
重启
持久化
无隐式 mock
单数据库
Browser Test
```

### 模型分配

```text
Gate：Codex high
实现：Agnes
Review：Agnes Review
Acceptance：Codex high
```

---

# 第七部分：Kanban 任务链与合同

## 35. 每阶段任务链（含 PR-5A、PR-5B）

```text
Task Spec
  ↓
可选 Codex Gate
  ↓
Implementation
  ↓
No-Agent Verification
  ↓
Agnes Review
  ↓
Codex Acceptance
  ↓
Controller Evidence Check
  ↓
Merge
```

No-Agent Verification 是脚本，不是模型 Profile。

## 36. Task Contract 模板

```yaml
task_id: FIX-201
phase: PR-2
role: implementation

goal:
  local-release 只使用一个 canonical DuckDB

source_of_truth:
  docs/TradingAgents_xg_dev_修复与Hermes低Token自动化实施方案_V1.6.1.md

context_files:
  - .hermes-workflow/context/PROJECT_BRIEF.md
  - .hermes-workflow/context/REPO_MAP.md
  - .hermes-workflow/context/QUALITY_GATES.md

allowed_files:
  - tradingagents/astock/api/__init__.py
  - tradingagents/astock/api/app_factory.py
  - tradingagents/astock/store/backend.py
  - scripts/migrate_astock_single_db.py
  - tests/test_astock_single_database.py

forbidden:
  - 不引入 SQLite 业务库
  - 不增加 PostgreSQL
  - 不修改交易模块
  - 不修改 Provider Router
  - 不新增页面

required_commands:
  - .venv/bin/pytest tests/test_astock_single_database.py -v
  - .venv/bin/python scripts/migrate_astock_single_db.py --dry-run
  - git diff --check

required_artifact:
  .hermes-workflow/evidence/pr2/implementation.json

max_production_files: 5
max_fix_attempts: 1

completion:
  - 代码已提交
  - 测试通过
  - Evidence 存在
  - 调用 kanban_complete

failure:
  第二次相同失败调用 kanban_block
```


## 36A. PR-5A Hermes Kanban 部署包

Hermes 部署时必须先由 Orchestrator 根据本章生成并冻结以下合同文件；合同冻结后 Implementation Worker 不得自行扩大范围：

建议先创建以下合同文件：

```text
.hermes-workflow/contracts/pr5a-gate.md
.hermes-workflow/contracts/pr5a-schema.md
.hermes-workflow/contracts/pr5a-market-engine.md
.hermes-workflow/contracts/pr5a-analysis-engine.md
.hermes-workflow/contracts/pr5a-api-web.md
.hermes-workflow/contracts/pr5a-verify.md
.hermes-workflow/contracts/pr5a-review.md
.hermes-workflow/contracts/pr5a-accept.md
```

阶段 Manifest：

```yaml
phase: PR-5A
name: Market Review and Stock Analysis
depends_on: PR-5
releases: PR-5B
workspace: dir:${XG_REPO}/.worktrees/xg-integration
base_sha_source: current_integration_head
max_parallel_implementation: 1
same_failure_limit: 2

tasks:
  - key: pr5a-gate
    assignee: xg-gate-codex
    contract: .hermes-workflow/contracts/pr5a-gate.md
    max_runtime: 1800
    max_retries: 1

  - key: pr5a-schema
    assignee: xg-implement-agnes
    parent: pr5a-gate
    contract: .hermes-workflow/contracts/pr5a-schema.md
    max_runtime: 7200
    max_retries: 1

  - key: pr5a-market-engine
    assignee: xg-implement-agnes
    parent: pr5a-schema
    contract: .hermes-workflow/contracts/pr5a-market-engine.md
    max_runtime: 10800
    max_retries: 1

  - key: pr5a-analysis-engine
    assignee: xg-implement-agnes
    parent: pr5a-market-engine
    contract: .hermes-workflow/contracts/pr5a-analysis-engine.md
    max_runtime: 10800
    max_retries: 1

  - key: pr5a-api-web
    assignee: xg-implement-agnes
    parent: pr5a-analysis-engine
    contract: .hermes-workflow/contracts/pr5a-api-web.md
    max_runtime: 10800
    max_retries: 1

  - key: pr5a-verify
    assignee: xg-patch-ds
    parent: pr5a-api-web
    contract: .hermes-workflow/contracts/pr5a-verify.md
    max_runtime: 3600
    max_retries: 1

  - key: pr5a-review
    assignee: xg-review-agnes
    parent: pr5a-verify
    contract: .hermes-workflow/contracts/pr5a-review.md
    max_runtime: 3600
    max_retries: 1

  - key: pr5a-accept
    assignee: xg-accept-codex
    parent: pr5a-review
    contract: .hermes-workflow/contracts/pr5a-accept.md
    max_runtime: 3600
    max_retries: 1
```

幂等键：

```text
xg-v033-pr5a-gate-v1
xg-v033-pr5a-schema-v1
xg-v033-pr5a-market-engine-v1
xg-v033-pr5a-analysis-engine-v1
xg-v033-pr5a-api-web-v1
xg-v033-pr5a-verify-v1
xg-v033-pr5a-review-v1
xg-v033-pr5a-accept-v1
```

PR-5A Acceptance Evidence：

```json
{
  "schema_version": "1.0",
  "phase": "PR-5A",
  "verdict": "PASS",
  "base_sha": "abc123",
  "head_sha": "def456",
  "allowed_files_ok": true,
  "canonical_database_ok": true,
  "implicit_mock_found": false,
  "market_review": {
    "trade_date_valid": true,
    "major_indices_success": 5,
    "breadth_valid": true,
    "sentiment_reproducible": true,
    "sector_data_available": true,
    "persistence_passed": true
  },
  "stock_analysis": {
    "facts_from_duckdb": true,
    "minimum_kline_rows": 120,
    "no_llm_mode_passed": true,
    "fact_citations_passed": true,
    "data_cutoff_recorded": true,
    "persistence_passed": true
  },
  "browser": {
    "market_review_passed": true,
    "stock_analysis_passed": true,
    "analysis_to_backtest_passed": true
  },
  "blocking_issues": []
}
```

Controller 必须在 `PR-5A` PASS 后才释放 `PR-5B`。


## 37. 任务创建示例

创建 Gate：

```bash
GATE_JSON=$(hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" create \
  "PR-2 Gate: Single DuckDB" \
  --assignee xg-gate-codex \
  --workspace "dir:$XG_REPO/.worktrees/xg-integration" \
  --idempotency-key "xg-v033-pr2-gate-v1" \
  --max-runtime 1800 \
  --max-retries 1 \
  --body "$(cat "$XG_REPO/.hermes-workflow/contracts/pr2-gate.md")" \
  --json)
```

从 JSON 中读取 Task ID 的方式应根据当前 CLI 输出结构实现，不使用文本截断猜 ID。

创建实现任务并设置 Parent：

```bash
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" create \
  "PR-2 Implement: Single DuckDB" \
  --assignee xg-implement-agnes \
  --parent "$GATE_TASK_ID" \
  --workspace "dir:$XG_REPO/.worktrees/xg-integration" \
  --idempotency-key "xg-v033-pr2-implement-v1" \
  --max-runtime 7200 \
  --max-retries 1 \
  --body "$(cat "$XG_REPO/.hermes-workflow/contracts/pr2-implement.md")" \
  --json
```

后续 Verification、Review、Acceptance 依次设置 Parent。

## 38. 幂等键规范

```text
xg-v033-pr1-implement-v1
xg-v033-pr1-review-v1
xg-v033-pr1-accept-v1
xg-v033-pr2-gate-v1
xg-v033-pr2-implement-v1
...
xg-v033-pr5a-gate-v1
xg-v033-pr5a-schema-v1
xg-v033-pr5a-market-engine-v1
xg-v033-pr5a-analysis-engine-v1
xg-v033-pr5a-api-web-v1
xg-v033-pr5a-verify-v1
xg-v033-pr5a-review-v1
xg-v033-pr5a-accept-v1
xg-v033-pr5b-gate-v1
xg-v033-pr5b-implement-v1
xg-v033-pr5b-review-v1
xg-v033-pr5b-accept-v1
...
xg-v033-final-accept-v1
```

Cron 重复执行时，相同 Idempotency Key 必须返回已有任务，不能重复创建。

## 39. Worker 协议

Worker 启动后必须：

1. 调用 `kanban_show()`；
2. 读取 Task Contract；
3. 记录 HEAD 和工作区状态；
4. 长任务至少每小时 `kanban_heartbeat`；
5. 完成后 `kanban_complete`；
6. 无法完成时 `kanban_block`；
7. 禁止仅输出自然语言后退出。

Worker 成功退出但没有 complete/block 属于协议违规，应由 Dispatcher 重试并最终熔断。

---

# 第八部分：Evidence、Review 与机器验收

## 40. Evidence 目录

```text
.hermes-workflow/evidence/pr1/
.hermes-workflow/evidence/pr2/
.hermes-workflow/evidence/pr3/
.hermes-workflow/evidence/pr4/
.hermes-workflow/evidence/pr5/
.hermes-workflow/evidence/pr5a/
.hermes-workflow/evidence/pr5b/
.hermes-workflow/evidence/pr6/
.hermes-workflow/evidence/final/
```

每阶段：

```text
gate.json
implementation.json
verification.json
review.json
acceptance.json
```

## 41. Acceptance JSON

```json
{
  "schema_version": "1.0",
  "phase": "PR-2",
  "task_id": "t_xxxxx",
  "verdict": "PASS",
  "base_sha": "abc123",
  "head_sha": "def456",
  "allowed_files_ok": true,
  "single_database_ok": true,
  "implicit_mock_found": false,
  "clean_before_write": true,
  "transactional_upsert": true,
  "bootstrap_idempotent": true,
  "market_review_passed": true,
  "stock_analysis_passed": true,
  "no_llm_analysis_passed": true,
  "fact_citations_passed": true,
  "analysis_to_backtest_passed": true,
  "backtest_canonical_store": true,
  "backtest_no_lookahead": true,
  "backtest_astock_rules": true,
  "commands": [
    ".venv/bin/pytest tests/test_astock_single_database.py -v",
    ".venv/bin/python scripts/migrate_astock_single_db.py --dry-run"
  ],
  "results": {
    "tests_passed": 42,
    "tests_failed": 0
  },
  "blocking_issues": []
}
```

Controller 合并条件：

```text
Acceptance Task == done
acceptance.json 存在
verdict == PASS
head_sha == 当前阶段分支 HEAD
allowed_files_ok == true
blocking_issues 为空
git diff --check 通过
```

## 42. Diff-only Review

生成：

```bash
BASE_SHA="<阶段开始SHA>"
HEAD_SHA="$(git rev-parse HEAD)"
OUT="$XG_REPO/.hermes-workflow/review/pr2"

mkdir -p "$OUT"

git diff --stat "$BASE_SHA..$HEAD_SHA" > "$OUT/diff-stat.txt"
git diff --name-only "$BASE_SHA..$HEAD_SHA" > "$OUT/changed-files.txt"
git diff --unified=40 "$BASE_SHA..$HEAD_SHA" > "$OUT/changes.diff"
git diff --check "$BASE_SHA..$HEAD_SHA" > "$OUT/diff-check.txt"
```

Review 输入只包含：

```text
Task Contract
diff-stat.txt
changed-files.txt
changes.diff
测试摘要
implementation.json
```

`changes.diff` 超过 80,000 字符时按文件拆分，不一次发送给模型。

## 43. 测试日志压缩

```bash
set -o pipefail
LOG="$XG_REPO/.hermes-workflow/logs/pr2-tests.log"

.venv/bin/pytest tests/test_astock_single_database.py -v \
  >"$LOG" 2>&1
CODE=$?

if [ "$CODE" -ne 0 ]; then
  tail -n 120 "$LOG"
  exit "$CODE"
fi

grep -E "passed|failed|error" "$LOG" | tail -n 10
```

成功 Evidence 只保存：

```json
{
  "command": ".venv/bin/pytest ...",
  "exit_code": 0,
  "passed": 42,
  "failed": 0,
  "duration_seconds": 18.4
}
```

---

# 第九部分：Cron Controller 与 Watchdog

## 44. Cron 设计原则

Cron 不直接调用模型，只执行确定性脚本：

```text
Cron
  ↓
Controller Script
  ├── 读取 Kanban JSON
  ├── 检查 Evidence
  ├── 检查 Git SHA
  ├── 创建缺失任务
  ├── 合并通过阶段
  └── 创建或释放下一阶段（包括 PR-5A、PR-5B）
        ↓
Gateway Kanban Dispatcher
        ↓
对应 Profile Worker
```

## 45. Controller 文件

创建：

```text
~/.hermes/scripts/xg_recovery_tick.py
```

职责：

1. 获取文件锁；
2. 确认仓库、Board、Gateway 和集成 Worktree；
3. 使用 CLI `--json` 读取任务；
4. 检测当前八阶段（含 PR-5A、PR-5B）；
5. 幂等创建缺失任务；
6. 校验 Acceptance JSON；
7. 校验 `head_sha` 与当前 Integration Branch HEAD；
8. 校验文件白名单；
9. 确认 Worktree 干净；
10. 允许 Kanban 依赖自动释放下一阶段；
11. 必要时执行一次 Dispatcher Nudge；
12. 无变化时空 stdout。

默认模式下 Controller **不执行阶段分支合并**，因为所有阶段按顺序提交到同一个 Integration Branch。

禁止 Controller：

```text
修改生产代码
修改 Acceptance Verdict
自动解除 blocked
自动强制解决冲突
直接写 Hermes kanban.db
跳过阶段
无限重试
在 Worktree 不干净时推进
```

## 46. Controller 伪代码

```python
def tick():
    with process_lock():
        ensure_repo_board_gateway_and_worktree()
        tasks = kanban_list_json()
        phase = detect_phase(tasks)

        if phase.has_blocked_tasks:
            report_once(phase.blocked_summary)
            return

        if phase.tasks_missing:
            create_missing_tasks_idempotently(phase)
            dispatch_once(max_tasks=1)
            return

        if phase.acceptance_done:
            evidence = load_acceptance(phase)
            validate_evidence_schema(evidence)
            validate_git_sha(evidence)
            validate_allowed_files(evidence)
            validate_no_blockers(evidence)
            validate_worktree_clean()
            record_phase_completed(phase)
            dispatch_once(max_tasks=1)
            report_phase_advanced()
            return

        return  # empty stdout
```

下一阶段任务已经通过 Parent 依赖预创建时，父任务完成后会自动进入可执行状态；Controller 只做 Evidence 复核和 Dispatcher Nudge。


## 47. Watchdog

创建：

```text
~/.hermes/scripts/xg_recovery_watchdog.py
```

仅在以下情况输出：

```text
Task blocked
Worker crashed
Task 超时
长时间无 heartbeat
Evidence 缺失
Git SHA 不匹配
Worktree 有未提交文件
合并冲突
Gateway 停止
Codex 使用量异常升高
PR-5A 市场复盘或分析 Evidence 缺失
复盘/分析使用 mock 或非 Canonical DB
LLM 解释缺少事实引用
PR-5B 回测 Evidence 缺失
回测直接调用 Provider 或读取非 Canonical DB
```

正常情况空 stdout。

## 48. 创建 No-Agent Cron

```bash
hermes -p xg-orchestrator-ds cron create "every 5m" \
  --no-agent \
  --script xg_recovery_tick.py \
  --deliver local \
  --name "xg-dev-recovery-controller"

hermes -p xg-orchestrator-ds cron create "every 15m" \
  --no-agent \
  --script xg_recovery_watchdog.py \
  --deliver local \
  --name "xg-dev-recovery-watchdog"
```

脚本必须位于：

```text
~/.hermes/scripts/
```

No-Agent 正常空 stdout 不投递消息，不调用模型，不产生模型 Token。

## 49. 启动唯一 Gateway

```bash
hermes -p xg-orchestrator-ds gateway install
hermes -p xg-orchestrator-ds gateway start
```

检查：

```bash
hermes -p xg-orchestrator-ds gateway status
hermes -p xg-orchestrator-ds cron status
hermes -p xg-orchestrator-ds cron list
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" stats
```

本项目只启动 `xg-orchestrator-ds` Gateway。其他 Profile 由 Dispatcher 作为 Worker 进程启动，不单独常驻 Gateway。

不要同时运行旧的独立 `hermes kanban daemon`。

## 50. 手动冒烟

```bash
hermes -p xg-orchestrator-ds cron run xg-dev-recovery-controller
hermes -p xg-orchestrator-ds cron tick

hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" dispatch \
  --max 1 \
  --failure-limit 2 \
  --json
```

观察：

```bash
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" watch
```

---

# 第十部分：测试、发布门禁和最终验收

## 51. 单元测试

必须覆盖：

```text
local-release Provider 依赖
Setup status
Bootstrap
Provider 独立健康检查
默认无 mock
单一数据库
数据 lineage
首次 Dashboard
数据库重启持久化
核心清洗先于写入
Bootstrap 单标的事务
Bootstrap 幂等
市场复盘 Schema、宽度、情绪、板块和涨跌停
市场复盘持久化和幂等
个股结构化事实和数据 lineage
无 LLM 模式
分析事实引用和数据截止时间
复盘 → 分析 → 回测串联
Canonical Backtest 数据源
A 股交易规则和无未来函数
回测可复现性
回测结果重启持久化
backend.json 不覆盖 local-release
不存在 SQLite/DuckDB 业务双写
```

## 52. 集成测试

离线链路：

```text
Fixture Provider
→ Router
→ Loader
→ Quality Gate
→ DuckDB
→ API
→ Web
```

真实网络测试单独标记：

```python
@pytest.mark.integration
@pytest.mark.live_provider
```

执行：

```bash
.venv/bin/pytest -m live_provider -v
```

## 53. 浏览器测试

覆盖：

```text
空库 Dashboard
进入 Data Hub
快速初始化
任务进度
真实行情展示
K 线页面
市场复盘页面
个股分析页面
无 LLM 降级
复盘 → 分析 → 回测
Canonical Backtest
回测结果持久化
重启持久化
Provider 超时降级
无隐式 mock
无无限 Loading
```

## 54. 最终 Offline 验证

```bash
cd "$XG_REPO/.worktrees/xg-integration"

./scripts/setup_local.sh
.venv/bin/python scripts/astock_doctor.py

.venv/bin/pytest \
  tests/test_astock_local_release_dependencies.py \
  tests/test_astock_local_startup.py \
  tests/test_astock_setup_status.py \
  tests/test_astock_setup_bootstrap.py \
  tests/test_astock_bootstrap_idempotency.py \
  tests/test_astock_transactional_ingest.py \
  tests/test_astock_provider_health_isolation.py \
  tests/test_astock_no_implicit_mock.py \
  tests/test_astock_single_database.py \
  tests/test_astock_market_review_schema.py \
  tests/test_astock_market_breadth.py \
  tests/test_astock_market_sentiment.py \
  tests/test_astock_sector_performance.py \
  tests/test_astock_market_review_api.py \
  tests/test_astock_market_review_persistence.py \
  tests/test_astock_stock_analysis_facts.py \
  tests/test_astock_stock_analysis_api.py \
  tests/test_astock_stock_analysis_no_llm.py \
  tests/test_astock_stock_analysis_lineage.py \
  tests/test_astock_backtest_canonical_store.py \
  tests/test_astock_backtest_api.py \
  tests/test_astock_backtest_no_lookahead.py \
  tests/test_astock_backtest_astock_rules.py \
  tests/test_astock_backtest_reproducibility.py \
  -v

./scripts/verify_astock_data_loop.sh

.venv/bin/pytest -m browser -v

git diff --check
```

额外检查：

```bash
find . -name "*.duckdb" \
  -not -path "./.venv/*" \
  -not -path "./.worktrees/*/.venv/*"

grep -R "sqlite3.connect" tradingagents/astock || true
grep -R "ASTOCK_MOCK_DATA_ENABLED.*true" tradingagents scripts || true
```

## 55. Live Provider Evidence

至少验证：

```text
600519.SH
最近至少 250 条日 K
Provider 非 mock
写入 Canonical DuckDB
重启后仍可读取
Dashboard 正确展示
市场复盘成功并持久化
600519.SH 综合分析成功
无 LLM 模式通过
分析事实引用通过
复盘和分析结果重启后仍可读取
Canonical Backtest 成功
A 股交易规则和无未来函数通过
回测结果重启后仍可读取
```

Evidence：

```json
{
  "symbol": "600519.SH",
  "provider": "mootdx",
  "rows_fetched": 250,
  "rows_written": 250,
  "mock": false,
  "database": "~/.tradingagents/astock/astock.duckdb",
  "restart_read_passed": true,
  "market_review_completed": true,
  "market_review_restart_read_passed": true,
  "stock_analysis_completed": true,
  "stock_analysis_no_llm_passed": true,
  "stock_analysis_fact_citations_passed": true,
  "stock_analysis_restart_read_passed": true,
  "analysis_to_backtest_passed": true,
  "backtest_completed": true,
  "backtest_no_lookahead_passed": true,
  "backtest_astock_rules_passed": true,
  "backtest_restart_read_passed": true,
  "verdict": "PASS"
}
```

Provider 名仅为示例，实际写入成功的真实 Provider 为准。

## 56. Final Codex Acceptance

Codex 只读取：

```text
Final Task Contract
八阶段 acceptance.json（含 PR-5A、PR-5B）
最终测试摘要
数据库检查结果
Git diff stat
关键 Diff
Live Provider Evidence
Browser Evidence
```

必须检查：

```text
八阶段全部 PASS（含 PR-5A、PR-5B）
集成分支包含八阶段提交
没有第二 K 线 DuckDB
没有 SQLite/DuckDB 业务双写
默认没有 mock
空库初始化链路通过
Dashboard 显示真实数据
核心清洗在写入前执行
Bootstrap 事务与幂等通过
市场复盘使用 Canonical DuckDB
市场复盘、宽度、情绪和板块 Evidence 通过
个股分析事实来自 Canonical DuckDB
无 LLM 模式通过
模型解释引用事实 ID
复盘 → 分析 → 回测串联通过
回测使用 Canonical DuckDB
回测无未来函数
回测处理基础 A 股交易规则
回测记录策略版本、代码 SHA、参数和数据快照
回测结果持久化和重启读取通过
Browser Test 通过
Live Provider 通过
```

最终：

```json
{
  "release": "0.3.3",
  "verdict": "PASS",
  "blocking_issues": []
}
```

Controller 验证后才创建：

```text
READY-FOR-RELEASE
```

---

# 第十一部分：失败处理、熔断和回滚

## 57. 重试预算

| 环节 | 最大重试 |
|---|---:|
| DeepSeek 小补丁 | 1 次定向修正 |
| Agnes 主实现 | 1 次定向修正，API 临时错误另计 |
| Agnes Review | 1 次重新 Review |
| Codex Gate | 1 次 |
| Codex Acceptance | 1 次 |
| Dispatcher Spawn | 2 次后自动 Block |
| 相同逻辑失败 | 第二次后人工介入 |

## 58. 禁止自动跨模型 Fallback

禁止：

```text
Agnes 失败后静默切 DeepSeek 继续改代码
Codex 验收失败后切 Agnes 宣告 PASS
DeepSeek 小补丁失败后切 Codex 大范围重构
```

正确流程：

```text
临时 API 错误
→ schedule/ready
→ 稍后重试同一 Profile

能力或合同问题
→ kanban_block
→ 人工修正合同或显式重新分配

第二次相同失败
→ BLOCKED
```

## 59. 工程熔断条件

出现任一情况立即停止当前任务：

1. 单任务修改超过 8 个生产文件；
2. 修改白名单外目录；
3. 引入第二数据库；
4. 用 mock 掩盖 Provider 失败；
5. 删除已有真实数据；
6. 跳过质量检查或先写库后清洗；
7. 两次相同失败；
8. 测试通过但首次启动仍为空白；
9. 页面错误被静默捕获；
10. API 返回 200 但没有数据状态；
11. 引入 SQLite/DuckDB 业务双写；
12. Acceptance SHA 与分支 HEAD 不一致；
13. Controller 出现合并冲突；
14. Codex 调用占比长期超过 12%；
15. 回测直接调用 Provider；
16. 回测读取非 Canonical DuckDB；
17. Bootstrap 重复执行产生重复主键；
18. 市场复盘使用 mock 或错误交易日；
19. 市场情绪由 LLM 直接决定而非确定性状态机；
20. 个股分析数据不足仍输出确定性多空结论；
21. LLM 解释没有关联事实 ID；
22. 无 LLM 时整个分析功能不可用；
23. 复盘、分析结果未持久化；
24. 回测结果未持久化；
25. 回测存在未来函数；
26. 回测未处理基础 A 股交易规则。

## 60. 暂停自动化

```bash
hermes -p xg-orchestrator-ds cron list
hermes -p xg-orchestrator-ds cron pause xg-dev-recovery-controller
hermes -p xg-orchestrator-ds cron pause xg-dev-recovery-watchdog
hermes -p xg-orchestrator-ds gateway stop
```

## 61. 回滚 Profile

删除新 Profile 前先导出：

```bash
for p in \
  xg-orchestrator-ds \
  xg-patch-ds \
  xg-implement-agnes \
  xg-review-agnes \
  xg-gate-codex \
  xg-accept-codex
do
  hermes profile export "$p" -o "$HOME/$p-backup.tar.gz"
done
```

删除：

```bash
hermes profile delete xg-orchestrator-ds
hermes profile delete xg-patch-ds
hermes profile delete xg-implement-agnes
hermes profile delete xg-review-agnes
hermes profile delete xg-gate-codex
hermes profile delete xg-accept-codex
```

不要删除：

```text
原 default Profile
原 Hermes Skills
原 Codex 认证备份
项目备份 Tag
Canonical DuckDB 备份
旧数据库迁移前备份
```

---


## 61A. Hermes 主控启动指令

完成 API Key、Profile 和路径配置后，在仓库外层终端执行：

```bash
export XG_REPO="/Users/<你的用户名>/Projects/k_TradingAgents"
cd "$XG_REPO"

hermes -p xg-orchestrator-ds chat
```

向 Orchestrator 提交以下主控指令：

```text
你是 TradingAgents xg_dev V0.3.3 修复实施总控。

唯一方案来源：
docs/TradingAgents_xg_dev_修复与Hermes低Token自动化实施方案_V1.6.1.md

目标：
在 fix/xg-dev-data-loop-v033 集成分支和单一 Integration Worktree 中，
按以下顺序完成八阶段：
PR-1 → PR-2 → PR-3 → PR-4 → PR-5 → PR-5A → PR-5B → PR-6。

最终产品闭环：
安装
→ Provider 可用
→ 首次真实数据拉取
→ 标准化和质量检查
→ 唯一 DuckDB 入库
→ Dashboard/K 线
→ 市场复盘
→ 个股综合分析
→ A 股规则回测
→ 结果持久化
→ 重启验证。

立即执行预检，但不要直接修改生产代码：

1. 读取完整 V1.5 文档。
2. 检查 Hermes 当前版本支持的 profile、kanban、cron、gateway 命令。
3. 检查六个 Profiles 是否存在及 config check 是否通过。
4. 检查 DeepSeek、Agnes、Codex 是否可调用。
5. 检查 XG_REPO、xg_dev、Integration Branch 和 Worktree。
6. 创建或校验 .hermes-workflow 目录。
7. 根据 V1.5 生成并冻结所有 Task Contracts、Manifest 和 Evidence Schema。
8. 初始化 tradingagents-xgdev Kanban Board。
9. 按依赖和幂等键创建八阶段任务链。
10. 检查 No-Agent Controller 与 Watchdog 脚本。
11. 创建 Cron，但首次保持暂停状态。
12. 输出 preflight-report.json。

只有以下条件全部通过才允许启动 PR-1：
- 配置检查通过；
- 三类模型路由通过；
- Worktree 干净；
- Kanban 幂等测试通过；
- Controller dry-run 通过；
- Evidence Schema 验证通过。

执行约束：
- Hermes 是唯一正式状态推进者；
- 一次只运行一个 Implementation Task；
- DeepSeek 负责调度、压缩和小补丁；
- Agnes 负责主要实现和普通 Review；
- Codex 只负责高风险 Gate 和独立 Acceptance；
- Cron 不调用 LLM；
- 禁止自动跨模型 fallback；
- 禁止隐式 mock；
- 禁止第二业务数据库；
- 第二次相同失败立即 BLOCKED；
- Worker 必须调用 kanban_complete 或 kanban_block；
- 模型的自然语言“完成”不构成验收；
- 只认可测试、Git SHA 和 Evidence JSON。

预检结束后：
- 如果失败，阻塞并给出可执行修复列表；
- 如果通过，解除 Controller Cron 暂停，创建并派发 PR-1；
- 不得跳过任何阶段；
- PR-5A 未通过时不得释放 PR-5B；
- PR-5B 未通过时不得释放 PR-6；
- Final Codex Acceptance 和机器门禁未通过时不得标记 READY-FOR-RELEASE。
```

预检报告建议保存：

```text
.hermes-workflow/evidence/preflight/preflight-report.json
```

最低结构：

```json
{
  "schema_version": "1.0",
  "document_version": "V1.5",
  "repository": "k_TradingAgents",
  "source_branch": "xg_dev",
  "integration_branch": "fix/xg-dev-data-loop-v033",
  "profiles_ok": true,
  "models_ok": true,
  "worktree_clean": true,
  "kanban_ok": true,
  "controller_dry_run_ok": true,
  "evidence_schema_ok": true,
  "blocking_issues": [],
  "verdict": "PASS"
}
```


# 第十二部分：完整执行顺序

## 62. 首次部署顺序

```text
01. 将 V1.5 文档放入 docs/
02. 定义 XG_REPO 等环境变量
03. 备份 Hermes 与 Git 状态
04. 检查 Hermes 版本和配置
05. 探测 DeepSeek、Agnes、Codex 模型
06. 创建六个 Profiles
07. 配置 DeepSeek
08. 配置 Agnes Named Custom Provider
09. 配置 Codex OAuth/API
10. 写入各 Profile SOUL.md
11. 设置低 Token 参数
12. 执行 config check 和 doctor
13. 创建项目 .hermes.md
14. 创建低 Token Context 包
15. 记录 prompt-size 基线
16. 冻结 xg_dev 并创建备份 Tag
17. 创建 Integration Branch 与 Worktree
18. 初始化 Kanban Board
19. 写 PR-1 Contracts
20. 创建 Controller 和 Watchdog
21. 创建 No-Agent Cron
22. 启动唯一 Gateway
23. 执行 Profile 冒烟测试
24. 执行 Kanban 路由测试
25. 创建 PR-1 任务链
26. PR-1 Acceptance 后记录阶段 SHA 并释放 PR-2
27. 在同一 Integration Branch 依次执行 PR-2～PR-5
28. 执行 PR-5A 市场复盘与个股综合分析
29. 执行 PR-5B Canonical Backtest
30. 执行 PR-6 扩展质量与发布门禁
31. 执行 Offline 验收
32. 执行 Live Provider 验收
33. 执行 Browser 验收
34. Codex Final Acceptance
35. Controller 标记 READY-FOR-RELEASE
```

## 63. 日常监控命令

```bash
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" list
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" stats
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" watch

hermes -p xg-orchestrator-ds cron status
hermes -p xg-orchestrator-ds cron runs xg-dev-recovery-controller --limit 20

hermes -p xg-orchestrator-ds logs gateway --since 1h
hermes -p xg-orchestrator-ds logs errors --since 1h

hermes dashboard
```

查看任务：

```bash
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" show <TASK_ID> --json
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" tail <TASK_ID>
hermes -p xg-orchestrator-ds kanban --board "$XG_BOARD" context <TASK_ID>
```

## 64. 使用量告警

| 指标 | 告警阈值 |
|---|---:|
| Codex 调用占比 | > 12% |
| 单任务逻辑修正 | > 1 次 |
| 单任务生产文件 | > 8 |
| 同时运行实现任务 | > 1 |
| Review Diff | > 80K 字符 |
| 相同错误 | 第二次出现 |
| Prompt 固定成本 | 比基线增加 > 20% |
| 任务无 Heartbeat | 接近 1 小时 |

Codex 过高时检查：

```text
是否把普通 Review 交给 Codex
是否每次 Cron 调用 Codex
是否重复 Gate
是否让 Codex 扫描完整仓库
是否传入完整成功日志
```

---

# 65. 最终策略摘要

```yaml
project:
  branch: xg_dev
  integration_branch: fix/xg-dev-data-loop-v033
  default_worktree: .worktrees/xg-integration
  release: 0.3.3
  stages: [PR-1, PR-2, PR-3, PR-4, PR-5, PR-5A, PR-5B, PR-6]

out_of_box:
  setup_script: scripts/setup_local.sh
  start_script: scripts/start_local.sh
  first_run_redirect: /data_hub?first_run=1

business_database:
  engine: duckdb
  path: ~/.tradingagents/astock/astock.duckdb
  count: 1

workflow:
  state_store: hermes_kanban_sqlite
  auto_decompose: false
  max_parallel_implementation: 1
  phase_branch_merge_required: false

models:
  orchestrator: deepseek-v4-flash
  small_patch: deepseek-v4-flash
  main_implementation: agnes
  normal_review: agnes
  high_risk_gate: codex
  final_acceptance: codex

cron:
  controller: no_agent
  interval: 5m
  watchdog: no_agent
  watchdog_interval: 15m

cost_control:
  diff_only_review: true
  compact_success_logs: true
  fixed_prompt_prefix: true
  auto_title: false
  cross_role_fallback: false
  same_failure_limit: 2

release_gate:
  machine_evidence_required: true
  single_duckdb_required: true
  implicit_mock_forbidden: true
  browser_required: true
  live_provider_required: true
  clean_before_write_required: true
  transactional_ingest_required: true
  bootstrap_idempotency_required: true
  market_review_required: true
  stock_analysis_required: true
  no_llm_analysis_required: true
  fact_citation_required: true
  analysis_to_backtest_flow_required: true
  canonical_backtest_required: true
  astock_rules_required: true
  no_lookahead_required: true
  backtest_persistence_required: true
  codex_pass_required: true
```

最重要的工程原则：

> DeepSeek 承担高频低风险工作，Agnes 承担主要实现，Codex 只参与高风险门禁和独立验收；Cron、测试、Git、数据库检查和阶段推进尽可能使用无模型脚本。

最重要的产品门禁：

> 在全新环境和空数据库条件下，用户必须能够通过一键安装、一键启动和 Web 快速初始化，完成真实数据拉取、核心清洗、唯一 DuckDB 入库、行情展示、市场复盘、个股综合分析和 Canonical Backtest；复盘、分析和回测结果重启后仍须存在。该条件未达到前，不继续开发外围模块。

---

# 66. V1.5 最终开箱即用验收场景

## 66.1 全新环境

```bash
export HOME="$(mktemp -d)"

git clone <repository-url>
cd k_TradingAgents
git switch fix/xg-dev-data-loop-v033

./scripts/setup_local.sh
./scripts/start_local.sh
```

## 66.2 浏览器完整路径

```text
浏览器自动打开
→ 自动进入首次设置
→ 至少一个 Provider available
→ 点击快速初始化
→ 至少 4 个指数和 1 个股票成功
→ 核心清洗先于写库
→ 单标的事务与幂等验证通过
→ 数据写入唯一 DuckDB
→ Dashboard 显示真实行情
→ 打开 600519.SH K 线
→ 生成当日市场复盘
→ 查看市场宽度、情绪、板块和强弱标的
→ 从强势板块进入 600519.SH 个股分析
→ 查看技术、基本面、估值、资金、消息、板块和风险
→ 关闭 LLM 后结构化分析仍可使用
→ 从分析页进入 MA5/MA20 回测
→ 回测处理 A 股规则且无未来函数
→ 回测写入 backtest_runs / backtest_trades
→ 停止并重启服务
→ 行情、复盘、分析和回测结果仍存在
```

## 66.3 机器门禁

```text
Provider source != mock
K 线行数 >= 250
重复主键 == 0
隔离数据有统计
Canonical DuckDB 数量 == 1
Dashboard source != mock
Kline source != mock
Market Review source != mock
Market Review 状态 == completed
Market Review restart_read == PASS
Market Review major_indices_success >= 5
Market Review breadth_valid == true
Market Review sentiment_reproducible == true
Stock Analysis facts_from_duckdb == true
Stock Analysis data_state == ready
Stock Analysis minimum_kline_rows >= 120
Stock Analysis no_llm_mode == PASS
Stock Analysis restart_read == PASS
Model Interpretation fact_citations == PASS
Model Interpretation data_cutoff_recorded == true
Review → Analysis → Backtest == PASS
Backtest 读取 Canonical DuckDB
Backtest no_lookahead == PASS
Backtest A-share rules == PASS
Backtest 状态 == completed
Backtest 重启读取 == PASS
Browser 无无限 Loading
```

唯一允许发布的最终状态：

```text
0.3.3 READY-FOR-RELEASE
```

---

# 67. 官方依据与版本注意

本方案的 Hermes 命令和配置结构依据 2026-07-22 可访问的官方文档整理，包括：

- Hermes Agent Profiles；
- Hermes Agent Kanban；
- Hermes Agent Cron；
- Hermes Agent Configuration；
- Hermes Agent AI Providers；
- Hermes Agent CLI Commands；
- DeepSeek API Models；
- OpenAI Models 与 Codex 官方发布说明。

Hermes、DeepSeek 和 Codex 均可能继续更新。正式执行前必须再次运行：

```bash
hermes --version
hermes config check
hermes doctor
hermes kanban --help
hermes cron --help
hermes profile --help
```

模型 ID 必须以账户实时 `/models` 返回或 `hermes model` 交互列表为准。


---

本文档已在分支 `fix/xg-dev-data-loop-v033` 上以 V1.6.1 版本实施。

## V1.6.1 实施记录

### 实施时间
2026-07-23

### 核心变更

从 V1.6 → V1.6.1：

- 移除 TushareProvider / Tushare Token 依赖
- 新增 CninfoProvider（巨潮资讯）公开查询 + 本地导入双模式
- 新增 cninfo_importer.py 本地 Manifest 导入
- 新增 derived_metrics.py 本地派生指标（PE派生、量价资金代理）
- Provider 状态替换：`missing_token`/`permission_required`/`insufficient_points`
  → `access_restricted`/`manual_import_required`
- 新增 `source_kind` 字段（online_api/public_web/local_import/derived）
- 新增 `ADJUSTMENT_FACTOR`、`CORPORATE_EVENTS` Capability
- provider_policy.yaml 改为 Community 模式（四 Provider 栈）
- pyproject.toml local-release 包含全部四 Provider 依赖
- 新增 4 个表：`announcement_documents` / `corporate_events` / `provider_field_lineage` 等
- 新增 4 个专用测试文件：cninfo_provider / cninfo_local_import / akshare_schema_drift / capital_flow_proxy_semantics
- Doctor 新增 `--provider-capabilities` 标记

### 当前提交链

```text
2ecb1d6 V1.6.1 补全 — 巨潮本地导入/公告表/专用测试
0526a35 V1.6.1 社区公共数据栈实施 — 去Tushare+Cninfo+派生
8291cdf fix: Codex Acceptance P1/P2
abadf19 chore: 忽略最终验收证据
fcf6534 V1.6 Doctor
5343c28 V1.6 Provider 包装器
d84ec95 V1.6 Capability 路由
f563925 V1.5 连板/板块/分析
(PR-1~6: a42d5a1...6c7c137)
```

### 验收结果

```text
测试:  242 项 ✅ ALL PASS
验收:  5 步  ✅ ALL PASS
Codex: ✅ 已运行
```

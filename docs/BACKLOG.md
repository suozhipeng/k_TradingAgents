# Backlog

> 待完成任务清单。历史 backlog 已随文档整合移除。

# TradingAgents-Astock 待开发 Backlog

## 1. 文档目标

本文档整理当前仓库后续最值得推进的需求项，按优先级划分为 P0/P1/P2。需求到模块、测试和 phase 的映射见 `04-development.md`。产品指标、运行指标、告警和 Ops 要求见 `03-operations.mddeployment.md` §8。

## 1.1 当前范围约束（2026-07-08）

当前开发范围明确为：

- 不接入真实券商
- 不接入真实 QMT 订单/委托查询
- 不把当前系统升级为完整自动实盘生产交易系统

在这个范围下，交易执行相关工作的目标是：

- 统一 `research` / `paper` / `managed` / `live-ready` 能力边界
- 保持现有 QMT 路由为 `mock` / `read_only` 语义并避免误导
- 完善投研、回测、模拟盘、工作台和产品化页面收口

以下能力继续视为范围外 / P3：

- 真实券商订单、成交、撤单、拒单、部分成交、券商回报 reconciliation
- 真实 QMT 订单/委托查询
- 默认自动实盘执行
- RBAC / 多用户系统
- SLA 与故障分级

## 1.2 当前建议开发顺序（2026-07-08）

| 顺序 | 优先级 | 项目 | 当前目标 |
|------|------|------|---------|
| 1 | P0 | `BL-001` + `BL-002` | ✅ 已完成 — QMT 能力边界统一，mock/read-only 语义已标注 |
| 2 | P1 | `BL-205` + `BL-201` | ✅ 已完成 — Dashboard 决策摘要 + 卡片五态已闭环 |
| 3 | P1 | `BL-203` + `BL-204` | ✅ 已完成 — 结构化每日复盘 + 批量分析入口已落地 |
| 4 | P1 | `FR-22` ~ `FR-25` | ✅ 已完成 — 4 个模块页面级收口已更新为 done |
| 5 | P2 | `NFR-04/05/07/09/11/14/16/17/19` | ✅ 已完成 — 9 项治理收尾已全部 done |
| 6 | P2 | Code Quality | ✅ 已完成 — 13 处 silent exception swallowing 已修复 |
| — | — | `FR-09` 页面级收口 | ✅ 已完成 — 旧入口 301/302 redirect + legacy_banner + 7 模块 sidebar 收敛 |
| — | — | `FR-07` 受控执行边界 | ✅ 已完成 — RiskGate 全链路 + QMT mock/read-only 固定；真实 broker reconciliation 为 P3 范围外设计决策 |

## 2. P0

### BL-000 建立实盘准入清单

#### 2026-07-08 Live 验证结论

| 验证项 | 结果 | 说明 |
|--------|------|------|
| 离线测试基线 | 1082 passed, 10 skipped | 零失败 |
| Live Provider (akshare) | 7 passed, 1 skipped | 全部 7 个 provider 测试通过；iwencai 需 cookie |
| Live Provider (tencent) | 5/5 ok | order_book/trade_tape/turnover 全部 ok |
| Live Provider (cninfo) | 2/2 ok | announcement_summary/full 全部 ok |
| Live Provider (mootdx) | 4/4 ok | kline/order_book/trade_tape/f10 全部 ok |
| DeepSeek 离线 | 13 passed | 1 skipped (需 API key) |
| Pydantic BT | 39 passed | TEST_PYDANTIC_BT=1 |
| 模块导入 | 26/28 OK | settlement/cli_report 为内部名非独立模块 |
- 已知缺口：2 项 | announcement_* 路由优先级非 akshare（预期行为）

#### 已知缺口详述

1. **`announcement_*` 能力** — 路由优先级为 cninfo → mootdx，测试 facade 仅注册 akshare 导致 error。这是测试场景的预期行为，生产环境 cninfo 适配器可用。
2. **`sector` 已修复** — akshare 适配器已实现 `get_sector_data()`，支持 industry（THS）和 concept（EM）两种模式。

现状：

- 当前系统已经能支撑投研分析、回测、模拟盘和 QMT managed mock/read-only 边界展示
- 但专业金融系统的实盘生产闭环仍缺账户/订单/成交 reconciliation、审计、kill switch、数据质量和组合级风控门槛

目标：

- 建立 `Live Trading Readiness` checklist
- 明确哪些能力属于 `research`、`paper`、`managed`、`live-ready`
- 把实盘准入条件写入状态文档、技术文档和 phase 归档

完成标准：

- 有账户资产、持仓、委托、成交、撤单、拒单、部分成交、券商回报的状态模型要求
- 有 kill switch、最大亏损、最大仓位、最大单笔金额、交易时段、手工确认的硬约束
- 有审计要求：数据快照、AI prompt、模型版本、人工确认、订单回报全链路可追溯
- 文档明确当前系统“可实盘辅助分析”，但“不等于完整自动实盘生产系统”

### BL-001 统一 QMT 能力边界

| 状态 | 备注 |
|------|------|
| ✅ done | QMT capability 标签已注入所有 API 响应（`capability: "managed"`, `note: "mock/read-only"`）；`real=1` 不再触发真实 QMT bridge，`real_connection_check.enabled=false` |

### BL-002 修正 `qmt/orders` 的 mock 语义

| 状态 | 备注 |
|------|------|
| ✅ done | `/qmt/orders` 已收口为 mock account snapshot；`orders` 固定为空兼容字段，UI/文档均不再描述为真实委托列表 |

### BL-003 修正 trade quote / trade state 的能力口径

状态：✅ done（2026-07-10，P0-B1/P0-B2）

现状与结论：

- 默认 Research-only 范围下，`/api/v1/trade/quote` 与其他执行 API 返回 `410 research_only`；研究行情入口为 `/api/v1/market/quote`。
- `/api/v1/market/quote`、龙虎榜、板块、北向、股票归属板块、动量和市场概览统一返回 `source`、`as_of`、`age_seconds`、`is_mock`、`is_stale`。
- `mock` / `synthetic` 明确标记 `is_mock=true`；`cache` / `store` / `fallback` / `duckdb` 超过 TTL 时明确标记 `is_stale=true`。
- `trade/state` 属于兼容模式中的 PaperTrader 路径，非实盘，且不属于默认 Research-only 产品面。

验收证据：

- `tests/test_astock_data_quality_banner.py` 覆盖来源分类、TTL、时区、空字典和非法输入边界。
- 2026-07-10 全量回归：`1136 passed, 10 skipped`。

### BL-004 为专业交易页建立正式归档

现状：

- `trading.html`、`routes_trade.py`、相关测试已进入代码
- Phase 29 已归档至 docs/phase-archive.md

目标：

- ✅ 已达成 — 有 scope、测试、风险说明、commit SHA（Phase 29 已归档至 docs/phase-archive.md）

完成标准：

- ✅ 已达成 — Phase 29 已归档至 docs/phase-archive.md
- 有测试 — ✅ WebUI + API 切片 150 passed
- 有风险说明 — ✅ 实时报价依赖/缓存/持久化
- 有 commit SHA — ✅ `268d326`, `87e5b73`, `1960c65` 等

### BL-200 Web-G0 需求冻结 — 更新 backlog / traceability / product-spec / checklist 文档


| 状态 | 备注 |
|------|------|
| ✅ done | Web-G0 phase 文档已创建，backlog/traceability/spec/checklist 均已更新 |

现状：
- Web 工作台竞品对齐矩阵已确定 P0/P1/P2 分组，但尚未写入 backlog 和 traceability
- 默认入口、能力标签和安全边界需要正式冻结，避免开发中反复改方向

目标：
- 将 DSA / AIS / TA / REF / TDX 矩阵映射到需求 ID，写入 backlog 和 traceability
- 固定 `/dashboard` 为默认首页
- 明确 QMT/miniQMT 默认不是自动实盘
- 明确 TDX 行情链路归属 Data & Ops，不归属 Trading & Execution

完成标准：
- 每个 P0/P1 能力都有需求 ID、模块、phase、验收证据位置
- 文档状态不把 planned 写成 done

### BL-201 Web-P0 首页重构 — dashboard 作为每日工作台

| 状态 | 备注 |
|------|------|
| ✅ done | dashboard.html 已完成 7 区域工作台收口，并补齐核心卡片 loading/empty/error/degraded/stale 处理与决策摘要 |

现状：
- ✅ 当前 `/dashboard` 已成为默认产品首页
- ✅ 第一屏已聚合市场、自选股/决策、任务、报告、告警、板块/龙头、数据健康
- ✅ 快捷操作区已补批量分析入口

目标：
- ✅ 已达成 — 第一屏聚合市场、自选股、持仓、AI 任务、报告、告警和数据健康
- ✅ 已达成 — 交易入口后置为二级动作

完成标准：
- ✅ 首页有市场、自选股/持仓、任务、报告、告警、龙头/板块摘要、数据健康七个区域
- ✅ 所有核心卡片支持 loading、empty、error/degraded/stale 状态
- ✅ 首页不使用 iframe
- ✅ 已补全决策摘要与批量分析入口

### BL-202 默认入口变更 — `/` 重定向到 `/dashboard`

| 状态 | 备注 |
|------|------|
| ✅ done | `/` 已 302 → `/dashboard`，在 `web/__init__.py:119` 实现 |

现状：
- `/` 默认进入交易页，用户还没完成分析、盯盘就被推到下单界面

目标：
- `/` 改为 302 到 `/dashboard`
- `trading.html` 不再作为新用户第一屏

完成标准：
- `/dashboard` 是产品默认入口
- 旧入口保留兼容，但显示迁移提示

### BL-203 DSA-01 每日市场复盘 — 按交易日生成市场回顾

| 状态 | 备注 |
|------|------|
| ✅ done | `/api/v1/daily/review` 已扩展为结构化复盘接口，覆盖指数、板块、涨跌家数、北向、龙虎榜、涨跌幅榜和市场 regime |

现状：
- ✅ 已有按交易日输出的复盘接口
- ✅ 不再只停留在 market summary / dashboard 指数卡片

目标：
- ✅ 已达成 — 可按交易日生成市场复盘，含指数、涨跌家数、板块强弱和市场 regime 摘要

完成标准：
- ✅ 复盘包含 5 大指数、涨跌家数比、板块强弱排序、北向资金、龙虎榜、涨跌幅榜和 regime
- ⏳ 报告归档能力可继续复用现有 reports 流程，但 daily 接口本身已完成

### BL-204 DSA-02 自选股批量分析 — 维护 watchlist 并批量生成 AI 摘要

| 状态 | 备注 |
|------|------|
| ✅ done | dashboard 已新增批量分析入口，直接触发 `/api/v1/watchlist/batch-analyze` 并回填决策卡片 |

现状：
- ✅ watchlist 管理已存在
- ✅ dashboard 已补一键批量分析入口

目标：
- ✅ 已达成 — 用户可维护 watchlist，并批量生成分析结果与评分

完成标准：
- ✅ 有 watchlist 管理或读取入口
- ✅ 批量分析任务可触发，并将结果直接渲染回 dashboard 决策区

### BL-205 DSA-03 决策仪表盘摘要 — 首页展示 buy/hold/sell/research-only 摘要

| 状态 | 备注 |
|------|------|
| ✅ done | dashboard 已展示 buy/hold/sell/research-only 摘要，且 `research_only` 由实际分析结果统计而非推导占位值 |

现状：
- ✅ 首页已有全局决策摘要
- ✅ 已支持 `research_only` 计数并明确 `actionable=false`

目标：
- ✅ 已达成 — 首页展示买入/观望/卖出和 research-only 等级摘要
- ✅ 已达成 — 不直接标成可执行指令

完成标准：
- ✅ 摘要明确标注 `research_only` / `actionable=false`

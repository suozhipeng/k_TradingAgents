# Backlog

> 待完成任务清单。历史 backlog 已随文档整合移除。

# TradingAgents-Astock 待开发 Backlog

## 1. 文档目标

本文档整理当前仓库后续最值得推进的需求项，按优先级划分为 P0/P1/P2。需求到模块、测试和 phase 的映射见 `04-dev/traceability-matrix.md`。产品指标、运行指标、告警和 Ops 要求见 `03-ops/deployment.md` §8。

## 2. P0

### BL-000 建立实盘准入清单

现状：

- 当前系统已经能支撑投研分析、回测、模拟盘和 QMT 受控执行
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

现状：

- QMT 在执行层已存在
- QMT 在 blueprint/provider 口径里仍保留 placeholder 语义

目标：

- 统一 QMT 在 provider、execution、API、状态文档中的能力定义

完成标准：

- blueprint / status / phase / code 口径一致
- 不再同时出现“已完成执行”和“provider 仍占位”冲突

### BL-002 修正 `qmt/orders` 的 mock 语义

现状：

- `/api/v1/qmt/orders` 返回的是 mock/read-only 响应

目标：

- 当前阶段不接入真实 QMT 订单/委托查询；该能力标注为已知问题/远期项
- 保持 `/api/v1/qmt/orders` 为 mock/read-only 响应，并在 API/UI/docs 中明确标注

完成标准：

- endpoint 语义与返回内容一致
- 文档不再误导为真实订单模块
- 真实 QMT 订单/委托查询明确列为暂不接入

### BL-003 修正 trade quote / trade state 的能力口径

现状：

- `trade/quote` 使用 EastMoney push2 实时报价 + Sina 降级 + 60s 缓存 — ✅ **已真实**
- `trade/state` 使用 PaperTrader 状态 + 实时报价估值 — ✅ **明确为 Paper Trading 路径**

目标：

- ✅ 已达成 — trade/quote 是实时数据（EastMoney → Sina → 缓存三级降级）
- trade/state 属于 Paper Trading，非实盘，文档已写明

完成标准：

- endpoint 语义与返回内容一致 — ✅ trade/quote 返回实时数据
- 用户不会把 mock 报价误认为真实交易报价 — ✅ trade/quote 已标注 source: "live"|"cache"；trade/state 通过 PaperTrader 路径

### BL-004 为专业交易页建立正式归档

现状：

- `trading.html`、`routes_trade.py`、相关测试已进入代码
- 已建立独立 phase 归档 `_archived/phase-29-trading-page.md`

目标：

- ✅ 已达成 — 有 scope、测试、风险说明、commit SHA（Phase 29 已归档至 `_archived/`）

完成标准：

- ✅ 已达成 — 有 scope — `_archived/phase-29-trading-page.md`（已归档至 `_archived/`）
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
| 🔶 partial | dashboard.html 已有 7 个区域骨架，但非所有卡片实现五态；Web-P0 需深化完成 |

现状：
- `/dashboard` 更像系统指标页，不像用户每日打开的工作台
- 当前首页缺少市场摘要、自选股/持仓、任务、报告、告警和数据健康聚合

目标：
- 重做 `/dashboard`，第一屏聚合市场、自选股、持仓、AI 任务、报告、告警和数据健康
- 交易入口后置为二级动作

完成标准：
- 首页有市场、自选股/持仓、任务、报告、告警、龙头/板块摘要、数据健康七个区域
- 所有卡片支持 loading、empty、error/degraded 状态
- 首页不使用 iframe
- 桌面 1366px、1440px、1920px 下无遮挡或横向溢出

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
| 🔶 partial | 市场摘要 API (market/summary) + dashboard 指数卡片已存在，但缺少结构化交易日回顾报告 |

现状：
- 无每日市场复盘能力
- 用户需要手动查看指数、涨跌家数和板块

目标：
- 可按交易日生成市场复盘，含指数、涨跌家数、板块强弱和风险摘要

完成标准：
- 复盘包含主要指数涨跌幅、涨跌家数比、板块强弱排序和风险标注
- 复盘结果可归档为报告

### BL-204 DSA-02 自选股批量分析 — 维护 watchlist 并批量生成 AI 摘要

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 有自选股异动卡片，PaperTrader 维护 watchlist，但缺少批量 AI 分析入口 |

现状：
- 自选股管理不完整，缺少批量 AI 分析入口

目标：
- 用户可维护 watchlist，并批量生成 AI 摘要和评分

完成标准：
- 有 watchlist 管理或读取入口
- 批量分析任务可触发、查看进度和结果

### BL-205 DSA-03 决策仪表盘摘要 — 首页展示 buy/hold/sell/research-only 摘要

| 状态 | 备注 |
|------|------|
| 🔶 partial | dashboard 展示汇总数据卡片（跟踪股票数/回测数/模拟盘净值/持仓数），但缺少 buy/hold/sell/research-only 决策摘要 |

现状：
- 首页缺少决策摘要，用户不知道 AI 对自选股/持仓的整体判断

目标：
- 首页展示买入/观望/卖出或 research-only 等级摘要
- 不得直接标成可执行指令

完成标准：
- 摘要明确标注 `research_only` / `actionable=false`

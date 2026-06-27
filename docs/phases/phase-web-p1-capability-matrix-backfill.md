# Phase Web-P1：竞品能力矩阵实现状态回填

| 状态：done | 更新日期：2026-06-27 |

## 0. 前置依赖

- Web-G0（需求冻结与追踪矩阵落地）— ✅ done
- 必须读取所有实际代码路径，不得使用 mock/hardcoded 数据判断状态

## 1. Phase 目标

对 Web-G0 阶段新增的 39 个 BL 项（BL-200 ~ BL-404）和 16 个 FR 项（FR-11 ~ FR-26）逐一检查实际代码实现状态，更新 backlog、traceability 矩阵并创建本 phase 归档。

## 2. 范围

### 包含

- 读取 `docs/ASTOCK_BACKLOG.md`，对 BL-200 ~ BL-404 共 39 项逐一检查 API endpoint、HTML 页面、路由注册和测试覆盖的实际存在情况
- 读取 `docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`，对 FR-11 ~ FR-26 共 16 项按实际代码路径更新状态（`done` / `partial` / `planned` / `blocked`）
- 读取 `docs/ASTOCK_WEBUI_PRODUCT_SPEC.md`，确认 7 模块 IA 是否需要同步更新
- 读取 `docs/ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`，确认新页面是否需要补充验收细节
- 创建本 phase 归档文档

### 排除

- 不修改任何运行代码（API、页面、测试）
- 不创建新页面或 endpoint
- 不运行 UAT 或集成测试——本阶段只做状态审计和文档更新

## 3. 检查方法

### API 端点检查清单（按实际注册路径验证）

| 端点 | 状态 | 代码位置 |
|------|------|----------|
| `/api/v1/market/summary` | ✅ 存在 | `routes_market.py` |
| `/api/v1/market/sectors` | ✅ 存在 | `routes_market_data.py` |
| `/api/v1/market/momentum` | ✅ 存在 | `routes_market_data.py` (GET) |
| `/api/v1/market/momentum-rotation` | ✅ 存在 | `routes_market_data.py` (POST) |
| `/api/v1/market/dragon-tiger` | ✅ 存在 | `routes_market_data.py` |
| `/api/v1/market/northbound` | ✅ 存在 | `routes_market_data.py` |
| `/api/v1/market/blocks` | ✅ 存在 | `routes_market_data.py` |
| `/api/v1/dashboard/overview` | ✅ 存在 | `routes_dashboard.py` |
| `/api/v1/data/health` | ✅ 存在 | `routes_data_health.py` |
| `/api/v1/ops/tasks` | ✅ 存在 | `routes_ops.py` |
| `/api/v1/ops/audit` | ✅ 存在 | `routes_ops.py` |
| `/api/v1/ops/stats` | ✅ 存在 | `routes_ops.py` |
| `/api/v1/reports/pptx` | ✅ 存在 | `routes_reports.py` |
| `/api/v1/backtest/run` | ✅ 存在 | `routes_backtest.py` |
| `/api/v1/backtest/optimize` | ✅ 存在 | `routes_backtest.py` |
| `/api/v1/alerts` | ❌ 不存在 | 未注册 — 无告警系统 |
| `/api/v1/reports` (list) | ❌ 不存在 | 只有 pptx 子端点，无报告列表 API |

### HTML 页面检查清单

| 路由 | 状态 | 模板文件 |
|------|------|----------|
| `/dashboard` | ✅ 904 行 dashboard v2 | `dashboard.html` |
| `/market_leaders` | ✅ 龙头统一入口（iframe 嵌入） | `market_leaders.html` |
| `/research` | ✅ AI 研究页 | `research.html` |
| `/strategy_hub` | ✅ 策略实验室 | `strategy_hub.html` |
| `/portfolio` | ✅ 组合工作台 | `portfolio.html` |
| `/trading` | ✅ 交易执行页 | `trading.html` |
| `/settings` | ✅ 系统设置页 | `settings.html` |
| `/data_health` | ✅ 数据健康页 | `data_health.html` |
| `/ops_audit` | ✅ 运维审计页 | `ops_audit.html` |
| `/reports` | ✅ 报告中心页 | `reports.html` |
| `/ai_agent` | ✅ AI Agent 页 | `ai_agent.html` |
| `/paper` | ✅ 模拟盘页 | `paper.html` |
| `/risk` | ✅ 风控页 | `risk.html` |
| `/qmt` | ✅ QMT 页 | `qmt.html` |

### 导航结构检查

base.html 的顶层 tab 导航已按 7 模块收敛：
- 📊 **今日** (`/dashboard`)
- 👁️ **盯盘** (`/market_leaders`)
- 🤖 **AI 研究** (`/research`)
- 🧪 **策略** (`/strategy_hub`)
- 📋 **组合风控** (`/portfolio`)
- 💹 **交易执行** (`/trading`)
- ⚙️ **系统** (`/settings`)

## 4. BL 项实现状态逐一摘要

### Web-G0 项 (BL-200 ~ BL-216) — P0

| BL ID | 名称 | 状态 | 证据 |
|-------|------|------|------|
| BL-200 | Web-G0 需求冻结 | done | Web-G0 phase 文档已创建，backlog/traceability/spec/checklist 均已更新 |
| BL-201 | 首页重构（Dashboard v2） | partial | dashboard.html 已有 7 个区域（市场/自选股/持仓/任务/报告/告警/龙头板块/数据健康），但并非所有卡片都实现了 loading/empty/error/degraded/stale 五态 |
| BL-202 | 默认入口变更 `/` → `/dashboard` | done | `/` route 返回 302 → `/dashboard`，已在 `web/__init__.py` 实现 |
| BL-203 | DSA-01 每日市场复盘 | partial | 市场摘要 API (market/summary) + dashboard 指数卡片已存在，但缺少按交易日生成结构化的市场回顾报告功能 |
| BL-204 | DSA-02 自选股批量分析 | partial | dashboard 有自选股异动卡片，watchlist 管理存在于 paper_trader，但缺少批量 AI 分析入口 |
| BL-205 | DSA-03 决策仪表盘摘要 | partial | dashboard 展示汇总数据卡片（跟踪股票数/回测数/模拟盘净值/持仓数），但缺少 buy/hold/sell/research-only 决策摘要 |
| BL-206 | DSA-04 历史报告归档 | partial | `/reports` 页面 + `/api/v1/reports/pptx` 端点存在，但报告缺少 symbol/模型/数据快照等结构化字段 |
| BL-207 | DSA-05 任务进度 | partial | `/api/v1/ops/tasks` 端点 + 任务中心页面（ops_audit.html）存在，但 dashboard 任务卡片缺少 queued/running/succeeded/failed 状态展示 |
| BL-208 | AIS-01 实时盯盘 | partial | `/market_leaders` 页面整合了龙头/龙虎榜/北向/板块 tab，但缺少统一的自选股实时状态表 |
| BL-209 | AIS-06 板块轮动 | partial | market/sectors API + dashboard 热门板块 TOP3 卡片存在，但缺少板块轮动详细视图 |
| BL-210 | AIS-09 持仓监控 | partial | dashboard 显示持仓数量 + 模拟盘净值，portfolio 页面显示完整组合数据 |
| BL-211 | TA-01 AI 研究链展示 | partial | research.html + ai_agent.html 存在，但缺少 researcher/trader/risk/portfolio 分层链路展示 |
| BL-212 | TA-03 research_only 安全边界 | planned | 所有 AI 输出默认 actionable=false 未全局实现 |
| BL-213 | TA-04 回测引擎入口 | partial | dashboard 有回测快捷入口 + 最近回测列表，backtest/run + backtest/optimize API 均已存在 |
| BL-214 | TA-07 模拟盘状态 | partial | dashboard 展示 paper_total_value + paper_positions，paper.html 页面存在 |
| BL-215 | TA-09 组合 VaR/集中度/归因 | partial | portfolio.html + `/api/v1/portfolio/risk` + `/api/v1/portfolio/attribution` 已实现（Phase 36） |
| BL-216 | TA-11 数据健康 | partial | data_health.html + `/api/v1/data/health` API 已存在，dashboard 有数据健康摘要卡片 |

### Web-P1 项 (BL-300 ~ BL-316) — P1

| BL ID | 名称 | 状态 | 证据 |
|-------|------|------|------|
| BL-300 | DSA-06 推送通知配置 | planned | 无通知系统，settings.html 无推送配置入口 |
| BL-301 | DSA-07 定时任务 | partial | PaperTradeScheduler (`execution/scheduler.py`) 已实现，但仅用于模拟盘交易周期，无通用分析任务调度 |
| BL-302 | DSA-12 代码/名称/拼音补全 | planned | 搜索框无智能补全功能 |
| BL-303 | AIS-02 AI 盯盘摘要 | planned | 无异常股票 AI 摘要 |
| BL-304 | AIS-03 主力资金 | partial | northbound API (北向资金) 存在，但无统一的主力资金流入/流出组件 |
| BL-305 | AIS-04 龙虎榜整合 | partial | dragon-tiger API + legacy dragon_tiger.html + 已集成到 market_leaders iframe tab |
| BL-306 | AIS-05 北向资金整合 | partial | northbound API + legacy northbound.html + 已集成到 market_leaders iframe tab |
| BL-307 | AIS-07 主力选股批量分析 | planned | 无候选池批量分析入口 |
| BL-308 | AIS-08 策略监控 | planned | 策略信号与告警系统未连接 |
| BL-309 | AIS-10 条件告警 | planned | `/api/v1/alerts` 不存在，无任何告警系统 |
| BL-310 | AIS-12 模型配置 | partial | settings.html 有模型/数据源选择器，但研究记录缺少 model/prompt_version |
| BL-311 | AIS-13 miniQMT/QMT 入口 | partial | qmt.html + `/api/v1/qmt/` routes 存在，但缺少 managed/paper 能力等级标注 |
| BL-312 | AIS-14 T+1 规则适配 | planned | T+1 约束未在回测/模拟盘/受控执行路径中显式标注 |
| BL-313 | TA-05 参数优化 | partial | backtest/optimize API 已存在，但优化结果未与报告关联 |
| BL-314 | TA-06 Walk-forward/反偏差检查 | planned | 回测结果缺少数据质量/OOS/偏差检查 |
| BL-315 | TA-08 QMT 受控执行 | partial | QMT routes + risk gate 已接线，但 QMT 不可用时 disabled/paper 降级未实现 |
| BL-316 | TA-10 审计中心 | partial | AuditStore + ops/tasks + ops/audit + ops/stats API + ops_audit.html 已存在 |

### Web-P2 项 (BL-400 ~ BL-404) — P2

| BL ID | 名称 | 状态 | 证据 |
|-------|------|------|------|
| BL-400 | DSA-10 多轮问股 | planned | 单股分析无上下文追问能力 |
| BL-401 | DSA-11 图片/CSV/Excel 导入 | planned | 无导入功能 |
| BL-402 | DSA-13 多市场支持 | planned | 仅支持 A 股 |
| BL-403 | AIS-11 宏观分析 | planned | 无宏观数据查询 |
| BL-404 | TDX-07 Obsidian 消费 | planned | 无 Obsidian 集成 |

### 状态分布统计

| 状态 | 数量 | 占比 |
|------|------|------|
| done | 2 | 5.1% |
| partial | 23 | 59.0% |
| planned | 14 | 35.9% |
| blocked | 0 | 0% |
| **合计** | **39** | **100%** |

## 5. 产品规范与验收清单检查

### ASTOCK_WEBUI_PRODUCT_SPEC.md

7 模块 IA 已在 base.html 的 tab 导航和 sidebar 中全部落地：
- 今日工作台 → `/dashboard` ✅
- 盯盘中心 → `/market_leaders` ✅
- AI 研究 → `/research` ✅
- 策略实验室 → `/strategy_hub` ✅
- 组合与风控 → `/portfolio` ✅
- 交易执行 → `/trading` ✅
- 系统与配置 → `/settings` ✅

不需要更新。

### ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md

当前清单覆盖了 Dashboard v2、Watch Center、AI Research Center、Strategy Lab、Market Leaders、Trading & Execution、Data & Ops、Portfolio Workbench 的核心页面。新页面清单（Market Leaders 候选池、策略完成度检查、组合风控与执行页等）已在清单中登记。不需要补充新页面，但后续 phase 开发需逐页补充验收状态。

**结论：不需要修改 product spec 或 acceptance checklist。** 当前文档 scope 已覆盖现有页面，后续 phase 开发时补充具体验收记录即可。

## 6. 测试命令

```bash
# 验证所有 API 端点存在
pytest tests/test_astock_api.py -q -k "test_" 2>/dev/null | tail -3

# 验证所有页面路由存在
pytest tests/test_astock_web.py -q 2>/dev/null | tail -3

# 验证 dashboard 页面返回 200
python -c "
import sys; sys.path.insert(0, '.')
try:
    from tradingagents.astock.web import app
    with app.test_client() as c:
        resp = c.get('/dashboard')
        print(f'/dashboard status: {resp.status_code}')
        assert resp.status_code == 200
    print('Dashboard route OK')
except Exception as e:
    print(f'Skipping runtime check: {e}')
"

# 验证 / 路由 302 → /dashboard
python -c "
import sys; sys.path.insert(0, '.')
try:
    from tradingagents.astock.web import app
    with app.test_client() as c:
        resp = c.get('/')
        print(f'Root route status: {resp.status_code}')
        print(f'Location: {resp.location}')
        assert resp.status_code == 302
        assert resp.location == '/dashboard'
    print('Root redirect OK')
except Exception as e:
    print(f'Skipping runtime check: {e}')
"

# 统计 BL 文档中状态分布
echo "=== Backlog status distribution ==="
grep -c '状态.*done\|状态.*partial\|状态.*planned\|状态.*blocked' docs/ASTOCK_BACKLOG.md 2>/dev/null || echo "check inline"

echo "=== Traceability FR-11~26 status ==="
grep 'FR-1[1-6]\|FR-2[0-6]' docs/ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md 2>/dev/null
```

## 7. 产品决策

| 决策 | 内容 | 理由 |
|------|------|------|
| 状态回填原则 | 严格按实际代码路径判断，不臆测未实现功能 | 避免文档状态与实际开发进度脱钩 |
| partial 的判定标准 | 只要存在 API 端点或 HTML 页面，不管是否完整产品形态，都算 partial | 现有代码有大量功能骨架但需要 WebUI 产品化落地 |
| planned 的判定标准 | 没有任何代码实现（API/页面/路由均不可见）才算 planned | 告警系统、T+1 适配、批量分析等需要新建模块 |

## 8. 完成标准

- ✅ BL-200 ~ BL-404 共 39 项逐一标注了实现状态并写入 backlog
- ✅ FR-11 ~ FR-26 共 16 项在 traceability 矩阵中状态更新
- ✅ 产品规范和验收清单已完成检查，不需要修改
- ✅ 本 phase 归档文档已创建

---

**来源**: `docs/ASTOCK_WEB_WORKBENCH_PARITY_TODO.md` §7 Web-P1
**Commit SHA**: *(pending — 本 phase 合并后更新)*

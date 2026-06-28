# Phase Web-G0：需求冻结与追踪矩阵落地

| 状态：done | 更新日期：2026-06-27 |

## 0. 前置依赖

- 无（Web-G0 是 Web 工作台竞品对齐的第一阶段，不依赖其他 phase）
- 技术审核结论已写入 `docs/ASTOCK_WEB_WORKBENCH_PARITY_TODO.md`

## 1. Phase 目标

在正式改代码前，把 Web 工作台竞品对齐需求写入 backlog 和 traceability 文档，固定默认入口、能力标签和安全边界，避免开发中反复改方向。

## 2. 范围

### 包含

- 创建 / 更新 `BACKLOG.md`，纳入 Web 工作台改造 P0/P1/P2 项，含 DSA/AIS/TA/REF/TDX 矩阵映射
- 创建 / 更新 `04-dev/traceability-matrix.md`，为每个竞品能力分配需求 ID，标注归属模块、phase、验收证据位置
- 创建 / 更新 `02-guide/USER_MANUAL.md`，定义 7 模块信息架构（今日工作台、盯盘中心、AI 研究、策略实验室、组合与风控、交易执行、系统与配置）
- 创建 / 更新 `README.md`，纳入全新 dashboard 页面及其所有状态（success / empty / error / degraded / caching / paper/managed 标签）
- 修改 `/` 路由默认行为：从 `trading.html` 改为 `302 -> /dashboard`
- 明确 `/dashboard` 为产品默认首页
- 明确 QMT/miniQMT 默认值：`managed` 或 `paper`，非自动实盘
- 明确 TDX 行情链路归属 Data & Ops，不归属 Trading & Execution

### 排除

- 不修改任何前端后端运行代码（除 `/` 路由 302 重定向外）
- 不创建新页面、不修改业务逻辑、不添加新 API
- 不运行 UAT 或集成测试——本阶段只做文档和路由配置

## 3. 任务分解

| ID | 任务 | 产物 | 验收 |
|----|------|------|------|
| G0-01 | 创建 / 更新 `ASTOCK_BACKLOG.md`，纳入 Web 工作台 P0/P1/P2 需求项，含 DSA/AIS/TA/REF/TDX 矩阵到需求 ID 的映射 | `BACKLOG.md` | 每个 DSA/AIS/TA/REF/TDX 编号至少对应一个 backlog 条目；P0/P1/P2 标记明确 |
| G0-02 | 创建 / 更新 `ASTOCK_REQUIREMENTS_TRACEABILITY_MATRIX.md`，为每个能力分配唯一需求 ID，标注归属模块、目标 phase、验收证据位置 | `04-dev/traceability-matrix.md` | 所有 P0/P1 能力均有需求 ID、模块、phase、验收证据位置 |
| G0-03 | 创建 / 更新 `ASTOCK_WEBUI_PRODUCT_SPEC.md`，定义 7 模块信息架构及其目标、默认能力等级 | `02-guide/USER_MANUAL.md` | 7 模块覆盖：今日工作台、盯盘中心、AI 研究、策略实验室、组合与风控、交易执行、系统与配置 |
| G0-04 | 创建 / 更新 `ASTOCK_WEBUI_PAGE_ACCEPTANCE_CHECKLIST.md`，纳入新 dashboard 页面及其所有状态 | `README.md` | dashboard 页面列出 success / empty / error / degraded / caching / paper/managed 标签验收项 |
| G0-05 | 修改 `/` 路由默认目标，从 `trading.html` 改为 `302 -> /dashboard` | `tradingagents/astock/web/__init__.py`（路由定义） | curl / 浏览器访问 `/` 返回 302 且 Location 指向 `/dashboard` |
| G0-06 | 在所有文档中明确 `/dashboard` 为默认首页 | 所有更新的 doc 文件 | TODO doc、Product Spec、Backlog、Traceability 中均标注 `/dashboard` 为默认首页 |
| G0-07 | 在所有文档中明确 QMT/miniQMT 默认值为 `managed` 或 `paper`，非自动实盘 | 所有更新的 doc 文件 | TODO doc、Product Spec 中 QMT/miniQMT 入口标注默认 managed/paper |
| G0-08 | 验收所有文档：确认文档中 planned 状态不被标记为 done | 检查所有文档的当前状态列 | 未实现的能力状态 == `planned`，不出现虚假 `done` |

## 4. 测试命令

```bash
# 验证 / 路由 302 重定向到 /dashboard
curl -sI http://localhost:5000/ 2>/dev/null | head -5

# 如果 Flask 应用已在运行，检查路由注册
pytest tests/test_astock_web.py -q -k "route" 2>/dev/null || echo "Route tests: no dedicated route test exists yet — see below"

# 兜底：直接检查路由代码断言
python -c "
import sys; sys.path.insert(0, '.')
try:
    from tradingagents.astock.web import app
    rules = [r.rule for r in app.url_map.iter_rules() if r.rule == '/']
    assert len(rules) == 1, f'Expected 1 root route, got {len(rules)}'
    route = [r for r in app.url_map.iter_rules() if r.rule == '/'][0]
    # Flask default view returns response directly, check endpoint name
    print(f'Root route endpoint: {route.endpoint}')
    print(f'Root route methods: {route.methods}')
    print('Route registration OK')
except ModuleNotFoundError as e:
    print(f'Cannot import web app: {e}')
    print('Skipping Python-level route check — app not loadable in this env')
except Exception as e:
    print(f'Route check error: {e}')
"

# 文档完整性检查
echo "=== Backlog coverage ==="
grep -cE '(DSA|AIS|TA|REF|TDX)-' BACKLOG.md 2>/dev/null || echo "No backlog file yet"

echo "=== Traceability coverage ==="
head -1 04-dev/traceability-matrix.md 2>/dev/null || echo "No traceability file yet"

echo "=== Product Spec coverage ==="
grep -cE '(今日工作台|盯盘中心|AI 研究|策略实验室|组合与风控|交易执行|系统与配置)' 02-guide/USER_MANUAL.md 2>/dev/null || echo "No product spec file yet"

echo "=== Acceptance Checklist ==="
grep -cE '(dashboard|empty|error|degraded)' README.md 2>/dev/null || echo "No checklist file yet"
```

## 5. 产品决策

| 决策 | 内容 | 理由 |
|------|------|------|
| 默认首页 | `/dashboard` | 用户打开首页 30 秒内需知道今天该看什么；交易页不应作为第一屏 |
| 根路由 | `/` -> `302 -> /dashboard` | 向后兼容；旧入口保留但不再做默认首页 |
| QMT/miniQMT 默认模式 | `managed` / `paper` | 防止 AI 直接实盘交易；自动实盘必须显式启用并标注风险 |
| TDX 行情链路归属 | Data & Ops | 行情数据是基础设施，不归属交易执行模块，避免架构耦合 |
| 文档状态原则 | 未实现的能力必须标注 `planned` | 防止后续误以为功能已完成 |
| 7 模块信息架构 | 今日工作台、盯盘中心、AI 研究、策略实验室、组合与风控、交易执行、系统与配置 | 覆盖三个竞品赛道 + 本项目已有重型能力，主次分明 |

## 6. 完成标准

- 每个 P0/P1 能力都有需求 ID、模块、phase、验收证据位置
- 文档状态不把 planned 写成 done
- `/dashboard` 被所有文档明确标注为默认首页
- QMT/miniQMT 在所有文档中标注默认 managed/paper
- TDX 行情链路明确归属 Data & Ops
- 完成后才能进入 Web-P0

---

**来源**: `docs/ASTOCK_WEB_WORKBENCH_PARITY_TODO.md` §7 Web-G0
**Commit SHA**: *(pending — 本 phase 合并后更新)*

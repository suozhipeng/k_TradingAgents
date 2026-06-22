# Phase 19：绩效分析 + 数据刷新/缓存 + 测试重构

## 元数据

- Status: `complete`
- Started: `2026-06-15`
- Completed: `2026-06-16`
- Owner: `Hermes`
- Branch: `xg_dev`
- Commits: `91c13b7`, `02aab36`, `6fc85d8`, `d75c734`, `957d159`

## 产品目标

新增绩效分析 WebUI（Chart.js 可视化）、数据刷新/缓存管理 WebUI，修复 valuation 性能缺陷，重构测试架构消除假包污染。

## 范围

### 包含

1. **WebUI 绩效分析** `/performance`：
   - Chart.js 净值曲线 + 初始资金基线
   - 回撤填充面积图
   - 周期收益柱状图（绿色/红色）
   - 买入/卖出信号分布环形图
   - 6 指标卡片（总收益、年化收益、Sharpe、最大回撤、胜率、交易次数）
   - 最近 24 期净值明细表
   - `POST /api/v1/backtest/analyze` API 端点

2. **数据刷新 API + WebUI**：
   - `POST /data/refresh/kline` — 手动拉取 K-line → DuckDB
   - `POST /data/refresh/valuation` — 手动拉取估值
   - `POST /data/refresh/all` — 批量多标的
   - 设置页（`/settings`）增加数据刷新面板
   - 研究页（`/research`）增加刷新 K-line/估值按钮

3. **缓存管理 API + WebUI**：
   - `GET /api/v1/cache/status` — 缓存桶大小（snapshot/history/summary）
   - `POST /api/v1/cache/clear` — 清空内存缓存
   - 设置页缓存管理面板

4. **valuation 路由优化**：
   - 路由顺序改为 tencent → akshare → mootdx
   - tencent 估值 ~0.3s（vs akshare ~26s），80x 提速
   - tencent 返回 PB/market_cap（akshare 返回 null）
   - 修复 ValuationLoader flat dict → DuckDB 写入

5. **环境升级**：
   - Python 3.9 → 3.10.19
   - `.venv/` 虚拟环境，全依赖安装
   - 缺失依赖：typer, streamlit, duckdb, flask, python-pptx, akshare, mootdx, pywencai

6. **测试架构重构**：
   - 11 个测试文件的 `_load_submodule` 消灭 `__path__=[]` 假包注入
   - 改用 `importlib.import_module()` 加载真实父包
   - 修复 `test_strategies_has_lists` 断言匹配新 UI
   - 全仓回归从 636/76/2 → **739/0/0**

7. **WebUI 断链修复**：
   - `/api/v1/backtest/list` → `/api/v1/backtest/results`
   - `/api/v1/data/research` → `/api/v1/research`

### 排除

- QMT 实盘部署（需外部环境）
- 新市场扩展

## 产品决策

1. tencent 作为 valuation 首选源（速度快、数据质量好）
2. 测试文件保留 `_load_submodule` 模式但改用真实父包导入
3. Flask dev server 端口改为 8080（macOS 5000 被 AirPlay 占用）

## 测试

- 全仓回归：**739 passed, 9 skipped, 0 failed, 0 errors**
- 测试文件重构：11 个文件修改，-281 +324 行

## 风险

- macOS 端口 5000 被 AirPlay 占用（需用 PORT=8080）
- `test_astock_web.py` 测试与 Flask `:memory:` DuckDB 连接偶有冲突（已隔离分组通过）

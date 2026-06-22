# Phase 22: KLineChart 全功能集成 + 全站优化

## 元数据

- Status: `implemented`
- Implementation: `complete`
- Started: `2026-06-20`
- Completed: `2026-06-22`
- Git branch: `xg_dev`
- Commits: `a0eb186`, `6a7cece`, `c94f8cd`, `23592c0`, `d049640`, `4297327`, `4007301`, `fb2d16b`, `624f088`, `f355a89`, `ad5f530`, `44c1b52`

## 范围

将 Research 页 K 线图从 lightweight-charts 迁移至 KLineChart，增加完整的技术指标和画线工具。同时修复全站 NaN JSON 序列化问题和多项 UI 缺陷。

## 已完成的变更

### 核心功能

| 变更 | 文件 | 说明 |
|------|------|------|
| KLineChart 集成 | `research.html` | 替换 lightweight-charts，保留十字光标联动统计、点击详情面板、周期切换 |
| KC Chart 独立页 | `kc_chart.html` (新) | 27 个技术指标 + 17 个画线工具 + 6 周期切换 + 实时更新 |
| TV Charting Library 准备 | `tv_chart.html` (新), `routes_tv.py` (新), `datafeed.js` (新) | Datafeed 适配器 + API 端点，待 Charting Library 文件到位 |
| Research 页跳转按钮 | `research.html` | 📊 KC Chart + 📈 TV Pro 双按钮，动态更新 symbol |

### 基础架构修复

| 变更 | 文件 | 说明 |
|------|------|------|
| NaN JSON 序列化 | `routes_data.py`, `routes_market.py`, `routes_backtest.py`, `routes_dashboard.py` | 所有 `to_dict()` 调用后替换 NaN/Inf → None |
| ValueError 异常捕获 | `routes_dashboard.py` | `_sanitize()` 增加 ValueError |
| 分钟级 K 线数据 | `routes_data.py` | mootdx fallback，5m/30m/60m 直接返回（不存 store） |
| 日期格式 | `routes_data.py`, `routes_market.py` | 带时间 → `YYYY-MM-DD HH:MM`，无时间 → `YYYY-MM-DD` |

### UI 缺陷修复

| 页面 | 问题 | 修复 |
|------|------|------|
| `reports.html` | `/api/v1/performance` 不存在导致 JSON 解析崩溃 | 移除已删除的 performance 选项 |
| `risk.html` | `/api/v1/market/summary` 缺 symbol 参数一直 400 | 添加 `?symbol=600519.SH` |
| `paper.html` | `??` 不捕获 NaN | 改为 `\|\| 0` |

### 测试

- `tests/test_astock_web.py` — 更新 research 页断言（移除 `kline-period-bar`、`history-days`）
- 812 tests passed, 9 skipped（仅跳过 live provider 和条件测试）

### 依赖

| 包 | 来源 | 用途 |
|----|------|------|
| `lightweight-charts@5.2.0` | npm → 静态目录 | Research 页 K 线图（已替换为 KLineChart，保留备份） |
| `klinecharts@10.0.0-beta3` | npm → 静态目录 | 全站 K 线引擎 |
| `charting_library@1.0.2` | npm → 未使用 | 仅类型定义，实际 Charting Library 需从官网下载 |

## 演示

- Research 页: `http://localhost:8080/research?symbol=600519.SH`
- KC Chart 独立页: `http://localhost:8080/kc_chart?symbol=600519.SH`
- TV Pro 页（需 Charting Library 文件）: `http://localhost:8080/tv_chart?symbol=600519.SH`

## 排除项

- TradingView Charting Library 文件未下载（需用户从官网申请）
- iwencai 语义搜索凭未配置
- 分钟级数据未持久化到 DB（DuckDB DATE 列限制）

## 风险评估

| 风险 | 概率 | 缓解 |
|------|------|------|
| KLineChart `createOverlay` 在某些浏览器不兼容 | 低 | 标准 Canvas API，所有现代浏览器支持 |
| mootdx 分钟数据网络延迟 | 中 | 异步加载，超时 60s，失败不影响日线展示 |
| Charting Library 后续集成 | 低 | Datafeed 适配器已就绪，只需放置文件 |

## 下阶段准入条件

1. TradingView Charting Library 文件下载就位
2. 或确认 KLineChart 已满足全部需求，关闭方案 B

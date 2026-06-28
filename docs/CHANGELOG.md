# Changelog

## 2026-06-28

- **feat**: 数据库模块 v1.0 — 三后端架构 (DuckDB/PostgreSQL/ClickHouse)
  - 完整 schema 设计：31 表，包含迁移版本管理、审计日志、API 密钥、数据质量规则和隔离区
  - 迁移引擎：`MIGRATIONS` 列表 + 运行时自动迁移
  - `DataJobManager` 升级：重试/优先级/持久化
  - 生产部署脚本：`scripts/astock_pg_tool.py` + `scripts/astock_sync_ch.py`
- **docs**: 新增 `full_function_documentation.md`（885行全功能文档）
- **docs**: 新增 `database_module_whitepaper.md`（708行数据库白皮书）
- **docs**: 新增 `docs/04-dev/PRD.md`（1094行合并需求文档）
- **cli**: Docker-based subprocess executor (`cli/main.py`)

## 2026-06-27

- **docs**: 大规模文档重组（84→50活跃文档，67归档）
  - 新增子目录结构: `01-arch/` `02-guide/` `03-ops/` `04-dev/`
  - 合并需求文档 → `04-dev/PRD.md`
  - 合并 API 文档 → `01-arch/API.md`
  - 已完成 phase 归档至 `_archived/`
- **feat**: 工业级回测引擎 v2 (`modules/backtest_engine.py`)
- **feat**: 回测看板 (`backtest.html`, ECharts 3Tab)
- **fix**: API `run_backtest` 增加 `data_assumption` 字段
- **feat**: GA 优化器 + StockFlow + PortfolioStrategyBase + MarketAnalyzer auto_regime + WFA
- **feat**: 预警系统 BL-309 — 规则 CRUD、检查引擎、告警历史
- **misc**: `.gitignore` 增加 `*.duckdb` 和 `docs/_archived/`

> 完整历史见 `_archived/ASTOCK_BACKLOG.md`。

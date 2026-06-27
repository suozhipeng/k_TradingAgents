# Changelog

## 2026-06-27

- **docs**: 大规模文档重组（84→50活跃文档，67归档）
  - 新增子目录结构: `01-arch/` `02-guide/` `03-ops/` `04-dev/`
  - 合并需求文档 → `04-dev/PRD.md`
  - 合并 API 文档 → `01-arch/API.md`
  - 已完成 phase 归档至 `_archived/`
- **feat**: 工业级回测引擎 v2 (`modules/backtest_engine.py`)
- **feat**: 回测看板 (`backtest.html`, ECharts 3Tab)
- **cli**: Docker-based subprocess executor
- **misc**: `.gitignore` 增加 `*.duckdb` 和 `docs/_archived/`

> 完整历史见 `_archived/ASTOCK_BACKLOG.md`。

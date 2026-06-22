# Delivery Phase Archive

This directory is the canonical local archive for every A-share Delivery
Phase. Chat output, commit messages, and standalone phase notes do not replace
the archive record.

## Required workflow

For every phase:

1. Create or update `phase-XX-<slug>.md`.
2. Record the phase objective and product boundary before implementation.
3. Record changed modules and behavior after implementation.
4. Record exact test commands and results.
5. Record unresolved risks and next-phase entry criteria.
6. Add the final Git commit SHA after the phase commit is created.
7. Update this index and `docs/ASTOCK_CURRENT_STATUS.md`.

A phase is not complete until its archive entry exists. If the commit SHA is
not known before commit, use `pending` and update it in the next documentation
checkpoint.

## Archive index

| Phase | Scope | Status | Archive / evidence |
|---|---|---|---|
| 0 | Positioning, boundary, disclaimer | Complete | [Phase 0](phase-00-boundary-blueprint.md) |
| 1 | Provider selection, routing, fallback, cache | Complete | [Phase 1](phase-01-provider-routing.md) |
| 2 | Five-layer 18-capability matrix | Foundation complete | [Phase 2](phase-02-capability-matrix.md) |
| 3 | Interface, tools, AStockAnalyst | Complete | [Phase 3](phase-03-interface-analyst.md) |
| 4 | Research graph bridge | Complete | [Phase 4](phase-04-research-graph.md) |
| 5 | Research runtime verification | Complete | [Phase 5](phase-05-research-runtime.md) |
| 6 | Research-only entry dispatch | Complete | [Phase 6](phase-06-entry-dispatch.md) |
| 7 | Display schema and CLI | Complete | [Phase 7](phase-07-schema-cli.md) |
| 8 | Read-only UI and multi-market viewer | Complete | [Phase 8](phase-08-readonly-viewer.md) |
| 9 | Trader, Risk, Portfolio Manager adaptation | Implementation complete — advisory chain wiring, CLI/UI rendering, runtime profiles, 62-test regression slice | [Phase 9](phase-09-trader-risk-portfolio.md) |
| 10 | Backtest and paper trading | Complete | [Phase 10](phase-10-backtest-paper-trading.md) |
|| 11 | QMT bridge — read-only to controlled execution | Complete | [Phase 11](phase-11-qmt-controlled-execution.md) |
| 12 | DuckDB local database — 10 tables, CLI tool, import/export | Complete | [Phase 12](phase-12-duckdb-local-database.md) |
| 13 | WebUI i18n + market switch — zh/en, LangSwitch, MarketSwitch | Complete | commit `02aee20` |
| 14 | Six backtest strategies (2 bull / 2 oscillation / 2 bear) | Complete | [Phase 14](phase-14-strategy-expansion.md) |
| 15 | Flask REST API + Chart.js + WebUI API client — 19 endpoints | Complete | commit `eff5d24` |
| 16 | Batch backtest, market analyzer, scheduler, SSE — 36 tests | Complete | commit `0019dc9` |
| 17 | Flask Jinja2 WebUI 9 pages + PPT reporting — 54 tests | Complete | commit `8f2423e` |
| 18 | Strategy expansion + optimizer — MACD, Bollinger, Grid + grid-search optimizer | Complete | commit `88b57a4`, `a1520d4`, `2c37feb` |
| 19 | Performance analysis + data refresh/cache + test refactor — Chart.js, 739/739 | Complete | commit `91c13b7`, `02aab36`, `957d159` |
| 20 | Strategy comparison WebUI — compare API enhanced (equity_curve, rank), multi-strategy Chart.js overlay | Complete | commit `d128dc9` |
|| 21 | Test stabilization — 786/795 passed, 0 failed, 0 errors, 4× consistent runs | Complete | [Phase 21](phase-21-test-stabilization.md) |
|| — | WebUI risk/reports pages upgrade + mootdx verification + iwencai docs | Complete | Hotfix (post-Phase-21) |
|| 22 | KLineChart full integration — lightweight-charts replacement, 27 indicators, 17 drawing tools, 6 periods, mootdx minute data, NaN serialization fix | Complete | [Phase 22](phase-22-klinechart-integration.md) |
|| 23 | 龙头股动量轮动决策系统 — stock pool, momentum rotation strategy, Streamlit + WebUI | Complete | [Phase 23](phase-23-momentum-rotation.md) |
|| 24 | AI Agent analysis page — ai_agent.html | Complete | [Phase 24](phase-24-ai-agent-page.md) |
|| 25 | Stock screener + sector rotation — TradingView-style screener, ECharts treemap heatmap | Complete | [Phase 25](phase-25-screener-sectors.md) |
|| 26 | WebUI full refactor — Strategy Hub (backtest+performance+compare merge), sidebar cleanup, Research v2, data-explosion prevention | Complete | [Phase 26](phase-26-webui-refactor.md) |
|| 27 | DataCleaner — full-path NaN→None sanitization, _coerce_float fix, _clean_nan() helper | Complete | [Phase 27](phase-27-data-cleaner.md) |
|| 28 | 5 new WebUI pages — momentum dashboard, momentum rotation, dragon_tiger, northbound, data_health | Complete | [Phase 28](phase-28-new-webui-pages.md) |
|| 29 | Professional trading page — TradingView-style trading console, real-time quotes, order panel, KLineChart, positions | Complete | [Phase 29](phase-29-trading-page.md) |

## Naming

Use lowercase ASCII filenames:

```text
phase-09-trader-risk-portfolio.md
phase-10-backtest-paper-trading.md
phase-11-qmt-controlled-execution.md
phase-12-duckdb-local-database.md
```

Do not overwrite historical results. Append a dated correction section when
later work changes an earlier conclusion.

## Operational governance

The phase archive is complemented by repo-level execution governance docs:

- [Hermes Skills Playbook](../HERMES_SKILLS_PLAYBOOK.md)
- [Hermes, Codex, DeepSeek Workflow](../HERMES_CODEX_DEEPSEEK_WORKFLOW.md)
- [Phase 09 Hermes Execution Brief](phase-09-hermes-execution-brief.md)

---
name: tradingagents-core
description: "Project-level core context for TradingAgents. Covers multi-agent architecture, backtesting, risk metrics, A-share provider chain, WebUI conventions, strategy development, and project boundaries. Mandatory first skill for any work touching the codebase."
version: 1.0.0
platforms: [linux, macos]
related_skills: [astock-analyst-delivery, astock-provider-delivery, astock-rollout-orchestrator, ecc-readonly-review, ecc-self-test, api-and-interface-design, security-and-hardening, source-driven-development]
---

# TradingAgents Core

Project-level core context for the TradingAgents multi-agent financial trading framework.

## When to Use

**Always load this skill first** before any other project skill. Mandatory when:

- Understanding the project architecture or module boundaries
- Working on multi-agent analysis chain (researchers → analysts → risk → trader)
- Modifying any part of the A-share extension (astock)
- Working on backtest engine, strategy lifecycle, or risk metrics
- Adding/modifying strategies, optimizer, momentum rotation
- Working on WebUI or display conventions
- Refactoring module boundaries or updating requirements docs
- Reviewing whether a change preserves original TradingAgents AI analysis capabilities

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Agent orchestration | LangGraph 0.4+ / LangChain 0.3+ |
| Data validation | Pydantic (BaseModel schemas) |
| Testing | pytest with unit/integration/smoke markers |
| CLI | Typer + Rich |
| Frontend | Jinja2 templates (25 pages) / React/TS experimental |
| REST API | Flask (14 blueprints, 57 endpoints) |
| Database | DuckDB (local, 10 tables) |
| Deployment | Docker / docker-compose (with Ollama profile) |
| A-stock data | akshare, mootdx, pywencai, Tencent Finance |
| Backtesting | backtrader 1.9+ |
| General market | yfinance, alpha_vantage |
| Risk | ATR stop-loss, safety/auto mode, portfolio constraints |

## Project Structure

```
k_TradingAgents/
├── tradingagents/              # Main package
│   ├── astock/                 # A-share extension
│   │   ├── data_sources/       # Provider adapters, router, cache, schema
│   │   ├── execution/          # Backtest, paper trading, QMT bridge, risk gate
│   │   ├── analysis/           # Market regime analysis
│   │   ├── api/                # Flask REST API (14 blueprints)
│   │   └── web/                # Jinja2 WebUI (25 templates)
│   ├── agents/                 # Original multi-agent system
│   ├── llm_clients/            # LLM provider abstraction
│   ├── dataflows/              # Data source routing
│   └── graph/                  # LangGraph orchestration
├── cli/                        # Typer CLI entry point
├── webui/                      # React/TS experimental frontend
├── tests/                      # pytest test suite (~67 files)
├── docs/                       # Phase archives, requirements, status
├── planning/                   # Architecture docs, review records
└── skills/                     # Project-local skills
```

## Multi-Agent Architecture

The research → analysis → risk → decision flow:

```
Data Sources (yfinance, akshare, etc.)
  → Analysts (Market, Technical, Sentiment, News, Fundamental)
    → Researchers (Bull Researcher, Bear Researcher, Research Manager)
      → Trader (synthetic proposal)
        → Risk Managers (3 risk agents + Portfolio Manager)
          → Final Decision
```

Key files:
- `tradingagents/graph/setup.py` — LangGraph state graph construction
- `tradingagents/graph/conditional_logic.py` — Agent routing & selection
- `tradingagents/astock/interface.py` — A-share section bundles
- `tradingagents/astock/runtime.py` — AStockGraphRuntime + advisory chain
- `tradingagents/astock/phase9_schemas.py` — ResearchConclusion → TraderProposal → RiskDecision → PortfolioDecision

## A-Share Provider Chain

Primary → fallback:
1. **mootdx** — Tongdaxin protocol (fast, batch-capable)
2. **akshare** — Broad coverage (news, fundamentals, announcements)
3. **Tencent Finance** — Real-time quotes, low latency
4. **pywencai** — Semantic query (iwencai)
5. **DuckDB store** — Cached historical data

All routed through `tradingagents/astock/data_sources/router.py` with automatic fallback.

## Project Boundaries

### Must Preserve
- Original `tradingagents/agents/`, `graph/`, `llm_clients/`, `dataflows/` — do not refactor without explicit approval
- A-share advisory output defaults: `actionable=false`, `execution_signal=ResearchOnly`
- Safety mode: every real execution requires human confirmation (`confirmed=True`)
- `decision_scope=research_only` for all A-share outputs

### Can Modify (within phase boundary)
- A-stock data sources, interfaces, tools, analysts
- Flask API endpoints and WebUI templates
- Backtest engine, strategies, optimizer
- Risk gates, paper trader, QMT bridge
- Docs, phase archives, requirements

### Safety Gates
| Gate | Mechanism |
|------|-----------|
| Safety mode (default) | Human confirm required per execution |
| Auto mode | User opt-in via config/CLI |
| ATR stop-loss | Real-time ATR, auto-reject if triggered |
| QMT degradation | QMT unavailable → auto-fallback to paper trader |
| Risk Gate | `risk_gate.py` — position sizing, drawdown limits |

## Backtest & Strategy

Backtest engine: `tradingagents/astock/execution/backtest_engine.py`
Paper trader: `tradingagents/astock/execution/paper_trader.py`
Strategy base: `tradingagents/astock/execution/strategy_base.py`

10 strategy types: 2 bull / 2 range / 2 bear + MACD + Bollinger + Grid + Momentum rotation

Optimizer composite score: `0.35 * Sharpe + 0.30 * Return - 0.25 * Drawdown + 0.10 * TradeFrequency`

Key risk metrics: Sharpe Ratio, VaR (95%/99%), Max Drawdown, Win Rate, Profit Factor.

## Key Commands

```bash
# Build/install
pip install -e .                     # base
pip install -e .[astock-providers]   # with A-share providers
pip install -e .[ui]                 # with Streamlit viewer

# Run
tradingagents research <symbol>      # CLI research
tradingagents astock <symbol>        # A-short research

# Test
pytest tests/ -q                     # full regression
pytest tests/test_astock_data_sources.py -q    # provider tests
pytest tests/test_astock_provider_fixtures.py -q
pytest tests/test_astock_interface_analyst.py -q

# Docker
docker compose up                    # default services + app
docker compose --profile ollama up   # with local LLM
```

## Code Conventions

- **Imports**: Standard library → third-party → local (grouped)
- **Types**: Pydantic BaseModel for all data contracts
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Tests**: Fixture-first, live validation opt-in
- **Error handling**: Unified exception classes (`AStockNoDataError`, `AStockSourceUnavailableError`)
- **Serialization**: All public outputs must be JSON-serializable
- **Secrets**: Never commit `.env` files or API keys — use env vars
- **LLM safety**: Treat all model output as untrusted — validate at boundaries

## Hermes Skills Dispatch

| Task Type | Skill Chain |
|-----------|------------|
| Provider implementation | `tradingagents-core` + `astock-provider-delivery` + `ecc-self-test` |
| Interface/tools/analyst wiring | `tradingagents-core` + `astock-analyst-delivery` + `ecc-self-test` |
| Phase rollout planning | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-readonly-review` |
| Strategy/backtest dev | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| WebUI/API work | `tradingagents-core` + `astock-rollout-orchestrator` + `ecc-self-test` |
| API/interface design | `tradingagents-core` + `api-and-interface-design` |
| Security review | `tradingagents-core` + `security-and-hardening` + `ecc-readonly-review` |

## Repo Anchors

- `docs/HERMES_SKILLS_PLAYBOOK.md` — Full skill dispatch contract
- `docs/HERMES_CODEX_DEEPSEEK_WORKFLOW.md` — Controller/coder/reviewer roles
- `docs/ASTOCK_CURRENT_STATUS.md` — Current phase baseline
- `docs/ASTOCK_REQUIREMENTS.md` — Requirements traceability
- `docs/ASTOCK_STRATEGY_DEVELOPMENT_GUIDE.md` — Strategy development rules
- `docs/phases/README.md` — Phase archive index
- `planning/codebase/STACK.md` — Complete tech stack analysis
- `planning/codebase/ARCHITECTURE.md` — Architecture documentation
- `planning/review/ECC_REVIEW.md` — ECC review records

## Common Pitfalls

| Pitfall | Consequence | Prevention |
|---------|------------|-----------|
| Skipping `tradingagents-core` for small tasks | Missing project conventions, wrong patterns | Always load this skill first |
| Refactoring original agents/llm_clients/ | Breaks base TradingAgents analysis | Those modules are read-only unless explicitly approved |
| `actionable=true` in advisory output | Safety boundary violation | Default stays `actionable=false`, add explicit flag only |
| Missing provider fallback | Hard crash when primary source unavailable | Always define fallback in router.py |
| Changing schema without updating blueprint | UI/dispatch layer unaware | Update ASTOCK_BLUEPRINT in same PR |

## Red Flags

- Working without loading `tradingagents-core` first
- Modifying `tradingagents/agents/` or `tradingagents/graph/` without explicit approval
- Setting `actionable=true` on any A-share research output
- Skipping Codex review gate before marking phase complete
- Schema changes without blueprint or docs update
- Merging provider and interface work into a single task
- Phase archive written without commit SHA

## Verification

- [ ] `tradingagents-core` loaded as the first skill for this session
- [ ] Project boundaries respected (agents/graph/llm_clients untouched unless approved)
- [ ] A-share output stays `actionable=false`, `execution_signal=ResearchOnly`
- [ ] Safety mode engaged for any execution path
- [ ] All schema changes reflected in `ASTOCK_BLUEPRINT`
- [ ] Fallback chain defined for any new provider
- [ ] Phase archive written with commit SHA before handoff

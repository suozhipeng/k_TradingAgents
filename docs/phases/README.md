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
| 9 | Trader, Risk, Portfolio Manager adaptation | Implementation complete — schemas, runtime profiles, advisory report extensions, 46+6 tests | [Phase 9](phase-09-trader-risk-portfolio.md) |
| 10 | Backtest and paper trading | Not started | Create from [template](TEMPLATE.md) |
| 11 | QMT read-only to controlled execution | Not started | Create from [template](TEMPLATE.md) |

## Naming

Use lowercase ASCII filenames:

```text
phase-09-trader-risk-portfolio.md
phase-10-backtest-paper-trading.md
phase-11-qmt-controlled-execution.md
```

Do not overwrite historical results. Append a dated correction section when
later work changes an earlier conclusion.

## Operational governance

The phase archive is complemented by repo-level execution governance docs:

- [Hermes Skills Playbook](../HERMES_SKILLS_PLAYBOOK.md)
- [Hermes, Codex, DeepSeek Workflow](../HERMES_CODEX_DEEPSEEK_WORKFLOW.md)
- [Phase 09 Hermes Execution Brief](phase-09-hermes-execution-brief.md)

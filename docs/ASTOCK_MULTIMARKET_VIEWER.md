# A 股 + Legacy Multi-Market Viewer

## Purpose

This viewer unifies the read-only display contract for two input families:

1. `AStockGraphReport` for A-share runs
2. Existing legacy TradingAgents final outputs for the generic market flow

It does **not** change the underlying graph business logic or add QMT
execution.

## Input boundaries

### A 股 input
- `AStockGraphReport`
- Produced by `AStockGraphRuntime`
- Consumed directly by the shared viewer dispatcher

### Legacy input
- Existing final-state dict from the generic TradingAgents graph
- Typical keys:
  - `market_report`
  - `sentiment_report`
  - `news_report`
  - `fundamentals_report`
  - `investment_debate_state`
  - `trader_investment_plan`
  - `risk_debate_state`
- Mapped into `LegacyUiModel` before rendering

## Shared dispatcher

The viewer entrypoint is:

- `tradingagents.ui.dispatcher.render_report_page(st, payload, legacy_renderer=None)`

Dispatch rules:

1. If the payload is an A 股 report, render with the A 股 view model.
2. If the payload matches legacy finance keys, render with the legacy view model.
3. Otherwise, fall back to the legacy read-only renderer.

## A 股 rendered fields

- ticker / symbol / normalized symbol
- trade date
- runtime mode
- status
- five-layer section status
- analyst summary
- bull view
- bear view
- research manager conclusion
- provider coverage
- missing data notes
- degradation notes

## Legacy rendered fields

- market / mode / asset type identification
- overall summary
- analyst team output
- research team output
- trading team output
- risk management output
- portfolio manager output
- missing / degraded notes

## Degradation semantics

- Missing rows still render as empty / unavailable rather than aborting.
- Empty sections become notes instead of exceptions.
- The raw payload remains available in a collapsible JSON block.

## Covered markets

- A-share
- Legacy generic finance output

## Remaining TODO

- Add a richer non-read-only front-end shell later if needed.
- Keep the viewer dispatcher stable as new markets are added.
- No QMT / order placement work belongs here.

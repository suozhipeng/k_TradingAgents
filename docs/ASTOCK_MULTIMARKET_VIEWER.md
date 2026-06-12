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

The viewer is implemented with a shared read-only shell (`tradingagents.ui.read_only_shell.render_readonly_report_shell(...)`) so both market families follow the same page order and section hierarchy.

The app entry also renders a landing shell (`tradingagents.ui.read_only_shell.render_viewer_landing_shell(...)`) before the final payload view so the interface feels like a product entry page instead of a direct content dump.

- `tradingagents.ui.dispatcher.render_report_page(st, payload, legacy_renderer=None)`

Dispatch rules:

1. If the payload is an A 股 report, render with the A 股 view model.
2. If the payload matches legacy finance keys, render with the legacy view model.
3. Otherwise, fall back to the legacy read-only renderer.

## Canonical page order

Both viewer families now follow the same top-level layout so the multi-market
page feels like one product instead of two unrelated screens:

1. Identity / mode / status metrics
2. Core summary
3. Structured status
4. Secondary outputs
5. Coverage / Degradation
6. Runtime Trace
7. Raw Payload

## Visual design principles

- Use the shared read-only shell for both A 股 and legacy payloads.
- Keep the metric strip, section headers, and raw payload debug zone in the same
  positions across markets.
- Separate major blocks with simple dividers rather than introducing new page
  routes or editing affordances.
- Keep empty sections and degradation notes readable, never hidden.

- ticker / symbol / normalized symbol
- trade date
- runtime mode
- status
- core summary
- structured section status (five-layer section table)
- bull view
- bear view
- research manager conclusion
- provider coverage
- missing data notes
- degradation notes
- runtime trace

## Legacy rendered fields

- market / mode / asset type identification
- core summary / overall summary
- structured analyst outputs
- structured decision-team outputs
- missing / degraded notes
- runtime trace

## Degradation semantics

- Missing rows still render as empty / unavailable rather than aborting.
- Empty sections become notes instead of exceptions.
- The raw payload remains available in a collapsible JSON block.
- Runtime trace stays visible even when some sections degrade.

## Covered markets

- A-share
- Legacy generic finance output

## Remaining TODO

- Add a richer non-read-only front-end shell later if needed.
- Keep the viewer dispatcher stable as new markets are added.
- No QMT / order placement work belongs here.

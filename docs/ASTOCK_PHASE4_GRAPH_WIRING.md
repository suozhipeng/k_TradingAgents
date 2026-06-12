# A 股 Phase 4: Research Graph Wiring

## What changed

This phase wires the existing A-share structured analysis output into the research chain without touching UI or QMT execution.

### Connected path

`AStockInterface -> astock tools -> AStockAnalyst -> research chain`

### Wired research inputs

- `market`
- `news`
- `fundamentals`
- `announcements`
- `research`

### Graph bridge

- Added an `AStock Analyst` bridge node in the research graph setup
- Added a conditional route so A-share tickers can pass through the AStock bridge before `Bull Researcher`
- Kept the existing non-A-share route intact

## Behaviors preserved

- Missing `ASTOCK_IWENCAI_COOKIE` degrades cleanly
- Missing providers do not fail the analyst node
- Existing generic financial flow remains unchanged
- No UI changes
- No QMT execution changes

## Remaining TODO

- Trader / Risk / Portfolio Manager A 股适配
- Backtest and paper-trading integration
- QMT read-only bridge and later controlled execution

UI integration and the production entry dispatch were completed in later
delivery phases. See `docs/ASTOCK_CURRENT_STATUS.md`.

## Verification

### Tests run

- `python3.13 -m pytest -q tests/test_astock_graph_bridge.py tests/test_astock_interface_analyst.py tests/test_astock_blueprint.py tests/test_astock_data_sources.py tests/test_astock_provider_fixtures.py`
- `ASTOCK_RUN_LIVE_TESTS=1 python3.13 -m pytest -q tests/test_astock_live_providers.py -m integration`

### Result

- Offline tests: `30 passed`
- Live provider tests: `7 passed, 1 skipped`

### Skip reason

- `ASTOCK_IWENCAI_COOKIE not configured`

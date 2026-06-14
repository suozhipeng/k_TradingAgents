# Phase 08: Read-Only Multi-Market Viewer

## Metadata

- Status: `complete`
- Archive type: `reconstructed on 2026-06-13`
- Evidence commits: `9763558`, `933fc81`, `f478a42`, `46b001e`, `ea95e04`, `bc73754`

## Product objective

Render A-share and legacy reports through a shared read-only presentation
contract.

## Delivered

- Streamlit A-share viewer.
- Legacy view model and dispatcher.
- Shared report shell and landing page.
- Visible missing-data and degradation states.

## Evidence

- `docs/ASTOCK_UI_READONLY.md`
- `docs/ASTOCK_MULTIMARKET_VIEWER.md`
- `tradingagents/ui/`
- `tests/test_astock_ui_views.py`

## Remaining risk

The static React WebUI and Streamlit runtime viewer have distinct roles:
WebUI = product entrypoint (static dashboard + report viewer), Streamlit = runtime viewer backend.
Both codebases stay separate; no full technical merge.

## Next entry criteria

Phase 09 product contracts for Trader, Risk, and Portfolio Manager, while
keeping all output non-actionable.

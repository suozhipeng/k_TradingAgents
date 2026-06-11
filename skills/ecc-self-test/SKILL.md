---
name: ecc-self-test
description: Use for local regression runs, acceptance checks, provider fixture verification, test result triage, and concise self-test reporting in this TradingAgents repo.
---

# ECC Self Test

Use this skill when work is already implemented and Hermes needs to verify it locally with the repo's tests and command checks.

## Scope

- Run only the smallest meaningful test slice first.
- Expand to broader regression only after targeted checks pass.
- Distinguish test failure, environment gap, and expected skip.

## Workflow

1. Run the targeted test file(s) for the changed area.
2. If they pass, run the broader regression slice that guards the integration boundary.
3. Record pass/fail/skip with the exact command.
4. Summarize unresolved risks separately from passed validation.

## Repo anchors

- `tests/test_astock_data_sources.py`
- `tests/test_astock_provider_fixtures.py`
- `tests/test_astock_live_providers.py`
- `tests/test_astock_interface_analyst.py`

## Output shape

- Commands
- Results
- Expected skips
- Remaining gaps

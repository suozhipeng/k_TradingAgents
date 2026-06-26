---
name: ecc-self-test
description: "Use for local regression runs, acceptance checks, provider fixture verification, test result triage, and concise self-test reporting in this TradingAgents repo."
version: 1.1.0
platforms: [linux, macos]
related_skills: [ecc-readonly-review, astock-provider-delivery, astock-analyst-delivery]
---

# ECC Self Test

Use this skill when work is already implemented and Hermes needs to verify it locally with the repo's tests and command checks.

## When to Use

- After implementing provider changes — run provider-specific tests
- After wiring interface/tools/analyst — run integration tests
- Before marking a phase complete — run full regression
- Before Codex review — ensure basic test pass
- After fixing a regression — verify the fix

## Scope

- Run only the smallest meaningful test slice first.
- Expand to broader regression only after targeted checks pass.
- Distinguish test failure, environment gap, and expected skip.

## Test Ordering Strategy

```
1. Targeted test  →  the exact test file for the changed area
   ↓ if pass
2. Provider fixture test  →  validates data normalization
   ↓ if pass
3. Interface/analyst integration test  →  validates wiring
   ↓ if pass
4. Full regression  →  broader module-level regression
   ↓ if pass
5. Smoke test  →  CLI end-to-end (optional)
```

## Failure Triage Guide

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| `ModuleNotFoundError` | Missing dependency | `pip install -e .[astock-providers]` |
| `AssertionError` on fixture data | Schema mismatch between provider and fixture | Update fixture or normalization |
| `AStockSourceUnavailableError` in live test | Provider API unavailable or env var missing | Check network / env vars |
| `Timeout` or `ConnectionError` | Network issue (CI firewall, proxy) | Re-run without live providers |
| `NaN` propagates to assertion | DataCleaner not applied | Apply `DataCleaner.clean()` on all numeric fields |
| Test passes locally but fails in CI | Environment difference (Python version, locale, timezone) | Pin Python version, use UTC, check locale |

## Workflow

### Step 1: Targeted Check

Run the specific test file for the changed area:

```bash
pytest tests/test_astock_interface_analyst.py -q -k <test_name>
```

### Step 2: Regression

If they pass, run the broader regression:

```bash
pytest tests/ -q --ignore=tests/test_astock_live_providers.py
```

### Step 3: Record Results

Log pass/fail/skip with the exact command:

```text
Commands:
  - pytest tests/test_astock_provider_fixtures.py -q → PASS (12/12)
  - pytest tests/test_astock_live_providers.py -q   → SKIP (env: AKSHARE_API_KEY not set)
  - pytest tests/ -q --ignore=live                   → PASS (148/148)

Expected skips:
  test_live_akshare — needs AKSHARE_API_KEY env var

Remaining gaps:
  test_qmt_bridge skipped (QMT runtime not available in this env)
```

## Repo Anchors

- `tests/test_astock_data_sources.py`
- `tests/test_astock_provider_fixtures.py`
- `tests/test_astock_live_providers.py`
- `tests/test_astock_interface_analyst.py`

## Output Shape

- Commands executed (exact shell commands)
- Results (PASS/FAIL/SKIP with counts)
- Expected skips (why they were skipped)
- Remaining gaps (risks not covered)

## Red Flags

- Skipping targeted tests and running full regression first
- Passing `--ignore` on all live tests without documenting why
- Test failure dismissed as "environment issue" without confirming
- Running tests with altered source (uncommitted changes) and reporting pass
- No test run at all before claiming work is done

## Verification

After self-test:

- [ ] Targeted test run: exact command + PASS result
- [ ] Regression run: exact command + PASS result (or documented skips)
- [ ] Expected skips documented with reason
- [ ] Remaining gaps documented for next phase or escalation
- [ ] No uncommitted changes that could mask real failures
- [ ] Test failure root cause understood (not dismissed as "flaky")

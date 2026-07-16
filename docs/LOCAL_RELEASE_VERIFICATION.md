# Local-release verification

This is the reproducible verification entry point for the loopback A-share
workbench. It does not require provider credentials or a live data source.

## One-time setup

Use the project virtual environment and install the declared extra:

```bash
.venv/bin/python -m pip install -e ".[local-release]"
```

The extra supplies `pytest`, Playwright's Python package, and `pyarrow`. The
project declares Pydantic as a runtime dependency because the backtest result
models import it directly. Parquet tests accept either `pyarrow` or
`fastparquet`; `pyarrow` is the canonical, reproducible engine installed by
this extra, so a fresh local-release environment does not skip those tests.

Install the browser executable separately:

```bash
.venv/bin/python -m playwright install chromium
```

## Verification commands

Run the backend local-release gate, including the Store Parquet round-trip and
the Pydantic `BacktestResult` storage test:

```bash
scripts/verify_local_release.sh
```

The script fixes `ASTOCK_TESTING=1` and `TEST_PYDANTIC_BT=1` for the gate. It
fails early with the exact Python dependency install command if the declared
extra has not been installed.

Run the real Chromium regression as part of the same gate:

```bash
scripts/verify_local_release.sh --browser
```

If Chromium is missing, the browser test fails with the exact
`.venv/bin/python -m playwright install chromium` command. The direct browser
test command is also supported:

```bash
.venv/bin/python -m pytest -m browser -q tests/test_local_release_browser.py
```

The browser test starts the supported Flask workbench on an ephemeral
loopback port, follows the Research navigation after the Dashboard is idle,
and fails on unexpected console or page errors. It explicitly checks that
only the local-release-disabled audit/task requests return the expected 410;
the known offline Google Fonts CSP diagnostic is not an application error.
It uses only in-memory storage and does not place orders or call a real
provider.

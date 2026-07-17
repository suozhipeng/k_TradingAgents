"""Browser-level smoke coverage for the sole local web workbench."""

from __future__ import annotations

import threading

import pytest
from werkzeug.serving import make_server


@pytest.mark.browser
def test_local_dashboard_loads_without_browser_errors():
    try:
        import playwright.sync_api as playwright
    except ModuleNotFoundError:
        pytest.fail(
            "Playwright is not installed. Run "
            "'.venv/bin/python -m pip install -e \".[local-release]\"' "
            "before running the browser gate.",
            pytrace=False,
        )

    from tradingagents.astock.api import create_app

    app = create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={"ASTOCK_LOCAL_RELEASE": True},
    )
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors: list[str] = []
    unexpected_responses: list[str] = []
    browser = None

    def record_console_error(message):
        if message.type != "error":
            return
        # The local workbench intentionally allows only same-origin styles.
        # Chromium reports the optional Google Fonts stylesheet as a CSP error
        # when the page is tested offline; it is not an application error.
        if "fonts.googleapis.com" in message.text and "style-src" in message.text:
            return
        errors.append(message.text)

    def record_response(response):
        if response.status < 400:
            return
        unexpected_responses.append(f"{response.status} {response.url}")

    try:
        with playwright.sync_playwright() as p:
            try:
                try:
                    browser = p.chromium.launch(headless=True)
                except playwright.Error as exc:
                    pytest.fail(
                        "Playwright Chromium is not installed. Run "
                        "'.venv/bin/python -m playwright install chromium' "
                        f"before running the browser gate ({exc}).",
                        pytrace=False,
                    )
                page = browser.new_page()
                page.on("console", record_console_error)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("response", record_response)
                page.goto(f"http://127.0.0.1:{server.server_port}/dashboard", wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=15000)
                assert page.locator("main").count() == 1
                assert "市场追踪中心" in page.locator("main").inner_text()
                # Exercise a real user navigation instead of only asserting that
                # the initial HTML was returned.  The Research Centre is one of
                # the analysis-only paths intentionally kept in local release.
                page.locator('a[href="/research"]').first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=15000)
                assert page.url.endswith("/research")
                assert page.locator("main").count() == 1
                assert not errors
                assert not unexpected_responses
            finally:
                if browser is not None:
                    browser.close()
                    browser = None
    finally:
        server.shutdown()
        thread.join(timeout=2)

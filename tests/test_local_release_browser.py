"""Browser-level smoke coverage for the sole local web workbench."""

from __future__ import annotations

import threading

import pytest
from werkzeug.serving import make_server


@pytest.mark.browser
def test_local_dashboard_loads_without_browser_errors():
    playwright = pytest.importorskip("playwright.sync_api")
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
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(f"http://127.0.0.1:{server.server_port}/dashboard", wait_until="domcontentloaded")
            page.wait_for_timeout(750)
            assert page.locator("main").count() == 1
            assert "市场追踪中心" in page.locator("main").inner_text()
            # Exercise a real user navigation instead of only asserting that
            # the initial HTML was returned.  The Research Centre is one of
            # the analysis-only paths intentionally kept in local release.
            page.locator('a[href="/research"]').first.click()
            page.wait_for_load_state("domcontentloaded")
            assert page.url.endswith("/research")
            assert page.locator("main").count() == 1
            assert not errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

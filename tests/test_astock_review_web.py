"""Tests for market-review and stock-analysis web entry points."""

from pathlib import Path

from flask import Flask

from tradingagents.astock.web import bp as web_bp


def test_review_pages_render():
    template_dir = Path(__file__).parents[1] / "tradingagents/astock/web/templates"
    app = Flask(__name__, template_folder=str(template_dir))
    app.register_blueprint(web_bp)
    client = app.test_client()
    assert client.get("/market_review").status_code == 200
    assert client.get("/stock_analysis").status_code == 200
    assert b"market/review" in client.get("/market_review").data
    assert b"analysis/stock" in client.get("/stock_analysis").data

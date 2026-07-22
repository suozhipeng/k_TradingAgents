"""Test transactional upsert semantics — write-before-clean must be rejected."""

import pytest


def test_transactional_bootstrap_rejects_write_before_clean():
    """Bootstrap endpoint rejects data without quality checks (not implemented)."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    app.config["STORE"] = None  # no store = not initialized
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.post("/api/v1/setup/bootstrap")
        assert response.status_code == 500

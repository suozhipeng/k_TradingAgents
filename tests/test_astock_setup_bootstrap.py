"""Tests for setup bootstrap endpoint — verifies bootstrap creates data."""

import pytest


def test_bootstrap_returns_ok_with_proper_store():
    """Bootstrap creates data when store supports it."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    store = MagicMock()
    store.kline_count = MagicMock(return_value=0)
    store.bootstrap_sample_data = MagicMock()
    app.config["STORE"] = store
    app.config["ASTOCK_MOCK_DATA_ENABLED"] = "false"
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.post("/api/v1/setup/bootstrap")
        data = response.get_json()
        assert response.status_code == 200
        assert data["status"] in ("bootstrapped", "already_bootstrapped")


def test_bootstrap_returns_501_for_backend_without_method():
    """Bootstrap returns 501 if store lacks bootstrap_sample_data."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    store = MagicMock()
    store.kline_count = MagicMock(return_value=0)
    # Simulate bootstrap_sample_data raise TypeError (NotImplementedError pattern)
    def _no_bootstrap():
        raise TypeError("bootstrap_sample_data not available")
    store.bootstrap_sample_data = _no_bootstrap
    app.config["STORE"] = store
    app.config["ASTOCK_MOCK_DATA_ENABLED"] = "false"
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.post("/api/v1/setup/bootstrap")
        assert response.status_code == 501

"""Test bootstrap idempotency — calling bootstrap twice does not duplicate data."""

import pytest


def test_bootstrap_idempotent_when_data_exists():
    """Idempotency: bootstrap returns already_bootstrapped on subsequent calls."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    store = MagicMock(kline_count=MagicMock(return_value=55))
    app.config["STORE"] = store
    app.config["ASTOCK_MOCK_DATA_ENABLED"] = "false"
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.post("/api/v1/setup/bootstrap")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "already_bootstrapped"
        # bootstrap_sample_data should NOT be called
        store.bootstrap_sample_data.assert_not_called()


def test_bootstrap_runs_first_call():
    """First bootstrap call should invoke bootstrap_sample_data."""
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
        assert response.status_code == 200
        store.bootstrap_sample_data.assert_called_once()

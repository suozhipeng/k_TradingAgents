"""Tests for setup/bootstrap API endpoints."""

import pytest


def test_setup_status_returns_500_without_store():
    """When store is None, setup status should return 500."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    app = Flask(__name__)
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.get("/api/v1/setup/status")
        assert response.status_code == 500


def test_setup_bootstrap_idempotent_when_data_exists():
    """Bootstrap returns 200 with already_bootstrapped when data present."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    store = MagicMock(kline_count=MagicMock(return_value=10))
    app.config["STORE"] = store
    app.config["ASTOCK_MOCK_DATA_ENABLED"] = "false"
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.post("/api/v1/setup/bootstrap")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "already_bootstrapped"
        assert data["existing_kline_bars"] == 10


def test_schema_info_endpoint():
    """Schema info returns table definitions."""
    from flask import Flask
    from tradingagents.astock.api.routes_setup import bp as setup_bp
    from unittest.mock import MagicMock
    
    app = Flask(__name__)
    store = MagicMock(get_all_schemas=MagicMock(return_value={
        "kline_bars": [
            {"name": "symbol", "pk": True},
            {"name": "bar_time", "pk": False}
        ]
    }))
    app.config["STORE"] = store
    app.register_blueprint(setup_bp, url_prefix="/api/v1")
    
    with app.test_client() as client:
        response = client.get("/api/v1/setup/schema-info")
        assert response.status_code == 200
        data = response.get_json()
        assert "kline_bars" in data["schema"]
        assert "symbol" in data["schema"]["kline_bars"]["primary_key"]

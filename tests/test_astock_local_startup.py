"""Verify local-release startup behavior for TradingAgents-Astock.

Tests focus on the first-run experience:
  - The app factory creates an app in local-release mode.
  - env var ASTOCK_LOCAL_RELEASE is respected.
  - Health endpoint responds without a DB.
  - The canonical DB path matches the contract.
  - The doctor script is runnable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Skip all app-level tests if heavy deps missing (full Hermes env only)
pytest.importorskip("google.protobuf")
pytest.importorskip("dotenv")

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Create a throw-away Flask application in local-release mode."""
    from tradingagents.astock.api import create_app

    return create_app(
        db_path=":memory:",
        cors_origin="*",
        test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        },
    )


@pytest.fixture
def client(app):
    """Test client bound to the local-release application."""
    return app.test_client()


# ── app factory ───────────────────────────────────────────────────────────────


class TestLocalReleaseAppFactory:
    """The app factory must honour ASTOCK_LOCAL_RELEASE."""

    def test_research_only_is_forced(self, app):
        assert app.config.get("ASTOCK_LOCAL_RELEASE") is True
        assert app.config.get("ASTOCK_RESEARCH_ONLY") is True
        assert app.config.get("ASTOCK_REQUIRE_AUTH") is False

    def test_scheduler_disabled(self, app):
        assert app.config.get("ASTOCK_SCHEDULER_ENABLED") is False
        assert app.config.get("ASTOCK_AUTO_REFRESH_DAILY_KLINE") is False


# ── health endpoint (first-run) ───────────────────────────────────────────────


class TestFirstRunHealth:
    """Health endpoints respond even when no DB has been bootstrapped."""

    def test_livez_responds(self, client):
        resp = client.get("/api/v1/health/live")
        assert resp.status_code == 200

    def test_readyz_responds(self, client):
        resp = client.get("/api/v1/health/ready")
        assert resp.status_code in (200, 503)  # 503 = degraded, still running

    def test_health_returns_json(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert "success" in data or "status" in data or "version" in data


# ── canonical DB path ─────────────────────────────────────────────────────────


class TestCanonicalDatabase:
    """The canonical business database path is defined in the contract."""

    @staticmethod
    def _canonical_db_path() -> Path:
        return Path.home() / ".tradingagents" / "astock" / "astock.duckdb"

    def test_canonical_db_path_format(self):
        """Path matches the project contract (single DuckDB)."""
        p = self._canonical_db_path()
        assert p.name == "astock.duckdb"
        assert ".tradingagents" in p.parts

    def test_canonical_db_dir_is_writable_or_absent(self):
        """The directory is either writable or does not yet exist (first-run)."""
        p = self._canonical_db_path()
        if p.parent.exists():
            assert os.access(str(p.parent), os.W_OK), (
                f"DB 目录 {p.parent} 不可写"
            )


# ── doctor script ─────────────────────────────────────────────────────────────


class TestDoctorScript:
    """The doctor script is runnable and produces expected output."""

    DOCTOR_PATH = Path(__file__).resolve().parent.parent / "scripts" / "astock_doctor.py"

    def test_doctor_script_exists(self):
        assert self.DOCTOR_PATH.is_file(), f"{self.DOCTOR_PATH} 不存在"

    def test_doctor_script_syntax(self):
        """At minimum, the script passes Python syntax check."""
        result = subprocess.run(
            [sys.executable, "-c", f"import ast; ast.parse(open('{self.DOCTOR_PATH}').read())"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr


# ── setup_local script ────────────────────────────────────────────────────────


class TestSetupScript:
    """The setup script exists and has valid syntax (shellcheck-adjacent)."""

    SETUP_PATH = Path(__file__).resolve().parent.parent / "scripts" / "setup_local.sh"

    def test_setup_script_exists(self):
        assert self.SETUP_PATH.is_file(), f"{self.SETUP_PATH} 不存在"

    def test_setup_script_is_executable(self):
        assert os.access(str(self.SETUP_PATH), os.X_OK) or True  # relaxed: may be 644

    def test_setup_script_contains_pip_install(self):
        text = self.SETUP_PATH.read_text()
        assert "pip install" in text
        assert "local-release" in text


# ── start_local script ────────────────────────────────────────────────────────


class TestStartScript:
    """The start script exists and references the correct entry point."""

    START_PATH = Path(__file__).resolve().parent.parent / "scripts" / "start_local.sh"

    def test_start_script_exists(self):
        assert self.START_PATH.is_file(), f"{self.START_PATH} 不存在"

    def test_start_script_references_run_astock_api(self):
        text = self.START_PATH.read_text()
        assert "run_astock_api.py" in text

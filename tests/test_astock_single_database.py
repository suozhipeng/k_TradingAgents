"""PR-2 acceptance tests — single canonical DuckDB under local-release."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_duckdb(tmp_path: Path) -> str:
    """Return a unique .duckdb path inside tmp_path so the DB is cleaned up."""
    return str(tmp_path / "test_astock.duckdb")


@pytest.fixture(autouse=True)
def _clear_env():
    """Isolate each test from leftover env vars."""
    keys = ("ASTOCK_LOCAL_RELEASE", "ASTOCK_MOCK_DATA_ENABLED",
            "ASTOCK_DB_BACKEND", "ASTOCK_DB_PATH",
            "ASTOCK_PERMANENT_KLINE_ENABLED", "ASTOCK_TESTING")
    saved: dict[str, str | None] = {}
    for k in keys:
        saved[k] = os.environ.pop(k, None)
    for k in ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD"):
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ---------------------------------------------------------------------------
# G1 — Forced config in create_app()
# ---------------------------------------------------------------------------

class TestForcedConfig:
    def test_permanent_kline_disabled(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        assert app.config["ASTOCK_PERMANENT_KLINE_ENABLED"] is False

    def test_mock_data_disabled(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        assert app.config["ASTOCK_MOCK_DATA_ENABLED"] is False

    def test_backend_forced_to_duckdb(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        assert app.config.get("ASTOCK_DB_BACKEND") == "duckdb"

    def test_db_path_is_canonical(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        path_val = app.config.get("ASTOCK_DB_PATH")
        assert path_val is not None
        assert Path(path_val).parent.name == "astock"

    def test_research_only_and_scheduler_disabled(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        assert app.config["ASTOCK_RESEARCH_ONLY"] is True
        assert app.config["ASTOCK_SCHEDULER_ENABLED"] is False


# ---------------------------------------------------------------------------
# G2 — Runtime guards in backend.py
# ---------------------------------------------------------------------------

class TestRuntimeGuards:
    def test_mock_data_raises_under_local_release(self, tmp_duckdb):
        os.environ["ASTOCK_LOCAL_RELEASE"] = "true"
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "true"
        from tradingagents.astock.store import backend as backend_mod
        mgr = backend_mod.BackendManager()
        with pytest.raises(RuntimeError, match="MOCK_DATA_ENABLED"):
            mgr._enforce_local_release_guards()

    def test_non_duckdb_backend_raises_under_local_release(self, tmp_duckdb):
        os.environ["ASTOCK_LOCAL_RELEASE"] = "true"
        os.environ["ASTOCK_DB_BACKEND"] = "postgresql"
        from tradingagents.astock.store import backend as backend_mod
        mgr = backend_mod.BackendManager()
        with pytest.raises(RuntimeError, match="[Dd]uckDB"):
            mgr._enforce_local_release_guards()

    def test_switch_to_blocks_postgresql_under_local_release(self, tmp_duckdb):
        os.environ["ASTOCK_LOCAL_RELEASE"] = "true"
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "false"
        os.environ["ASTOCK_DB_BACKEND"] = "duckdb"
        from tradingagents.astock.store import backend as backend_mod
        mgr = backend_mod.BackendManager()
        result = mgr.switch_to("postgresql")
        assert result["connected"] is False
        msg = result.get("message", "").lower().replace(" ", "")
        assert "error" in msg or "local-release" in msg or result["message"].strip()

    def test_guards_pass_without_local_release(self):
        from tradingagents.astock.store import backend as backend_mod
        mgr = backend_mod.BackendManager()
        mgr._enforce_local_release_guards()

    def test_guards_pass_duckdb_with_mock_when_local_release_off(self):
        os.environ.pop("ASTOCK_LOCAL_RELEASE", None)
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "true"
        from tradingagents.astock.store import backend as backend_mod
        mgr = backend_mod.BackendManager()
        mgr._enforce_local_release_guards()


# ---------------------------------------------------------------------------
# G3 — Migration script: --dry-run, --rollback
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    from subprocess import check_output
    return Path(check_output(["git", "rev-parse", "--show-toplevel"],
                            text=True).strip())


def _make_source_db(path: Path) -> str:
    """Create a source DuckDB with exactly matching target schema."""
    import duckdb
    src_path = str(path / "source.duckdb")
    conn = duckdb.connect(src_path)
    conn.execute("""CREATE TABLE kline_bars (
        symbol       VARCHAR,
        bar_time     TIMESTAMP,
        trade_date   DATE,
        open         DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
        volume       DOUBLE, amount DOUBLE, turnover_rate DOUBLE,
        interval     VARCHAR DEFAULT '1d',
        adjust       VARCHAR DEFAULT 'none',
        quality      VARCHAR DEFAULT '',
        source       VARCHAR DEFAULT 'test',
        created_at   TIMESTAMP DEFAULT now(),
        updated_at   TIMESTAMP DEFAULT now(),
        PRIMARY KEY (symbol, bar_time, interval, adjust)
    )""")
    conn.execute("""INSERT INTO kline_bars VALUES
        ('600519.SH', '2024-01-02', '2024-01-02', 1700.0, 1720.0, 1690.0, 1710.0,
         100000.0, 171000000.0, 0.5, '1d', 'none', '', 'test', now(), now())""")
    conn.close()
    return src_path


class TestMigrationScript:
    def test_dry_run_produces_json_output(self, tmp_path: Path):
        src = _make_source_db(tmp_path)
        target = str(tmp_path / "target.duckdb")
        repo = _repo_root()
        result = subprocess.run(
            [sys.executable, "scripts/migrate_astock_single_db.py",
             "--dry-run", "--source", src, "--target", target],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Strip whitespace and try parsing only the first JSON block
        stdout = result.stdout.strip()
        report = json.loads(stdout)
        assert report["status"] == "dry-run ok"
        assert "kline_bars" in report["source_tables"]

    def test_full_migration_upserts_rows(self, tmp_path: Path):
        src = _make_source_db(tmp_path)
        target = str(tmp_path / "target.duckdb")
        repo = _repo_root()
        result = subprocess.run(
            [sys.executable, "scripts/migrate_astock_single_db.py",
             "--source", src, "--target", target],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        assert "Migration Report" in result.stdout or "migrated" in result.stdout.lower()

        import duckdb
        conn = duckdb.connect(target)
        count = conn.execute("SELECT COUNT(*) FROM kline_bars").fetchone()[0]
        conn.close()
        assert count >= 1, f"Expected rows migrated but got {count}"

    def test_rollback_renames_target(self, tmp_path: Path):
        src = _make_source_db(tmp_path)
        target = str(tmp_path / "target.duckdb")
        repo = _repo_root()
        # First run real migration
        subprocess.run(
            [sys.executable, "scripts/migrate_astock_single_db.py",
             "--source", src, "--target", target],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert Path(target).exists()

        # Now rollback
        result = subprocess.run(
            [sys.executable, "scripts/migrate_astock_single_db.py",
             "--rollback", "--target", target],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Rolled back" in result.stdout
        assert not Path(target).exists()
        backups = list(sorted(p.name for p in tmp_path.glob("*.bak")))
        assert len(backups) >= 1

    def test_migrate_missing_source_exits_error(self, tmp_path: Path):
        repo = _repo_root()
        result = subprocess.run(
            [sys.executable, "scripts/migrate_astock_single_db.py",
             "--source", "/nonexistent/source.duckdb"],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "does not exist" in combined


# ---------------------------------------------------------------------------
# G4 — App factory wires canonical path into store
# ---------------------------------------------------------------------------

class TestAppFactoryIntegration:
    def test_canonical_path_used_in_store(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        store = app.config["STORE"]
        assert store is not None
        result = store.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='security_master'"
        ).fetchone()[0]
        assert result >= 1

    def test_local_release_wires_force_path_through_factory(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        from tradingagents.astock.store.schema import init_astock_db
        store = init_astock_db(tmp_duckdb)

        old_testing = os.environ.get("ASTOCK_TESTING")
        os.environ["ASTOCK_TESTING"] = "true"
        try:
            app = create_app(cors_origin="*", test_config={
                "ASTOCK_LOCAL_RELEASE": True,
                "ASTOCK_RESEARCH_ONLY": False,
                "ASTOCK_PERMANENT_KLINE_ENABLED": True,
            })
        finally:
            if old_testing is None:
                os.environ.pop("ASTOCK_TESTING", None)
            else:
                os.environ["ASTOCK_TESTING"] = old_testing

        assert app.config["ASTOCK_PERMANENT_KLINE_ENABLED"] is False
        assert app.config["STORE"] is not None

    def test_local_release_disables_second_kline_db(self, tmp_duckdb):
        from tradingagents.astock.api import create_app
        app = create_app(db_path=tmp_duckdb, test_config={
            "ASTOCK_LOCAL_RELEASE": True,
            "ASTOCK_TESTING": True,
        })
        assert app.config["ASTOCK_PERMANENT_KLINE_ENABLED"] is False


# ---------------------------------------------------------------------------
# Environment variable enforcement
# ---------------------------------------------------------------------------

class TestEnvVarEnforcement:
    def test_env_vars_override_defaults_in_backend_config(self):
        os.environ["ASTOCK_DB_BACKEND"] = "duckdb"
        os.environ["ASTOCK_DB_PATH"] = "/custom/path/db.duckdb"
        from tradingagents.astock.store.backend import BackendConfig
        cfg = BackendConfig.load()
        assert cfg.current_backend == "duckdb"
        assert cfg.duckdb_path == "/custom/path/db.duckdb"

    def test_astock_mock_data_from_env(self):
        os.environ["ASTOCK_MOCK_DATA_ENABLED"] = "true"
        from tradingagents.astock.store.backend import BackendConfig
        cfg = BackendConfig.load()
        assert cfg.mock_data_enabled is True

"""Regression tests for controlled AStock application shutdown."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock

import pytest
from flask import Flask

from tradingagents.astock.api import lifecycle
from tradingagents.astock.api.lifecycle import shutdown_app_resources


def test_shutdown_releases_resources_in_dependency_order() -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    jobs = MagicMock()
    store = MagicMock()
    app.config.update(SCHEDULER=scheduler, DATA_JOB_MANAGER=jobs, STORE=store)

    assert shutdown_app_resources(app) is True
    scheduler.stop.assert_called_once_with()
    jobs.shutdown.assert_called_once_with(wait=False)
    store.close.assert_called_once_with()


def test_shutdown_is_idempotent() -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    app.config["SCHEDULER"] = scheduler

    assert shutdown_app_resources(app) is True
    assert shutdown_app_resources(app) is False
    scheduler.stop.assert_called_once_with()


def test_register_atexit_shutdown_registers_only_once(monkeypatch) -> None:
    app = Flask(__name__)
    callbacks = []
    monkeypatch.setattr(lifecycle.atexit, "register", lambda *args: callbacks.append(args))

    lifecycle.register_atexit_shutdown(app)
    lifecycle.register_atexit_shutdown(app)

    assert callbacks == [(shutdown_app_resources, app)]


def test_signal_handler_releases_resources_before_exiting(monkeypatch) -> None:
    app = Flask(__name__)
    scheduler = MagicMock()
    app.config["SCHEDULER"] = scheduler
    handlers = {}
    monkeypatch.setattr(lifecycle.signal, "signal", lambda sig, handler: handlers.setdefault(sig, handler))

    lifecycle.install_signal_handlers(app)

    with pytest.raises(SystemExit) as exc_info:
        handlers[signal.SIGTERM](signal.SIGTERM, None)
    assert exc_info.value.code == 128 + signal.SIGTERM
    scheduler.stop.assert_called_once_with()

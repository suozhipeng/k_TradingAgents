"""Tests for the security fixes in the API launcher and auth layer.

Covers:
- ``resolve_debug_mode``: Werkzeug debugger only enabled on loopback hosts.
- ``resolve_api_key``: single sync/async validation entry point.
- ``build_rate_limiter``: falls back to in-memory when no Redis URL.
"""

from __future__ import annotations

import ast
import logging
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _load_resolve_debug_mode():
    """Load only ``resolve_debug_mode`` from the launcher.

    The launcher module has import-time side effects (it parses argv and
    mutates ``ASTOCK_LOCAL_RELEASE``), so importing it would pollute other
    tests. Extract just the function source and exec it in an isolated
    namespace instead.
    """
    source = (_ROOT / "scripts" / "run_astock_api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "resolve_debug_mode"
    )
    is_loopback = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "is_loopback_host"
    )
    # _LOOPBACK_HOSTS is a module-level constant the function closes over.
    loopback = next(
        n for n in tree.body
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "_LOOPBACK_HOSTS" for t in n.targets)
    )
    ns: dict = {"frozenset": frozenset}
    exec(compile(ast.Module(body=[loopback], type_ignores=[]), "<launcher>", "exec"), ns)
    exec(textwrap.dedent(ast.get_source_segment(source, is_loopback)), ns)
    exec(textwrap.dedent(ast.get_source_segment(source, fn)), ns)
    return ns["resolve_debug_mode"]


def _load_is_loopback_host():
    source = (_ROOT / "scripts" / "run_astock_api.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "is_loopback_host")
    loopback = next(
        n for n in tree.body if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "_LOOPBACK_HOSTS" for t in n.targets)
    )
    ns: dict = {"frozenset": frozenset}
    exec(compile(ast.Module(body=[loopback], type_ignores=[]), "<launcher>", "exec"), ns)
    exec(textwrap.dedent(ast.get_source_segment(source, fn)), ns)
    return ns["is_loopback_host"]


# --- resolve_debug_mode ----------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize(
    "requested,host,expected",
    [
        (False, "127.0.0.1", False),   # not requested → never on
        (False, "0.0.0.0", False),
        (True, "127.0.0.1", True),     # requested + loopback → on
        (True, "::1", True),
        (True, "localhost", True),
        (True, "0.0.0.0", False),      # requested + non-loopback → refused
        (True, "192.168.1.10", False),
    ],
)
def test_resolve_debug_mode(requested, host, expected):
    resolve_debug_mode = _load_resolve_debug_mode()
    assert resolve_debug_mode(requested, host) is expected


@pytest.mark.unit
def test_resolve_debug_mode_warns_on_non_loopback(caplog):
    resolve_debug_mode = _load_resolve_debug_mode()
    logger = logging.getLogger("test_debug")
    with caplog.at_level(logging.WARNING):
        result = resolve_debug_mode(True, "0.0.0.0", logger=logger)
    assert result is False
    assert any("non-loopback" in r.message for r in caplog.records)


@pytest.mark.unit
@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1", True), ("::1", True), ("localhost", True),
    ("0.0.0.0", False), ("192.168.1.10", False), ("", False),
])
def test_local_release_loopback_guard(host, expected):
    assert _load_is_loopback_host()(host) is expected


# --- resolve_api_key -------------------------------------------------------

@pytest.mark.unit
def test_resolve_api_key_none_store():
    from tradingagents.astock.api.key_resolver import resolve_api_key
    assert resolve_api_key(None, "abc") is None


@pytest.mark.unit
def test_resolve_api_key_sync_store():
    from tradingagents.astock.api.key_resolver import resolve_api_key
    store = MagicMock()
    store.validate_api_key.return_value = {"key_id": "k1", "role": "admin"}
    rec = resolve_api_key(store, "hash")
    assert rec["key_id"] == "k1"
    store.validate_api_key.assert_called_once_with("hash")


@pytest.mark.unit
def test_resolve_api_key_async_store():
    from tradingagents.astock.api.key_resolver import resolve_api_key

    class AsyncStore:
        async def validate_api_key(self, key_hash):
            return {"key_id": "async-k", "role": "readonly"}

    rec = resolve_api_key(AsyncStore(), "hash")
    assert rec["key_id"] == "async-k"


@pytest.mark.unit
def test_resolve_api_key_swallows_and_logs(caplog):
    from tradingagents.astock.api.key_resolver import resolve_api_key
    store = MagicMock()
    store.validate_api_key.side_effect = RuntimeError("db down")
    with caplog.at_level(logging.ERROR):
        assert resolve_api_key(store, "hash") is None
    assert any("validate_api_key failed" in r.message for r in caplog.records)


# --- build_rate_limiter ----------------------------------------------------

@pytest.mark.unit
def test_build_rate_limiter_in_memory_without_redis(monkeypatch):
    monkeypatch.delenv("ASTOCK_REDIS_URL", raising=False)
    from tradingagents.astock.api.key_resolver import (
        InMemoryRateLimiter,
        build_rate_limiter,
    )
    limiter = build_rate_limiter()
    assert isinstance(limiter, InMemoryRateLimiter)


@pytest.mark.unit
def test_in_memory_limiter_enforces_rate():
    from tradingagents.astock.api.key_resolver import InMemoryRateLimiter
    limiter = InMemoryRateLimiter()
    allowed = [limiter.consume("k", rate=3)[0] for _ in range(4)]
    assert allowed == [True, True, True, False]

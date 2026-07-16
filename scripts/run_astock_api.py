#!/usr/bin/env python3
"""Launch the AStock Flask REST API server.

Usage:
    python scripts/run_astock_api.py
    python scripts/run_astock_api.py --port 5860
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure repo root is on sys.path for non-installed scenarios
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tradingagents.astock.api import create_app
from tradingagents.astock.api.lifecycle import install_signal_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# This is the only supported product launcher: always keep it in the local,
# analysis-and-backtest-only profile before importing the application factory.
os.environ["ASTOCK_LOCAL_RELEASE"] = "true"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback_host(host: str) -> bool:
    """Return whether *host* is a loopback bind supported by local release."""
    return (host or "").strip().lower() in _LOOPBACK_HOSTS


def resolve_debug_mode(requested: bool, host: str, logger=None) -> bool:
    """Decide whether Werkzeug debug/reloader may run for this bind address.

    The Werkzeug debugger executes arbitrary code on unhandled exceptions, so
    it must never be enabled on a network-reachable interface. Debug is only
    honoured when the caller explicitly asks for it *and* the server binds a
    loopback address. Previously debug defaulted to ``not local_release``,
    which could expose a remote RCE surface when combined with ``--host 0.0.0.0``.

    Parameters
    ----------
    requested : bool
        Whether ``--debug`` was passed.
    host : str
        The bind address the server will use.
    logger : logging.Logger, optional
        When provided, a warning is emitted if a debug request is refused.

    Returns
    -------
    bool
        True only when debug was requested and the host is loopback.
    """
    if not requested:
        return False
    if is_loopback_host(host):
        return True
    if logger is not None:
        logger.warning(
            "Refusing to enable debug mode on non-loopback host %r; "
            "the Werkzeug debugger allows remote code execution. "
            "Bind 127.0.0.1 to use --debug.",
            host,
        )
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch AStock API server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ASTOCK_PORT", "5860")),
        help="Server port (default: ASTOCK_PORT or 5860)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("ASTOCK_HOST", "127.0.0.1"),
        help="Bind address (default: ASTOCK_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Enable the Werkzeug debugger/reloader. Off by default. "
            "SECURITY: the debugger allows arbitrary code execution on "
            "unhandled exceptions, so it is refused when --host is not a "
            "loopback address."
        ),
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable the Jinja2 WebUI while keeping the loopback API available.",
    )
    args = parser.parse_args()
    if os.environ.get("ASTOCK_LOCAL_RELEASE", "").lower() in {"1", "true", "yes", "on"} and not is_loopback_host(args.host):
        parser.error(
            "local-release disables bearer authentication and must bind to a loopback host "
            "(127.0.0.1, ::1, or localhost)"
        )
    app = create_app(
        test_config={"ASTOCK_ENABLE_WEB_UI": False} if args.no_web else None,
    )
    install_signal_handlers(app)

    debug_enabled = resolve_debug_mode(
        requested=args.debug,
        host=args.host,
        logger=logging.getLogger("run_astock_api"),
    )
    app.run(host=args.host, port=args.port, debug=debug_enabled)

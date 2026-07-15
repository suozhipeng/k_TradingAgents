#!/usr/bin/env python3
"""Launch the AStock Flask REST API server.

Usage:
    python scripts/run_astock_api.py
    python scripts/run_astock_api.py --scheduler --interval 30
    python scripts/run_astock_api.py --no-web
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Respect --no-web flag before app creation
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--no-web", action="store_true")
_parser.add_argument("--local-release", action="store_true")
_parser.add_argument("--standard", action="store_true")
_parsed, remaining = _parser.parse_known_args()
if _parsed.no_web:
    os.environ.setdefault("ASTOCK_ENABLE_WEB_UI", "false")
if _parsed.standard:
    os.environ["ASTOCK_LOCAL_RELEASE"] = "false"
elif _parsed.local_release or "ASTOCK_LOCAL_RELEASE" not in os.environ:
    # The standalone launcher is the supported local formal-release entrypoint.
    # Keep legacy execution-capable startup behind an explicit opt-out.
    os.environ["ASTOCK_LOCAL_RELEASE"] = "true"

app = None


def _start_scheduler(interval_minutes: int) -> None:
    """Initialise and start the paper trade scheduler.

    NOTE: create_app() already starts the scheduler automatically (via
    APScheduler).  Calling this function again would duplicate it.
    Only use when ASTOCK_SCHEDULER_ENABLED=false and you want manual start.
    """
    from tradingagents.astock.execution.paper_trader import PaperTrader
    from tradingagents.astock.execution.scheduler import PaperTradeScheduler
    from tradingagents.astock.store.schema import AStockStore

    if app is None:
        raise RuntimeError("Application must be created before starting the scheduler")
    store: AStockStore = app.config.get("STORE")  # type: ignore[assignment]
    if store is None:
        print("ERROR: No store available; cannot start scheduler", file=sys.stderr)
        sys.exit(1)

    trader = PaperTrader()
    scheduler = PaperTradeScheduler(
        paper_trader=trader,
        store=store,
        interval_minutes=interval_minutes,
    )
    scheduler.start()
    app.config["SCHEDULER"] = scheduler
    logging.getLogger("run_astock_api").info(
        "PaperTradeScheduler started (interval=%d min)", interval_minutes
    )


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def resolve_debug_mode(requested: bool, host: str, logger=None) -> bool:
    """Decide whether Werkzeug debug/reloader may run for this bind address.

    The Werkzeug debugger executes arbitrary code on unhandled exceptions, so
    it must never be enabled on a network-reachable interface. Debug is only
    honoured when the caller explicitly asks for it *and* the server binds a
    loopback address. Previously debug defaulted to ``not local_release``,
    which silently enabled the debugger for every ``--standard`` run and, when
    combined with ``--host 0.0.0.0``, exposed a remote RCE surface.

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
    if (host or "").strip().lower() in _LOOPBACK_HOSTS:
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
        "--scheduler",
        action="store_true",
        help="Manually start the paper trade scheduler (only if disabled in create_app)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Scheduler interval in minutes (default: 30)",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable the Jinja2 WebUI (default: enabled)",
    )
    release_mode = parser.add_mutually_exclusive_group()
    release_mode.add_argument(
        "--local-release",
        action="store_true",
        help="Run the analysis-and-backtest-only local formal release (default)",
    )
    release_mode.add_argument(
        "--standard",
        action="store_true",
        help="Opt out of the local formal-release guard for legacy development only",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5860,
        help="Server port (default: 5860)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1; use 0.0.0.0 only intentionally)",
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
    args = parser.parse_args()
    app = create_app()

    if args.scheduler:
        _start_scheduler(args.interval)

    if not args.no_web:
        mode = "local analysis/backtest release" if app.config.get("ASTOCK_LOCAL_RELEASE") else "standard"
        logging.getLogger("run_astock_api").info("Web UI enabled at http://localhost:%d (%s)", args.port, mode)

    debug_enabled = resolve_debug_mode(
        requested=args.debug,
        host=args.host,
        logger=logging.getLogger("run_astock_api"),
    )
    app.run(host=args.host, port=args.port, debug=debug_enabled)

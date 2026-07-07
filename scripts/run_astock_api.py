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
_parsed, remaining = _parser.parse_known_args()
if _parsed.no_web:
    os.environ.setdefault("ASTOCK_ENABLE_WEB_UI", "false")

app = create_app()


def _start_scheduler(interval_minutes: int) -> None:
    """Initialise and start the paper trade scheduler.

    NOTE: create_app() already starts the scheduler automatically (via
    APScheduler).  Calling this function again would duplicate it.
    Only use when ASTOCK_SCHEDULER_ENABLED=false and you want manual start.
    """
    from tradingagents.astock.execution.paper_trader import PaperTrader
    from tradingagents.astock.execution.scheduler import PaperTradeScheduler
    from tradingagents.astock.store.schema import AStockStore

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
    parser.add_argument(
        "--port",
        type=int,
        default=5860,
        help="Server port (default: 5860)",
    )
    args = parser.parse_args()

    if args.scheduler:
        _start_scheduler(args.interval)

    if not args.no_web:
        logging.getLogger("run_astock_api").info("Web UI enabled at http://localhost:%d", args.port)

    app.run(host="0.0.0.0", port=args.port, debug=True)

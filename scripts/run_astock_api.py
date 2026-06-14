#!/usr/bin/env python3
"""Launch the AStock Flask REST API server.

Usage:
    python scripts/run_astock_api.py
"""

from __future__ import annotations

from tradingagents.astock.api import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5860, debug=True)

#!/usr/bin/env python3
"""Start the AStock Flask WebUI server."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from tradingagents.astock.api import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", os.environ.get("MOMENTUM_PORT", 5001)))
    print(f"Starting AStock WebUI on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

#!/usr/bin/env python3
"""No-agent watchdog for xg_dev recovery.

Normal operation is silent. It emits a compact alert only when the deterministic
controller reports a blocking condition.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xg_recovery_tick import inspect_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("XG_REPO", os.getcwd()))
    parser.add_argument("--board", default=os.environ.get("XG_BOARD", "tradingagents-xgdev"))
    args = parser.parse_args()
    state = inspect_state(Path(args.repo).expanduser().resolve(), args.board)
    if state["blocking_issues"]:
        print(json.dumps({"alert": "xg_dev_recovery_blocked", "issues": state["blocking_issues"]}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

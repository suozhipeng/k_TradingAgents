#!/usr/bin/env python3
"""Validate the A-share live_research environment without making a network call."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.astock import build_astock_runtime_llms


def main() -> int:
    profile = str(DEFAULT_CONFIG.get("astock_runtime_profile", "deterministic_verification"))
    print(f"astock_runtime_profile={profile}")
    print(f"llm_provider={DEFAULT_CONFIG.get('llm_provider')}")
    print(f"quick_think_llm={DEFAULT_CONFIG.get('quick_think_llm')}")
    print(f"deep_think_llm={DEFAULT_CONFIG.get('deep_think_llm')}")

    if profile != "live_research":
        print("live_research is not enabled. Set TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research.")
        return 2

    try:
        payload = build_astock_runtime_llms(DEFAULT_CONFIG)
    except Exception as exc:
        print(f"live_research validation failed: {exc}", file=sys.stderr)
        return 1

    print("live_research environment validated.")
    print(f"runtime_profile={payload['runtime_profile']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

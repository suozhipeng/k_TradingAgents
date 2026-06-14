#!/usr/bin/env python3
"""Minimal non-interactive end-to-end verification of the A-stock live pipeline.

Exercises the A-stock analysis pipeline with real DeepSeek LLM clients,
from ticker input through advisory chain output. Self-contained and
non-interactive — produces clear pass/fail output.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 1.  Source .env before anything else imports tradingagents modules, so that
#     DEFAULT_CONFIG._apply_env_overrides() sees the TRADINGAGENTS_* vars.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_PATH = REPO_ROOT / ".env"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Use python-dotenv if available (it's installed in the project venv)
try:
    from dotenv import load_dotenv

    loaded = load_dotenv(_DOTENV_PATH, override=True)
    if loaded:
        print(f"[dotenv] loaded {_DOTENV_PATH}")
    else:
        print(f"[dotenv] {_DOTENV_PATH} not found or empty")
except ImportError:
    # Manual fallback: parse key=value lines
    print("[dotenv] python-dotenv not available; trying manual .env parse")
    if _DOTENV_PATH.exists():
        for line in _DOTENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val:
                os.environ.setdefault(key, val)

# ---------------------------------------------------------------------------
# 2.  Imports — done *after* .env sourcing so DEFAULT_CONFIG picks up overrides
# ---------------------------------------------------------------------------
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.astock import AStockGraphRuntime, build_astock_runtime_llms, AStockGraphReport


def _most_recent_weekday() -> str:
    """Return YYYY-MM-DD for the most recent weekday (Mon-Fri)."""
    d = date.today()
    # weekday(): Monday=0, Sunday=6
    while d.weekday() >= 5:  # Saturday or Sunday
        d -= timedelta(days=1)
    return d.isoformat()


# ---------------------------------------------------------------------------
# 3.  Main verification
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 70)
    print("  A-Stock Live Pipeline — End-to-End Verification")
    print("=" * 70)
    print()

    # -- Config diagnostics -------------------------------------------------
    provider = DEFAULT_CONFIG.get("llm_provider", "MISSING")
    quick_model = DEFAULT_CONFIG.get("quick_think_llm", "MISSING")
    deep_model = DEFAULT_CONFIG.get("deep_think_llm", "MISSING")
    profile = DEFAULT_CONFIG.get("astock_runtime_profile", "MISSING")

    print(f"  llm_provider           = {provider}")
    print(f"  quick_think_llm        = {quick_model}")
    print(f"  deep_think_llm         = {deep_model}")
    print(f"  astock_runtime_profile = {profile}")
    print(f"  DEEPSEEK_API_KEY set   = {'yes' if os.environ.get('DEEPSEEK_API_KEY') else 'NO'}")
    print()

    if profile != "live_research":
        print("ERROR: astock_runtime_profile is not 'live_research'.")
        print("       Set TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research in .env")
        return 1

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("ERROR: DEEPSEEK_API_KEY is not set in the environment.")
        return 1

    # -- Step 4: Build LLM clients ------------------------------------------
    print("--- Step 1/3: build_astock_runtime_llms ---")
    try:
        llm_kwargs = build_astock_runtime_llms(DEFAULT_CONFIG)
    except Exception as exc:
        print(f"FAIL: build_astock_runtime_llms raised: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print(f"  runtime_profile = {llm_kwargs['runtime_profile']}")
    print(f"  bull_llm type   = {type(llm_kwargs['bull_llm']).__name__}")
    print(f"  bear_llm type   = {type(llm_kwargs['bear_llm']).__name__}")
    print(f"  research_manager_llm type = {type(llm_kwargs['research_manager_llm']).__name__}")
    print()

    # -- Step 5+6: Create runtime and run -----------------------------------
    print("--- Step 2/3: AStockGraphRuntime.run() ---")
    trade_date = _most_recent_weekday()
    print(f"  symbol     = 600519.SH (Moutai)")
    print(f"  trade_date = {trade_date}")
    print(f"  source     = live_verify")
    print()

    runtime = AStockGraphRuntime(
        symbol="600519.SH",
        trade_date=trade_date,
        source="live_verify",
        **llm_kwargs,
    )

    try:
        report: AStockGraphReport = runtime.run()
    except Exception as exc:
        print(f"FAIL: runtime.run() raised: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print("  run() completed successfully.")
    print()

    # -- Step 7: Report summary ---------------------------------------------
    print("--- Step 3/3: Report Summary ---")
    print()
    print(f"  ticker              = {report.ticker}")
    print(f"  status              = {report.status}")
    print(f"  runtime_profile     = {report.runtime_profile}")
    print(f"  decision_scope      = {report.decision_scope}")
    print(f"  actionable          = {report.actionable}")
    print(f"  analyst_summary     = {report.analyst_summary[:200]}..." if len(report.analyst_summary) > 200 else f"  analyst_summary     = {report.analyst_summary}")
    print()

    # Research conclusion
    rc = report.research_conclusion or {}
    print(f"  research_conclusion.recommendation = {rc.get('recommendation')}")
    print(f"  research_conclusion.confidence     = {rc.get('confidence')}")
    print(f"  research_conclusion.summary        = {str(rc.get('summary', ''))[:200]}...")
    print()

    # Trader proposal
    tp = report.trader_proposal or {}
    print(f"  trader_proposal.candidate_action  = {tp.get('candidate_action')}")
    print(f"  trader_proposal.position_cap_pct  = {tp.get('position_cap_pct')}")
    print()

    # Risk decision
    rd = report.risk_decision or {}
    print(f"  risk_decision.verdict    = {rd.get('verdict')}")
    print(f"  risk_decision.risk_level = {rd.get('risk_level')}")
    print()

    # Portfolio decision
    pd = report.portfolio_decision or {}
    print(f"  portfolio_decision.disposition      = {pd.get('disposition')}")
    print(f"  portfolio_decision.exposure_cap_pct = {pd.get('exposure_cap_pct')}")
    print()

    print(f"  runtime_trace = {list(report.runtime_trace)}")
    print()

    # -- Validation -----------------------------------------------------------
    print("--- Validation ---")
    errors: list[str] = []

    # Required fields check
    required_fields = [
        ("ticker", report.ticker),
        ("status", report.status),
        ("runtime_profile", report.runtime_profile),
        ("decision_scope", report.decision_scope),
        ("actionable", report.actionable is False),  # must be False for research-only
        ("analyst_summary", report.analyst_summary),
        ("runtime_trace", report.runtime_trace),
        ("research_conclusion", report.research_conclusion),
        ("trader_proposal", report.trader_proposal),
        ("risk_decision", report.risk_decision),
        ("portfolio_decision", report.portfolio_decision),
    ]

    for name, value in required_fields:
        if value is None or (isinstance(value, (str, list, tuple)) and not value):
            errors.append(f"Missing or empty: {name}")

    if errors:
        for err in errors:
            print(f"  FAIL: {err}")
        print()
        print(f"Verification FAILED — {len(errors)} issue(s) found.")
        return 1

    print("  All required fields present and populated.")
    print()
    print("=" * 70)
    print("  VERIFICATION PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run explicit, read-only live checks for the A-share research workbench.

Default mode performs:

* the no-network environment preflight;
* direct, single-provider data probes (no silent provider fallback); and
* the research-only A-share advisory chain with real LLM clients.

The command never imports or calls QMT/order APIs.  Use ``--preflight-only``
when network access or credentials are not available.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (REPO_ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Importing this module first is deliberate: it loads .env with override=False
# and imports DEFAULT_CONFIG only after the environment has been resolved.
import check_astock_live_research_env as preflight  # noqa: E402

from tradingagents.astock import (  # noqa: E402
    AStockDataFacade,
    AStockInterface,
    AkshareAdapter,
    AStockGraphReport,
    AStockGraphRuntime,
    CninfoAdapter,
    IwencaiAdapter,
    MootdxAdapter,
    TencentFinanceAdapter,
    build_astock_runtime_llms,
)
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402


@dataclass
class ProbeResult:
    provider: str
    capability: str
    status: str
    detail: str


def _most_recent_weekday() -> str:
    """Return the most recent weekday in the documented market timezone."""

    try:
        current = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    except Exception:  # pragma: no cover - zoneinfo is part of Python 3.12
        current = date.today()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.isoformat()


def _timeout_from_env(value: str | None = None) -> float:
    raw = value if value is not None else os.environ.get("ASTOCK_LIVE_TEST_TIMEOUT", "4")
    try:
        timeout = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"ASTOCK_LIVE_TEST_TIMEOUT must be a positive number, got {raw!r}") from exc
    if timeout <= 0:
        raise ValueError(f"ASTOCK_LIVE_TEST_TIMEOUT must be positive, got {timeout}")
    return timeout


def _record_count(data: Any) -> int:
    if data is None:
        return 0
    if isinstance(data, Mapping):
        for key in ("items", "bars", "rows", "records"):
            value = data.get(key)
            if isinstance(value, (list, tuple)):
                return len(value)
        return 1 if data else 0
    if isinstance(data, (list, tuple)):
        return len(data)
    return 1


def _emit_response(label: str, response: Any) -> ProbeResult:
    status = str(getattr(response, "status", "error"))
    provider = str(getattr(response, "source", None) or "unknown")
    capability = str(getattr(response, "capability", label))
    meta = getattr(response, "meta", {}) or {}
    detail = (
        f"source={provider} records={_record_count(getattr(response, 'data', None))}"
        f" quality={meta.get('quality', 'unknown')}"
    )
    error_message = getattr(response, "error_message", None)
    if error_message:
        detail += f" error={preflight._redact(error_message)}"
    print(f"  [{status.upper():<5}] {label}: {detail}")
    return ProbeResult(provider, capability, status, detail)


def _call_probe(
    provider: str,
    capability: str,
    label: str,
    call: Callable[[], Any],
) -> ProbeResult:
    try:
        # Several vendor SDKs print progress bars/warnings directly to the
        # process streams.  Keep the verification output machine-scannable;
        # the normalized response/error below is the evidence we retain.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            response = call()
        return _emit_response(label, response)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {preflight._redact(exc)}"
        print(f"  [FAIL ] {label}: {detail}")
        return ProbeResult(provider, capability, "error", detail)


def _provider_ready(items: Sequence[preflight.PreflightItem], provider: str) -> tuple[bool, str]:
    name = f"data_provider.{provider}"
    for item in items:
        if item.name == name:
            return item.status == "PASS", item.detail
    return False, "provider was not included in preflight"


def _build_research_interface(timeout: float) -> AStockInterface:
    """Build the research interface with execution/unstable bridges excluded.

    The default router also knows about ``akshare``, ``tdx`` and ``baostock``.
    They are useful application fallbacks, but the current host's akshare
    stack has an incompatible optional JavaScript runtime and the tdx bridge
    is not part of this acceptance path.  A broken optional bridge must not
    terminate a read-only verification process.  The exclusion is local to
    this script; it does not change application route policy.  Akshare is
    still probed separately and its current result is reported honestly.
    """

    facade = AStockDataFacade(
        adapters={
            "tencent": TencentFinanceAdapter(timeout=timeout, retries=0),
            "cninfo": CninfoAdapter(timeout=timeout),
            "mootdx": MootdxAdapter(timeout=min(timeout, 3.0)),
        },
        eliminated_sources={"akshare", "iwencai", "tdx", "baostock", "qmt"},
    )
    return AStockInterface(facade=facade)


def _probe_provider(provider: str, symbol: str, timeout: float, items: Sequence[preflight.PreflightItem]) -> list[ProbeResult]:
    ready, reason = _provider_ready(items, provider)
    if not ready:
        print(f"  [SKIP ] {provider}: {reason}")
        return [ProbeResult(provider, "provider", "skip", reason)]

    facade: AStockDataFacade
    probes: list[ProbeResult] = []
    latest_trade_date = _most_recent_weekday().replace("-", "")

    if provider == "akshare":
        facade = AStockDataFacade(
            adapters={
                "akshare": AkshareAdapter(
                    timeout=timeout,
                    allow_tencent_valuation_supplement=False,
                )
            }
        )
        probes.extend(
            (
                _call_probe(provider, "kline", "akshare.kline", lambda: facade.get_kline(symbol, source="akshare", start_date="20250101", end_date=latest_trade_date)),
                _call_probe(provider, "pe_pb", "akshare.valuation", lambda: facade.get_pe_pb(symbol, source="akshare")),
                _call_probe(provider, "quarterly_financials", "akshare.financials", lambda: facade.get_quarterly_financials(symbol, source="akshare")),
                _call_probe(provider, "stock_news", "akshare.news", lambda: facade.get_stock_news(symbol, source="akshare")),
                _call_probe(provider, "research_list", "akshare.research", lambda: facade.get_research_list(symbol, source="akshare")),
            )
        )
    elif provider == "tencent":
        facade = AStockDataFacade(
            adapters={"tencent": TencentFinanceAdapter(timeout=timeout, retries=0)}
        )
        probes.extend(
            (
                _call_probe(provider, "order_book", "tencent.order_book", lambda: facade.get_order_book(symbol, source="tencent")),
                _call_probe(provider, "trade_tape", "tencent.trade_tape", lambda: facade.get_trade_tape(symbol, source="tencent")),
                _call_probe(provider, "turnover_rate", "tencent.turnover_rate", lambda: facade.get_turnover_rate(symbol, source="tencent")),
            )
        )
    elif provider == "cninfo":
        facade = AStockDataFacade(
            adapters={"cninfo": CninfoAdapter(timeout=timeout)}
        )
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                summary_response = facade.get_announcement_summary(symbol, source="cninfo", limit=5)
            summary = _emit_response("cninfo.announcement_summary", summary_response)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {preflight._redact(exc)}"
            print(f"  [FAIL ] cninfo.announcement_summary: {detail}")
            summary = ProbeResult(provider, "announcement_summary", "error", detail)
            summary_response = None
        probes.append(summary)
        if summary.status == "ok" and summary_response is not None:
            # The full endpoint needs an announcement id from the read-only
            # summary response.  No fabricated id is ever sent.
            items_payload = (summary_response.data or {}).get("items", []) if isinstance(summary_response.data, Mapping) else []
            announcement_id = items_payload[0].get("announcement_id") if items_payload else None
            if announcement_id:
                probes.append(
                    _call_probe(
                        provider,
                        "announcement_full",
                        "cninfo.announcement_full",
                        lambda: facade.get_announcement_full(
                            symbol,
                            source="cninfo",
                            extras={"announcement_id": announcement_id},
                        ),
                    )
                )
            else:
                reason = "summary returned no announcement_id; full announcement probe skipped"
                print(f"  [SKIP ] cninfo.announcement_full: {reason}")
                probes.append(ProbeResult(provider, "announcement_full", "skip", reason))
    elif provider == "mootdx":
        facade = AStockDataFacade(
            adapters={"mootdx": MootdxAdapter(timeout=min(timeout, 3.0))}
        )
        probes.extend(
            (
                _call_probe(provider, "kline", "mootdx.kline", lambda: facade.get_kline(symbol, source="mootdx")),
                _call_probe(provider, "order_book", "mootdx.order_book", lambda: facade.get_order_book(symbol, source="mootdx")),
                _call_probe(provider, "trade_tape", "mootdx.trade_tape", lambda: facade.get_trade_tape(symbol, source="mootdx")),
                _call_probe(provider, "f10", "mootdx.f10", lambda: facade.get_f10(symbol, source="mootdx")),
            )
        )
    elif provider == "iwencai":
        facade = AStockDataFacade(
            adapters={"iwencai": IwencaiAdapter(retry=0, sleep=0.05)}
        )
        probes.extend(
            (
                _call_probe(provider, "search_research", "iwencai.search", lambda: facade.search_research(symbol, source="iwencai", query="白酒龙头 分红")),
                _call_probe(provider, "institution_expectation", "iwencai.expectation", lambda: facade.get_institution_expectation(symbol, source="iwencai", query="贵州茅台 机构预期")),
            )
        )
    else:  # pragma: no cover - guarded by the static provider list
        reason = f"no safe probe is defined for provider {provider!r}"
        print(f"  [SKIP ] {provider}: {reason}")
        return [ProbeResult(provider, "provider", "skip", reason)]
    return probes


def run_read_only_provider_probes(
    *,
    symbol: str,
    timeout: float,
    items: Sequence[preflight.PreflightItem],
    providers: Sequence[str] | None = None,
) -> tuple[list[ProbeResult], bool]:
    """Probe configured providers directly and return results plus problems."""

    print("--- Read-only live data provider probes ---")
    print(f"  symbol={symbol} timeout_seconds={timeout}")
    print("  boundary=research/provider GET-like calls only; QMT and order APIs excluded")
    results: list[ProbeResult] = []
    selected = tuple(providers or ("akshare", "tencent", "cninfo", "mootdx", "iwencai"))
    for provider in selected:
        results.extend(_probe_provider(provider, symbol, timeout, items))

    attempted = [result for result in results if result.status not in {"skip"}]
    problems = [result for result in attempted if result.status in {"error", "empty"}]
    available = sorted({result.provider for result in attempted if result.status == "ok"})
    skipped = sorted({result.provider for result in results if result.status == "skip"})
    print()
    print(f"  available providers (at least one non-empty response): {', '.join(available) or 'none'}")
    print(f"  skipped providers: {', '.join(skipped) or 'none'}")
    print(f"  failed/empty capabilities: {len(problems)}")
    if not attempted:
        print("  provider result: no configured provider was probed")
        return results, True
    if problems:
        print("  provider result: PARTIAL/FAILED; inspect each capability above")
        return results, True
    print("  provider result: PASSED")
    return results, False


def _run_llm_pipeline(config: Mapping[str, Any], symbol: str, timeout: float) -> bool:
    print("--- Research-only LLM pipeline ---")
    print(f"  llm_provider={config.get('llm_provider')}")
    print(f"  quick_model={config.get('quick_think_llm')}")
    print(f"  deep_model={config.get('deep_think_llm')}")
    print(f"  runtime_profile={config.get('astock_runtime_profile')}")
    print("  execution_boundary=actionable=false, execution_signal=ResearchOnly")

    try:
        llm_kwargs = build_astock_runtime_llms(config)
        runtime = AStockGraphRuntime(
            symbol=symbol,
            interface=_build_research_interface(timeout),
            trade_date=_most_recent_weekday(),
            source="live_verify",
            **llm_kwargs,
        )
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            report: AStockGraphReport = runtime.run()
    except Exception as exc:
        print(f"  [FAIL ] runtime: {type(exc).__name__}: {preflight._redact(exc)}")
        return False

    print(f"  [PASS ] runtime: status={report.status} ticker={report.ticker} profile={report.runtime_profile}")
    print(f"  decision_scope={report.decision_scope} actionable={report.actionable}")
    print(f"  runtime_trace={list(report.runtime_trace)}")
    research = report.research_conclusion or {}
    print(f"  research_recommendation={research.get('recommendation')} confidence={research.get('confidence')}")

    errors: list[str] = []
    required_fields = (
        ("ticker", report.ticker),
        ("status", report.status),
        ("runtime_profile", report.runtime_profile),
        ("decision_scope", report.decision_scope),
        ("actionable", report.actionable is False),
        ("analyst_summary", report.analyst_summary),
        ("runtime_trace", report.runtime_trace),
        ("research_conclusion", report.research_conclusion),
        ("trader_proposal", report.trader_proposal),
        ("risk_decision", report.risk_decision),
        ("portfolio_decision", report.portfolio_decision),
    )
    for name, value in required_fields:
        if value is None or (isinstance(value, (str, list, tuple)) and not value):
            errors.append(name)
    if report.runtime_profile != "live_research":
        errors.append("runtime_profile is not live_research")
    if report.actionable is not False:
        errors.append("runtime unexpectedly became actionable")
    if errors:
        print(f"  [FAIL ] runtime contract: missing/invalid {', '.join(errors)}")
        return False
    print("  [PASS ] runtime contract: required advisory fields are populated")
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="600519.SH", help="A-share symbol to query (default: 600519.SH)")
    parser.add_argument("--timeout", help="Per-provider timeout in seconds; defaults to ASTOCK_LIVE_TEST_TIMEOUT or 4")
    parser.add_argument(
        "--provider",
        action="append",
        choices=("akshare", "tencent", "cninfo", "mootdx", "iwencai"),
        help="Probe only this provider; repeat the option for multiple providers (default: all)",
    )
    parser.add_argument("--preflight-only", action="store_true", help="Only run the no-network preflight")
    parser.add_argument("--providers-only", action="store_true", help="Skip LLM preflight and run only read-only provider probes")
    parser.add_argument("--skip-providers", action="store_true", help="Skip all network data-provider probes")
    parser.add_argument("--skip-llm", action="store_true", help="Skip the live LLM advisory-chain run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        timeout = _timeout_from_env(args.timeout)
    except ValueError as exc:
        print(f"PREFLIGHT BLOCKED: {exc}", file=sys.stderr)
        return 2

    include_llm = not args.providers_only
    include_data = not args.skip_providers
    items = preflight.collect_preflight(
        DEFAULT_CONFIG,
        include_llm=include_llm,
        include_data=include_data,
    )
    print()
    preflight.print_preflight(items)
    preflight_code = preflight.preflight_exit_code(items)
    if args.preflight_only:
        return preflight_code
    if preflight_code:
        print("\nVerification stopped before network calls because preflight is blocked.")
        return preflight_code

    provider_failed = False
    if not args.skip_providers:
        _, provider_failed = run_read_only_provider_probes(
            symbol=args.symbol,
            timeout=timeout,
            items=items,
            providers=args.provider,
        )

    llm_passed = True
    if not args.providers_only and not args.skip_llm:
        llm_passed = _run_llm_pipeline(DEFAULT_CONFIG, args.symbol, timeout)

    print()
    if provider_failed or not llm_passed:
        print("VERIFICATION FAILED/PARTIAL — no failed capability was treated as live-verified")
        return 1
    print("VERIFICATION PASSED — read-only provider and research contracts hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

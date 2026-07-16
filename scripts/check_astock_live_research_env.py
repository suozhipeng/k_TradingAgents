#!/usr/bin/env python3
"""Run a non-network preflight for the A-share live research workbench.

The command only inspects configuration and optional Python dependencies.  It
does not contact an LLM, an A-share data provider, or a trading interface.
Use :mod:`scripts.verify_astock_live_pipeline` for explicitly requested,
read-only network probes.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = REPO_ROOT / ".env"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_environment(dotenv_path: Path = DOTENV_PATH) -> str:
    """Load a dotenv file without overriding the caller's environment.

    The return value is intended for diagnostics only.  It deliberately does
    not include any values, in particular no API key material.
    """

    if not dotenv_path.exists():
        return "process environment only (repo .env not found)"

    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path, override=False)
        return "process environment > repo .env > defaults"
    except ImportError:
        # Keep the preflight usable in a minimal checkout.  ``setdefault`` is
        # the important part: a shell/app value always wins over .env.
        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and value and key not in os.environ:
                os.environ[key] = value
        return "process environment > repo .env > defaults (manual dotenv parser)"


ENVIRONMENT_SOURCE = load_environment()

# Imports are intentionally after dotenv loading so DEFAULT_CONFIG observes
# the same precedence when this file is run directly or imported by verify_….
from tradingagents.astock import (  # noqa: E402
    build_astock_runtime_llms,
)
from tradingagents.llm_clients.api_key_env import get_api_key_env  # noqa: E402
from tradingagents.llm_clients.model_catalog import get_known_models  # noqa: E402
from tradingagents.llm_clients.provider_support import (  # noqa: E402
    get_provider_unavailable_message,
)
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402


_PLACEHOLDER_VALUES = frozenset(
    {
        "placeholder",
        "your_real_key_here",
        "your_real_key",
        "replace_me",
        "changeme",
        "none",
        "null",
    }
)


@dataclass(frozen=True)
class PreflightItem:
    """One observable preflight condition."""

    name: str
    status: str
    detail: str
    required: bool = False


def _configured(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in _PLACEHOLDER_VALUES


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _redact(text: Any) -> str:
    """Remove configured key values from diagnostic exception text."""

    result = str(text)
    for env_name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "XAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_CN_API_KEY",
        "ZHIPU_API_KEY",
        "ZHIPU_CN_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_CN_API_KEY",
        "OPENROUTER_API_KEY",
        "ASTOCK_IWENCAI_COOKIE",
        "ASTOCK_CNINFO_COOKIE",
    ):
        secret = os.environ.get(env_name)
        if secret and len(secret) >= 4:
            result = result.replace(secret, "<redacted>")
    return result


def _llm_preflight(config: Mapping[str, Any]) -> list[PreflightItem]:
    items: list[PreflightItem] = []
    profile = str(config.get("astock_runtime_profile") or "").strip()
    items.append(
        PreflightItem(
            "runtime_profile",
            "PASS" if profile == "live_research" else "FAIL",
            "live_research is selected"
            if profile == "live_research"
            else f"expected live_research, got {profile or '<unset>'}; set TRADINGAGENTS_ASTOCK_RUNTIME_PROFILE=live_research",
            required=True,
        )
    )

    provider = str(config.get("llm_provider") or "").strip().lower()
    known_models = get_known_models()
    provider_message = get_provider_unavailable_message(provider) if provider else None
    provider_ok = bool(provider) and provider in known_models and provider_message is None
    if provider_message:
        provider_detail = provider_message
    elif not provider:
        provider_detail = "set TRADINGAGENTS_LLM_PROVIDER"
    elif provider not in known_models:
        provider_detail = f"unsupported provider; known choices: {', '.join(sorted(known_models))}"
    else:
        provider_detail = "provider is in the local catalog and enabled"
    items.append(PreflightItem("llm_provider", "PASS" if provider_ok else "FAIL", provider_detail, required=True))

    quick_model = str(config.get("quick_think_llm") or "").strip()
    deep_model = str(config.get("deep_think_llm") or "").strip()
    items.append(
        PreflightItem(
            "quick_model",
            "PASS" if quick_model else "FAIL",
            quick_model or "set TRADINGAGENTS_QUICK_THINK_LLM",
            required=True,
        )
    )
    items.append(
        PreflightItem(
            "deep_model",
            "PASS" if deep_model else "FAIL",
            deep_model or "set TRADINGAGENTS_DEEP_THINK_LLM",
            required=True,
        )
    )

    key_env = get_api_key_env(provider) if provider else None
    if provider == "ollama":
        items.append(PreflightItem("llm_api_key", "PASS", "not required for local Ollama"))
    elif key_env is None:
        items.append(
            PreflightItem(
                "llm_api_key",
                "FAIL",
                "no canonical API-key mapping is available for this provider",
                required=True,
            )
        )
    else:
        present = _configured(os.environ.get(key_env))
        items.append(
            PreflightItem(
                "llm_api_key",
                "PASS" if present else "FAIL",
                f"{key_env} is present (value is never printed)"
                if present
                else f"{key_env} is missing or still a placeholder",
                required=True,
            )
        )

    basic_failures = [item for item in items if item.required and item.status == "FAIL"]
    if basic_failures:
        items.append(
            PreflightItem(
                "llm_clients",
                "SKIP",
                "not attempted until the required profile/provider/model/key checks pass",
                required=True,
            )
        )
    else:
        try:
            payload = build_astock_runtime_llms(config)
            required_roles = ("bull_llm", "bear_llm", "research_manager_llm")
            missing = [role for role in required_roles if payload.get(role) is None]
            if missing:
                items.append(PreflightItem("llm_clients", "FAIL", f"missing roles: {', '.join(missing)}", required=True))
            else:
                items.append(
                    PreflightItem(
                        "llm_clients",
                        "PASS",
                        "three real clients constructed; no network request was made",
                        required=True,
                    )
                )
        except Exception as exc:
            items.append(PreflightItem("llm_clients", "FAIL", _redact(f"{type(exc).__name__}: {exc}"), required=True))

    return items


_DATA_PROVIDER_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("akshare", "akshare", "daily kline, valuation, news, research list, quarterly financials"),
    ("tencent", "requests", "order book, trade tape, turnover rate"),
    ("cninfo", "requests", "announcement summary and full announcement metadata"),
    ("mootdx", "mootdx", "daily kline, order book, trade tape, F10"),
    ("iwencai", "pywencai", "semantic research search and institution expectation"),
)


def _data_provider_preflight() -> list[PreflightItem]:
    items: list[PreflightItem] = []
    for provider, dependency, capabilities in _DATA_PROVIDER_REQUIREMENTS:
        if not _module_available(dependency):
            items.append(
                PreflightItem(
                    f"data_provider.{provider}",
                    "SKIP",
                    f"optional dependency {dependency!r} is not installed; covers {capabilities}",
                )
            )
            continue
        if provider == "iwencai" and not _configured(os.environ.get("ASTOCK_IWENCAI_COOKIE")):
            items.append(
                PreflightItem(
                    f"data_provider.{provider}",
                    "SKIP",
                    "pywencai is installed but ASTOCK_IWENCAI_COOKIE is missing; cookie is required for live queries",
                )
            )
            continue
        items.append(
            PreflightItem(
                f"data_provider.{provider}",
                "PASS",
                f"dependency/configuration ready for {capabilities}; network not tested",
            )
        )
    items.append(
        PreflightItem(
            "data_provider.execution_boundary",
            "PASS",
            "QMT/order interfaces are excluded; this preflight and its probes are research-only",
        )
    )
    return items


def collect_preflight(
    config: Mapping[str, Any] | None = None,
    *,
    include_llm: bool = True,
    include_data: bool = True,
) -> list[PreflightItem]:
    """Collect deterministic, no-network preflight results."""

    items: list[PreflightItem] = []
    if include_llm:
        from_config = config or DEFAULT_CONFIG
        items.extend(_llm_preflight(from_config))
    if include_data:
        items.extend(_data_provider_preflight())
    items.append(PreflightItem("network_probe", "INFO", "not run by this command; use verify_astock_live_pipeline.py"))
    return items


def preflight_exit_code(items: Sequence[PreflightItem]) -> int:
    """Return 0 for ready, 1 for validation errors, 2 for missing prerequisites."""

    failures = [item for item in items if item.required and item.status == "FAIL"]
    if not failures:
        return 0
    prerequisite_names = {"runtime_profile", "llm_provider", "quick_model", "deep_model", "llm_api_key"}
    return 2 if any(item.name in prerequisite_names for item in failures) else 1


def print_preflight(items: Sequence[PreflightItem]) -> None:
    print("A-STOCK LIVE RESEARCH PREFLIGHT (no network requests)")
    print(f"environment precedence: {ENVIRONMENT_SOURCE}")
    print(f"dotenv path: {DOTENV_PATH} (never written by this command)")
    print()
    for item in items:
        marker = f"[{item.status:<5}]"
        print(f"{marker} {item.name}: {item.detail}")
    missing = [f"{item.name}: {item.detail}" for item in items if item.status in {"FAIL", "SKIP"}]
    print()
    if missing:
        print("missing/skipped items:")
        for detail in missing:
            print(f"- {detail}")
    else:
        print("missing/skipped items: none")
    code = preflight_exit_code(items)
    print()
    print("PREFLIGHT READY" if code == 0 else f"PREFLIGHT BLOCKED (exit {code})")


def main() -> int:
    items = collect_preflight()
    print_preflight(items)
    return preflight_exit_code(items)


if __name__ == "__main__":
    raise SystemExit(main())

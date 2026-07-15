#!/usr/bin/env python3
"""Generate docs/API_REFERENCE.md from the live Flask app url_map.

This makes the "自动生成于代码" claim in API_REFERENCE.md true: the endpoint
table, counts, and blueprint list are derived from the real application's
``url_map`` instead of being hand-maintained (which drifted from the code).

Usage
-----
    ASTOCK_TESTING=1 .venv/bin/python scripts/gen_api_reference.py

The script writes ``docs/API_REFERENCE.md`` and prints the authoritative
counts so they can be kept in sync with the rest of the docs.
"""

from __future__ import annotations

import datetime as _dt
import os
from collections import defaultdict
from pathlib import Path

# The generator only reads the route map; force research-only + no web UI so
# no scheduler/paper side effects start during doc generation.
os.environ.setdefault("ASTOCK_TESTING", "1")
os.environ.setdefault("ASTOCK_ENABLE_WEB_UI", "false")
os.environ.setdefault("ASTOCK_SCHEDULER_ENABLED", "false")

from tradingagents.astock.api import create_app  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OUT_PATH = _REPO_ROOT / "docs" / "API_REFERENCE.md"
_METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


def _blueprint_name(endpoint: str) -> str:
    return endpoint.split(".")[0] if "." in endpoint else endpoint


def collect_routes(app):
    """Return {blueprint: [(method, path, doc), ...]} plus summary counts."""
    by_bp: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    paths: set[str] = set()
    variants: set[tuple[str, str]] = set()

    for rule in app.url_map.iter_rules():
        path = str(rule)
        if not path.startswith("/api/"):
            continue
        paths.add(path)
        view = app.view_functions.get(rule.endpoint)
        doc = ""
        if view is not None and view.__doc__:
            doc = view.__doc__.strip().splitlines()[0].strip()
        bp = _blueprint_name(rule.endpoint)
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            variants.add((method, path))
            by_bp[bp].append((method, path, doc))

    return by_bp, paths, variants


def render(by_bp, paths, variants) -> str:
    generated = _dt.date.today().isoformat()
    lines: list[str] = []
    lines.append("# A-Stock API 端点参考\n")
    lines.append(f"> 自动生成于代码（`scripts/gen_api_reference.py`），更新于 {generated}。以实际代码为准。\n")
    lines.append(
        f"> 共 **{len(variants)}** 个端点（含 HTTP 方法变体，对应 **{len(paths)}** 个唯一路径），"
        f"覆盖 **{len(by_bp)}** 个路由模块。\n"
    )

    for bp in sorted(by_bp):
        rows = sorted(
            set(by_bp[bp]),
            key=lambda r: (r[1], _METHOD_ORDER.get(r[0], 9)),
        )
        lines.append(f"\n## `routes_{bp}.py`\n")
        lines.append("| Method | Path | 说明 |")
        lines.append("|--------|------|------|")
        for method, path, doc in rows:
            lines.append(f"| `{method}` | `{path}` | {doc or '(无描述)'} |")

    return "\n".join(lines) + "\n"


def main() -> None:
    app = create_app()
    by_bp, paths, variants = collect_routes(app)
    _OUT_PATH.write_text(render(by_bp, paths, variants), encoding="utf-8")
    print(f"Wrote {_OUT_PATH.relative_to(_REPO_ROOT)}")
    print(f"  endpoint variants (method,path): {len(variants)}")
    print(f"  unique paths:                    {len(paths)}")
    print(f"  route modules (blueprints):      {len(by_bp)}")


if __name__ == "__main__":
    main()

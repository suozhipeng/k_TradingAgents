"""Verification provenance for live-verified provider capability claims.

This module enables programmatic capture of the environment, date, commit SHA,
and test command at the time of live provider verification, replacing hardcoded
verification metadata with a self-documenting, auditable provenance record.
"""

from __future__ import annotations

import datetime
import functools
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class VerificationProvenance:
    """Immutable snapshot of a live provider verification.

    Attributes:
        verified_on: ISO date string (e.g. "2026-06-14").
        verified_at_commit: Git commit SHA from ``git rev-parse HEAD``,
            or ``"unknown"`` if git is unavailable.
        test_command: The exact pytest invocation used for verification.
        python_version: Python version string (``sys.version.split()[0]``).
        platform: Platform identifier from ``platform.platform()``.
        capabilities: Sorted tuple of verified capability names.
        evidence_ref: Path to the phase archive doc or verification log
            that validates this provider was verified, or a descriptive
            string for providers without live verification.
        pass_count: Number of passing tests (default 0).
        fail_count: Number of failing tests (default 0).
        skip_count: Number of skipped tests (default 0).
    """

    verified_on: str
    verified_at_commit: str
    test_command: str
    python_version: str
    platform: str
    capabilities: tuple[str, ...]
    evidence_ref: str
    pass_count: int = 0
    fail_count: int = 0
    skip_count: int = 0

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "verified_on": self.verified_on,
            "verified_at_commit": self.verified_at_commit,
            "test_command": self.test_command,
            "python_version": self.python_version,
            "platform": self.platform,
            "capabilities": list(self.capabilities),
            "evidence_ref": self.evidence_ref,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "skip_count": self.skip_count,
        }


@functools.lru_cache(maxsize=1)
def _get_commit_sha() -> str:
    """Return the current git commit SHA, or ``"unknown"`` on failure.

    Cached after the first call so repeated invocations during a single
    ``payload()`` call do not re-invoke subprocess.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = result.stdout.strip()
        return sha if sha else "unknown"
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def capture_verification_provenance(
    *,
    test_command: str,
    capabilities: tuple[str, ...],
    evidence_ref: str,
    pass_count: int = 0,
    fail_count: int = 0,
    skip_count: int = 0,
) -> VerificationProvenance:
    """Build a provenance snapshot for a live provider verification.

    All keyword arguments are required (*except* ``pass_count``,
    ``fail_count``, and ``skip_count``, which default to 0).

    This function is **safe to call at module import time** — the git
    subprocess call is guarded against ``FileNotFoundError`` and
    ``CalledProcessError``.  However, the intent is that it be called
    *inside* ``payload()``, not at module level, so that the import
    graph can resolve without git access.
    """
    cap_sorted = tuple(sorted(capabilities)) if capabilities else ()
    return VerificationProvenance(
        verified_on=datetime.date.today().isoformat(),
        verified_at_commit=_get_commit_sha(),
        test_command=test_command,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        capabilities=cap_sorted,
        evidence_ref=evidence_ref,
        pass_count=pass_count,
        fail_count=fail_count,
        skip_count=skip_count,
    )


def preserve_verification_provenance(
    provider_name: str,
    provenance: VerificationProvenance,
    base_dir: str = "docs/verification_provenance",
) -> str:
    """Write a provenance record to a JSON file for durable archival.

    Creates ``{base_dir}/{provider_name}_{verified_on}.json``.
    Returns the absolute path of the written file.
    """
    path = Path(base_dir).resolve() / f"{provider_name}_{provenance.verified_on}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(provenance.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    )
    return str(path)


def load_verification_provenance(
    provider_name: str,
    base_dir: str = "docs/verification_provenance",
) -> VerificationProvenance:
    """Load the most recent provenance record from durable JSON storage.

    Scans ``{base_dir}/{provider_name}_*.json`` files sorted by filename
    in descending order and returns the parsed result of the most recent
    file.  If no files exist, returns a static default with
    ``verified_on="unknown"``.

    Args:
        provider_name: Provider identifier (e.g. ``"akshare"``).
        base_dir: Directory containing provenance JSON files.

    Returns:
        A ``VerificationProvenance`` instance.
    """
    base = Path(base_dir).resolve()
    pattern = f"{provider_name}_*.json"
    files = sorted(base.glob(pattern), reverse=True)
    if files:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        return VerificationProvenance(
            verified_on=data.get("verified_on", "unknown"),
            verified_at_commit=data.get("verified_at_commit", "unknown"),
            test_command=data.get("test_command", ""),
            python_version=data.get("python_version", ""),
            platform=data.get("platform", ""),
            capabilities=tuple(data.get("capabilities", [])),
            evidence_ref=data.get("evidence_ref", ""),
            pass_count=data.get("pass_count", 0),
            fail_count=data.get("fail_count", 0),
            skip_count=data.get("skip_count", 0),
        )
    return VerificationProvenance(
        verified_on="unknown",
        verified_at_commit="unknown",
        test_command="",
        python_version="",
        platform="",
        capabilities=(),
        evidence_ref=f"No durable verification record found for '{provider_name}'.",
    )


def render_provenance_block(provenance: VerificationProvenance) -> dict:
    """Render a provenance record as a dict suitable for the blueprint payload.

    This is a thin wrapper around ``provenance.to_dict()`` and exists
    as a named export so callers can swap rendering strategies later.
    """
    return provenance.to_dict()

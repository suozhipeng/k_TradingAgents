from __future__ import annotations

import pytest

from scripts.hermes_codex_git_gate import ensure_accept, normalize_verdict


@pytest.mark.unit
def test_normalize_verdict_accepts_known_values():
    assert normalize_verdict("accept") == "accept"
    assert normalize_verdict("Partial") == "partial"
    assert normalize_verdict(" FAIL ") == "fail"


@pytest.mark.unit
def test_normalize_verdict_rejects_unknown_value():
    with pytest.raises(ValueError):
        normalize_verdict("approved")


@pytest.mark.unit
def test_ensure_accept_requires_accept():
    ensure_accept("accept")
    with pytest.raises(ValueError):
        ensure_accept("partial")
